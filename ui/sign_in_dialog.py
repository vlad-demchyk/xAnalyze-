"""Signing in to the xFormat subscription, asked as one small question.

Separate from the settings dialog on purpose. Settings is where a preference
lives; signing in is an action with a visible consequence - the AI assessment
becomes available and starts being paid for by the subscription - and burying
an action among preferences is what made the toolbar's account state invisible.

The password is never stored, here or anywhere: `sign_in` exchanges it for
tokens and this dialog clears the field the moment it returns.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout,
)

from i18n.translations import t
from llm import credentials
from llm.base import LLMAuthError, LLMUnavailable


class SignInDialog(QDialog):
    """Asks for an email and a password, and reports what came back.

    `status` is None until a sign-in succeeds, so the caller can tell "the
    dialog was closed" from "the account is connected" without asking the
    provider a second question.
    """

    def __init__(self, provider, lang: str, parent=None):
        super().__init__(parent)
        self.provider = provider
        self.lang = lang
        self.status = None

        self.setWindowTitle(t("sign_in_title", lang))
        layout = QVBoxLayout(self)

        hint = QLabel(t("sign_in_hint", lang))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        form = QFormLayout()
        self.email_edit = QLineEdit(
            credentials.load_secret("xformat_account_email") or "")
        form.addRow(t("settings_email", lang), self.email_edit)
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText(t("settings_password_hint", lang))
        form.addRow(t("settings_password", lang), self.password_edit)
        layout.addLayout(form)

        self.message = QLabel()
        self.message.setWordWrap(True)
        layout.addWidget(self.message)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            t("settings_sign_in", lang))
        buttons.accepted.connect(self._on_sign_in)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_sign_in(self) -> None:
        email = self.email_edit.text().strip()
        password = self.password_edit.text()
        if not email or not password:
            self.message.setText(t("settings_need_credentials", self.lang))
            return
        try:
            status = self.provider.sign_in(email, password)
        except (LLMAuthError, LLMUnavailable) as exc:
            self.message.setText(str(exc))
            return
        # Cleared before anything else happens with it.
        self.password_edit.clear()
        if not status.signed_in:
            self.message.setText(
                t("settings_not_signed_in", self.lang, detail=status.detail))
            return
        self.status = status
        self.accept()
