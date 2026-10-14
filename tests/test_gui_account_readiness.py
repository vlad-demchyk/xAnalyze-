"""Selected-provider readiness is independent of the header account and GUI thread."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import threading
import time
from types import SimpleNamespace

import pytest
try:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget
    from ui.app_state import AppState
    from ui.window_parts.account import AccountMixin, UNASKED
except ImportError:
    pytest.skip("PySide6 unavailable", allow_module_level=True)

from llm.base import AuthStatus, LLMProviderFactory
from analysis_modes import METHOD_AI, METHOD_LOCAL


class Provider:
    def __init__(self, name, signed_in=False, gate=None):
        self.name, self.signed_in, self.gate = name, signed_in, gate
        self.calls = []
    def auth_status(self, **kwargs):
        self.calls.append((threading.get_ident(), kwargs))
        if self.gate:
            self.gate.wait(2)
        return AuthStatus(self.signed_in, "fixture@example.test" if self.signed_in else "")
    def sign_out(self):
        self.signed_in = False


class Window(AccountMixin, QWidget):
    def __init__(self, provider):
        super().__init__()
        self.settings = SimpleNamespace(llm_provider=provider, xformat_base_url="https://fixture.invalid",
            xformat_endpoints={}, prefer_claude_code_in_cli=False, claude_model="fixture", claude_code_model="fixture",
            claude_code_effort="low")
        self.lang = "uk"
        self.app_state = AppState(self)
        self.account_label, self.account_btn = QLabel(self), QPushButton(self)
        self._account_cache = UNASKED
        self.analyze_btn = QPushButton(self)
        self.view_model = SimpleNamespace(is_busy=False)
        self.status_bar = SimpleNamespace(showMessage=lambda *_args: None)
        self._retranslate_choices = lambda: None
    def closeEvent(self, event):
        if hasattr(self, "_stop_account_checks"):
            self._stop_account_checks()
        super().closeEvent(event)


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def wait_until(app, predicate, timeout=.7):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        time.sleep(.005)
    assert predicate(), "GUI condition did not arrive"


def providers(monkeypatch, account, selected):
    monkeypatch.setattr(LLMProviderFactory, "create", lambda name, **kwargs: account if name == "xformat" else selected)
    monkeypatch.setattr("config.get_anthropic_api_key", lambda: "owned-fixture-key")


@pytest.mark.parametrize("name", ["anthropic", "claude-code"])
def test_personal_provider_offers_ai_without_xformat_account(app, monkeypatch, name):
    account, selected = Provider("xformat"), Provider(name, True)
    providers(monkeypatch, account, selected)
    window = Window(name)
    try:
        window._refresh_account_control(refresh=True)
        wait_until(app, lambda: window.app_state.ai_available)
        assert window._account_status(ask=False) is None
        assert selected.calls and selected.calls[0][0] != threading.get_ident()
        assert account.calls[0][1].get("read_only") is True
    finally:
        window.close()


def test_slow_status_keeps_gui_timer_running(app, monkeypatch):
    gate = threading.Event()
    account, selected = Provider("xformat", gate=gate), Provider("anthropic", True)
    providers(monkeypatch, account, selected)
    window = Window("anthropic")
    ticks = []
    QTimer.singleShot(10, lambda: ticks.append(True))
    try:
        began = time.monotonic()
        window._refresh_account_control(refresh=True)
        assert time.monotonic() - began < .1
        wait_until(app, lambda: bool(ticks), timeout=.15)
        assert account.calls[0][0] != threading.get_ident()
        gate.set()
        wait_until(app, lambda: window.app_state.ai_available)
    finally:
        gate.set();window.close()


def test_old_provider_result_cannot_enable_ai_after_switch(app, monkeypatch):
    gate = threading.Event()
    account, selected = Provider("xformat"), Provider("anthropic", True, gate)
    providers(monkeypatch, account, selected)
    window = Window("anthropic")
    try:
        window._refresh_account_control(refresh=True)
        wait_until(app, lambda: bool(selected.calls))
        window.settings.llm_provider = "xformat"
        window._refresh_account_control(refresh=True)
        wait_until(app, lambda: not getattr(window, "_account_checking", False))
        gate.set()
        wait_until(app, lambda: not window._account_results.empty())
        # A completed generation stops polling. The queued late reply must
        # also be harmless when polling resumes for a later refresh.
        window._poll_account_check()
        assert not window.app_state.ai_available
    finally:
        gate.set();window.close()


def test_closed_window_does_not_receive_late_status(app, monkeypatch):
    gate = threading.Event()
    account, selected = Provider("xformat", gate=gate), Provider("anthropic", True)
    providers(monkeypatch, account, selected)
    window = Window("anthropic")
    window._refresh_account_control(refresh=True)
    window.close();gate.set()
    deadline = time.monotonic() + .1
    while time.monotonic() < deadline:
        app.processEvents();time.sleep(.005)
    assert window._account_cache is UNASKED and not window.app_state.ai_available


def test_existing_ai_choice_waits_for_provider_then_is_restored(app, monkeypatch):
    gate = threading.Event()
    account, selected = Provider("xformat"), Provider("anthropic", True, gate)
    providers(monkeypatch, account, selected)
    window = Window("anthropic")
    try:
        window.app_state.set_ai_available(True)
        window.app_state.set_methods((METHOD_AI,))
        window._refresh_account_control(refresh=True)
        assert not window.analyze_btn.isEnabled()
        gate.set()
        wait_until(app, lambda: window.app_state.ai_available)
        assert window.app_state.methods == (METHOD_AI,) and window.analyze_btn.isEnabled()
    finally:
        gate.set();window.close()


def test_explicit_local_choice_during_check_is_not_changed_back_to_ai(app, monkeypatch):
    gate = threading.Event()
    account, selected = Provider("xformat"), Provider("anthropic", True, gate)
    providers(monkeypatch, account, selected)
    window = Window("anthropic")
    try:
        window.app_state.set_ai_available(True)
        window.app_state.set_methods((METHOD_AI,))
        window._refresh_account_control(refresh=True)
        window._discard_pending_ai_method()
        gate.set()
        wait_until(app, lambda: window.app_state.ai_available)
        assert window.app_state.methods == (METHOD_LOCAL,)
    finally:
        gate.set();window.close()


def test_signed_in_header_does_not_enable_a_different_missing_provider(app, monkeypatch):
    account, selected = Provider("xformat", True), Provider("anthropic", False)
    providers(monkeypatch, account, selected)
    window = Window("anthropic")
    try:
        window._refresh_account_control(refresh=True)
        wait_until(app, lambda: not window._account_checking)
        assert window._account_cache.signed_in and not window.app_state.ai_available
    finally:
        window.close()


def test_slow_selected_provider_does_not_keep_known_header_account_pending(app, monkeypatch):
    gate = threading.Event()
    account, selected = Provider("xformat"), Provider("claude-code", True, gate)
    providers(monkeypatch, account, selected)
    window = Window("claude-code")
    try:
        window._refresh_account_control(refresh=True)
        wait_until(app, lambda: window._account_cache is None, timeout=.2)
        assert window.account_btn.isEnabled() and window._account_checking
        gate.set()
        wait_until(app, lambda: window.app_state.ai_available)
    finally:
        gate.set();window.close()


def test_slow_xformat_does_not_delay_personal_provider_readiness(app, monkeypatch):
    gate = threading.Event()
    account, selected = Provider("xformat", gate=gate), Provider("anthropic", True)
    providers(monkeypatch, account, selected)
    window = Window("anthropic")
    try:
        window._refresh_account_control(refresh=True)
        wait_until(app, lambda: window.app_state.ai_available, timeout=.2)
        assert window._account_cache is UNASKED
    finally:
        gate.set();window.close()


def test_signing_out_of_header_account_keeps_personal_provider_and_ai_choice(app, monkeypatch):
    account, selected = Provider("xformat", True), Provider("anthropic", True)
    providers(monkeypatch, account, selected)
    window = Window("anthropic")
    try:
        window._account_cache = AuthStatus(True, "fixture@example.test")
        window._provider_ready = True
        window.app_state.set_ai_available(True)
        window.app_state.set_methods((METHOD_AI,))
        window._sign_out()
        assert window._account_cache is None and window.app_state.ai_available
        assert window.app_state.methods == (METHOD_AI,)
    finally:
        window.close()


def test_inline_selector_activation_is_user_only_even_for_same_value(app):
    from ui.widgets import InlineValue
    value = InlineValue()
    value.set_items([("Local", "local"), ("AI", "ai")])
    activated = []
    value.activated.connect(activated.append)
    value.setCurrentIndex(1)
    assert activated == []
    value._activate_index(1)
    assert activated == [1]


def test_keyboard_selection_emits_user_activation(app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from ui.widgets import InlineValue
    value = InlineValue()
    value.set_items([("Local", "local"), ("AI", "ai")])
    activated = []
    value.activated.connect(activated.append)
    QTest.keyClick(value, Qt.Key.Key_Right)
    assert value.currentData() == "ai" and activated == [1]


def test_pending_ai_request_is_not_silently_started_as_offline(app, monkeypatch):
    from ui.main_window import MainWindow
    window = Window("anthropic")
    window._account_checking = True
    window._pending_ai_methods = (METHOD_AI,)
    window._validate_target = lambda: pytest.fail("run began before provider check")
    try:
        MainWindow._on_analyze_clicked(window)
    finally:
        window.close()


def test_actual_window_provider_switch_restores_ai_and_routes_new_provider(app, monkeypatch):
    import config
    from ui.main_window import MainWindow
    account, api, cli = Provider("xformat"), Provider("anthropic", True), Provider("claude-code", True)
    lookup = {"xformat": account, "anthropic": api, "claude-code": cli}
    monkeypatch.setattr(LLMProviderFactory, "create", lambda name, **kwargs: lookup[name])
    monkeypatch.setattr("config.get_anthropic_api_key", lambda: "owned-fixture-key")
    settings = config.Settings(llm_provider="anthropic", ui_language="uk")
    settings.save = lambda: None
    monkeypatch.setattr(config.Settings, "load", lambda: settings)
    window = MainWindow()
    try:
        wait_until(app, lambda: window.app_state.ai_available)
        window.method_combo.setCurrentIndex(window.method_combo.findData(window.choice_key((METHOD_AI,))))
        window.provider_combo.setCurrentIndex(window.provider_combo.findData("claude-code"))
        wait_until(app, lambda: window.app_state.ai_available)
        assert window.current_request().methods == (METHOD_AI,)
        assert window._detector_for_request()[0] == "claude-code-llm-judge"
    finally:
        window.close()


def test_signin_during_old_probe_enables_run_and_selects_xformat_billing(app, monkeypatch):
    import config
    from PySide6.QtWidgets import QDialog
    from ui.main_window import MainWindow
    import ui.sign_in_dialog
    gate = threading.Event()
    account, api, cli = Provider("xformat"), Provider("anthropic", True), Provider("claude-code", True, gate)
    lookup = {"xformat": account, "anthropic": api, "claude-code": cli}
    monkeypatch.setattr(LLMProviderFactory, "create", lambda name, **kwargs: lookup[name])
    monkeypatch.setattr("config.get_anthropic_api_key", lambda: "owned-fixture-key")
    settings = config.Settings(llm_provider="anthropic", ui_language="uk")
    settings.save = lambda: None
    monkeypatch.setattr(config.Settings, "load", lambda: settings)
    class AcceptedDialog:
        def __init__(self, *args):
            self.status = AuthStatus(True, "owned@example.test")
        def exec(self):
            account.signed_in = True
            return QDialog.DialogCode.Accepted
    monkeypatch.setattr(ui.sign_in_dialog, "SignInDialog", AcceptedDialog)
    window = MainWindow()
    try:
        wait_until(app, lambda: window.app_state.ai_available)
        window.method_combo.setCurrentIndex(window.method_combo.findData(window.choice_key((METHOD_AI,))))
        window.provider_combo.setCurrentIndex(window.provider_combo.findData("claude-code"))
        wait_until(app, lambda: bool(cli.calls))
        assert not window.analyze_btn.isEnabled()
        window._sign_in()
        assert window.analyze_btn.isEnabled()
        assert window.settings.llm_provider == window.provider_combo.currentData() == window.app_state.provider == "xformat"
        assert set(window.current_request().methods) == {METHOD_LOCAL, METHOD_AI}
        gate.set()
        deadline = time.monotonic() + .1
        while time.monotonic() < deadline:
            app.processEvents();time.sleep(.005)
        assert window.app_state.ai_available
    finally:
        gate.set();window.close()
