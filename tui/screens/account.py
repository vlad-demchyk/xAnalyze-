"""Sign in to the account that pays for AI calls.

Settings has always let a person choose `xformat` as the provider, and the
TUI had no way to sign in to it - so choosing it and having no session was
reachable from here and only fixable from the window or from
`xanalyze ai login`. A setting whose one prerequisite lives on another
surface is a setting that lies about what it does.

The password is never stored, here or anywhere: `sign_in` exchanges it for a
token that goes to the OS keychain, and the field is cleared before the
result is even looked at. That is the same contract `ui/sign_in_dialog.py`
and `cli_impl.aicmds.cmd_ai_login` keep, and it is why this screen exists
while an API-key field still deliberately does not - a key is a secret that
would have to be *kept*, and a password here is one that is spent.

The call is made off the UI thread. A sign-in on a captive network is thirty
seconds of a frozen interface otherwise, which is the same reason
`UpdateScreen` threads its own network call.
"""
from __future__ import annotations

import threading

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label, Static

import config

from tui.screens.base import XScreen

#: The only provider with credentials to take. Claude Code owns its own
#: sign-in and Anthropic takes a key, so for those this screen says where to
#: go rather than pretending to a flow it does not have - the same three-way
#: answer `xanalyze ai login` gives.
SIGNS_IN = "xformat"


class AccountScreen(XScreen):
    """Who is signed in, and the two buttons that change it."""

    BINDINGS = [
        ("escape", "back", "Back"),
        ("ctrl+r", "refresh", "Refresh"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._busy = False

    def compose(self) -> ComposeResult:
        yield from self.compose_chrome()
        with Vertical(id="account-view"):
            yield Label(self.tr("tui_account_title"), classes="menu-title")
            yield Static("")
            yield Label("", id="account-state")
            yield Static("")
            yield Label(self.tr("tui_account_email"))
            yield Input(placeholder=self.tr("tui_account_email_placeholder"),
                        id="account-email")
            yield Label(self.tr("tui_account_password"))
            yield Input(password=True, id="account-password")
            yield Static("")
            with Horizontal():
                yield Button(self.tr("settings_sign_in"), id="sign-in",
                             variant="primary")
                yield Button(self.tr("tui_account_sign_out"), id="sign-out")
                yield Button(self.tr("tui_back"), id="back")
            yield Static("")
            yield Label("", id="account-status")
            yield Label(self.tr("tui_account_privacy"), classes="hint")

    def on_mount(self) -> None:
        self.action_refresh()

    def on_screen_resume(self) -> None:
        self.action_refresh()

    # ------------------------------------------------------------- state
    def _provider(self):
        from llm.base import LLMProviderFactory

        settings = config.Settings.load()
        return LLMProviderFactory.create(
            SIGNS_IN, base_url=settings.xformat_base_url,
            endpoints=settings.xformat_endpoints,
        ), settings

    def action_refresh(self) -> None:
        """Say who is signed in, and say it about the chosen provider.

        A screen that reported the xFormat session while the run was
        configured to use Claude Code would be answering a question nobody
        asked, so the other two providers are told where their sign-in
        actually lives instead.
        """
        settings = config.Settings.load()
        state = self.query_one("#account-state", Label)
        if settings.llm_provider != SIGNS_IN:
            state.update(self.tr(f"tui_account_elsewhere_{settings.llm_provider}")
                         if settings.llm_provider in ("anthropic", "claude-code")
                         else self.tr("tui_account_not_xformat"))
            self._enable(False)
            return
        self._enable(True)
        try:
            provider, _settings = self._provider()
            status = provider.auth_status()
        except Exception as exc:  # noqa: BLE001 - shown, never swallowed
            state.update(self.tr("tui_account_unknown", detail=str(exc)))
            return
        if status.signed_in:
            state.update(self.tr("tui_account_signed_in",
                                 email=status.email or "?"))
        else:
            state.update(self.tr("tui_account_signed_out"))

    def _enable(self, enabled: bool) -> None:
        for widget_id in ("sign-in", "sign-out"):
            self.query_one(f"#{widget_id}", Button).disabled = not enabled
        for widget_id in ("account-email", "account-password"):
            self.query_one(f"#{widget_id}", Input).disabled = not enabled

    def _status(self, text: str) -> None:
        self.query_one("#account-status", Label).update(text)

    # ------------------------------------------------------------ actions
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.action_back()
        elif event.button.id == "sign-in":
            self._sign_in()
        elif event.button.id == "sign-out":
            self._sign_out()

    def _sign_in(self) -> None:
        if self._busy:
            return
        email = self.query_one("#account-email", Input).value.strip()
        password_field = self.query_one("#account-password", Input)
        password = password_field.value
        if not email or not password:
            self._status(self.tr("settings_need_credentials"))
            return
        # Cleared here, before the call: whatever happens next, it is not
        # sitting in a widget waiting to be read off a shared screen.
        password_field.value = ""
        self._busy = True
        self._status(self.tr("tui_account_working"))

        def work() -> None:
            try:
                provider, _settings = self._provider()
                status = provider.sign_in(email, password)
            except Exception as exc:  # noqa: BLE001 - shown to the user
                self.app.call_from_thread(self._done, None, str(exc))
                return
            self.app.call_from_thread(self._done, status, "")

        threading.Thread(target=work, daemon=True).start()

    def _sign_out(self) -> None:
        try:
            provider, _settings = self._provider()
            provider.sign_out()
        except Exception as exc:  # noqa: BLE001 - shown to the user
            self._status(str(exc))
            return
        self._status(self.tr("tui_account_signed_out"))
        self.action_refresh()

    def _done(self, status, error: str) -> None:
        self._busy = False
        if error:
            self._status(error)
        elif status is not None and not status.signed_in:
            self._status(self.tr("settings_not_signed_in",
                                 detail=status.detail))
        else:
            self._status(self.tr("tui_account_welcome"))
        self.action_refresh()
