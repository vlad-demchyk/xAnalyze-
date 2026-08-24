"""The xFormat account control in the brand header."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog

from analysis_modes import METHOD_AI, METHOD_LOCAL
from i18n.translations import t


def _ask_account_later(window) -> None:
    """Ask about the account once the window is on screen.

    Deferred rather than skipped: the header should end up telling the truth,
    it just must not make startup wait for a round trip to do so.
    """
    from PySide6.QtCore import QTimer

    QTimer.singleShot(0, lambda: window._refresh_account_control(refresh=True))


#: "This has not been asked yet", distinct from "the answer is no".
UNASKED = object()

# Private alias: the name this lived under inside main_window.py before the
# split, kept so older call sites read unchanged.
_UNASKED = UNASKED


class AccountMixin:
    """Sign-in state for the header's account button.

    Reads `self.settings`, `self.lang`, `self.account_label`,
    `self.account_btn` and the choice widgets from the facade.
    """

    def _xformat_provider(self):
        from llm.base import LLMProviderFactory

        return LLMProviderFactory.create(
            "xformat",
            base_url=self.settings.xformat_base_url,
            endpoints=self.settings.xformat_endpoints or {},
        )

    def _account_status(self, refresh: bool = False, ask: bool = True):
        """The xFormat account's state, or None when it cannot be asked.

        Asked of the subscription specifically, not of whichever provider is
        configured: this control is about the account, and a machine with a
        personal key but no account is signed out as far as it is concerned.

        Cached, because every answer is a network round trip and the question
        is asked on every retranslate. Refreshed only where the answer can
        actually have changed - signing in, signing out, opening settings.
        """
        if refresh:
            self._account_cache = _UNASKED
        if self._account_cache is not _UNASKED:
            return self._account_cache
        if not ask:
            # Building the window must not wait on the network. The control is
            # drawn as signed out and corrected a moment later, which is honest:
            # nothing is known yet.
            return None

        from llm.base import LLMAuthError, LLMUnavailable

        try:
            status = self._xformat_provider().auth_status()
        except (LLMAuthError, LLMUnavailable, Exception):  # noqa: BLE001
            status = None
        self._account_cache = status if status and status.signed_in else None
        return self._account_cache

    def _refresh_account_control(self, refresh: bool = False,
                                 ask: bool = True) -> None:
        status = self._account_status(refresh=refresh, ask=ask)
        if status is not None:
            self.account_label.setText(status.detail)
            self.account_btn.setText(t("settings_sign_out", self.lang))
        else:
            self.account_label.setText("")
            self.account_btn.setText(t("settings_sign_in", self.lang))
        # The one place that learns whether an AI pass can be paid for is
        # also the place that has to say so. `AppState` normalises the
        # method choice against this, and it was never told: the state kept
        # its startup default of "no account", so a signed-in user asking
        # for the AI pass had it silently normalised back to offline.
        if ask or status is not None:
            self.app_state.set_ai_available(status is not None)

    def _on_account_clicked(self) -> None:
        if self._account_status(refresh=True) is not None:
            self._sign_out()
            return
        self._sign_in()

    def _sign_in(self) -> None:
        from ui.sign_in_dialog import SignInDialog

        dialog = SignInDialog(self._xformat_provider(), self.lang, self)
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.status is None:
            return
        # Signing in *is* the choice of who pays: an account that was just
        # connected and then ignored in favour of a personal key would make the
        # sign-in pointless. The CLI's rule is the opposite and stays that way -
        # inside a Claude Code session its own signed-in account pays.
        self.settings.llm_provider = "xformat"
        self.settings.save()
        self._select_ai_method()
        self._refresh_account_control(refresh=True)
        self.status_bar.showMessage(
            t("sign_in_switched", self.lang, detail=dialog.status.detail))

    def _sign_out(self) -> None:
        try:
            self._xformat_provider().sign_out()
        except Exception as exc:  # noqa: BLE001 - the tokens are gone either way
            self.status_bar.showMessage(str(exc))
        self._refresh_account_control(refresh=True)
        # The method combo drops its AI entries when nothing can pay for them,
        # and a request that asked for AI normalises back to the offline engine.
        self._retranslate_choices()
        self.status_bar.showMessage(t("signed_out_message", self.lang))

    def _select_ai_method(self) -> None:
        """Offer the AI method and pick it, now that there is an account.

        Both rather than AI alone: the offline engine costs nothing and finds
        the exact character defects a model does not, so dropping it in
        exchange would be a downgrade disguised as an upgrade.
        """
        self._retranslate_choices()
        index = self.method_combo.findData(
            self.choice_key((METHOD_LOCAL, METHOD_AI)))
        if index >= 0:
            self.method_combo.setCurrentIndex(index)
