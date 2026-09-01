"""A window where a person signs in to the site themselves.

Nothing else in this application handles anybody's credentials, and this
does not either: it opens a real browser view on the site's own sign-in
page, and whatever the site gives that browser is what the run will use.
2FA, SSO, a captcha, a corporate identity provider - all of them work here
for the same reason they work in a browser, because this *is* one.

Two things it must get right:

* **The profile is persistent and named after the host.** An off-the-record
  profile is the right default for auditing a stranger's site and the wrong
  one here: the session would not survive the window closing. See
  `audit.driver.open_session_profile` and `site_session`.
* **The fetcher gets the session too.** The crawl reads pages with
  `requests`, which shares no storage with QtWebEngine, so the cookies are
  copied across as they arrive. Without that half, the browser sees the
  account and the crawl sees the login form - one run, two answers.

What is deliberately *not* here: any attempt to fill the form, remember a
password, or detect which field is which. The window is a browser and the
person is the one signing in.
"""
from __future__ import annotations

from PySide6.QtCore import QUrl, Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QVBoxLayout,
)

import site_session
from i18n.translations import t


class SiteSignInDialog(QDialog):
    """Sign in to `url` in a real browser view, and keep the session."""

    #: How big the view has to be for a real sign-in page - including the
    #: identity provider's, which is usually the taller of the two.
    SIZE = (980, 760)

    def __init__(self, url: str, lang: str = "uk", parent=None):
        super().__init__(parent)
        self.lang = lang
        self.url = url
        self.host = site_session.host_of(url)
        self.saved = False
        #: Collected as the site sets them, because `allCookies()` is not a
        #: question a cookie store answers synchronously.
        self._cookies: dict = {}
        self._page = None

        self.setWindowTitle(t("sign_in_site_title", lang, host=self.host))
        self.resize(*self.SIZE)

        layout = QVBoxLayout(self)
        note = QLabel(t("sign_in_site_note", lang, host=self.host))
        note.setWordWrap(True)
        layout.addWidget(note)

        from PySide6.QtWebEngineWidgets import QWebEngineView

        from audit import driver

        self.profile = driver.open_session_profile(self.host, parent=self)
        self.view = QWebEngineView(self)
        self._attach_page()
        layout.addWidget(self.view, 1)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        buttons = QDialogButtonBox(self)
        self.done_btn = buttons.addButton(t("sign_in_site_done", lang),
                                          QDialogButtonBox.ButtonRole.AcceptRole)
        self.forget_btn = buttons.addButton(t("sign_in_site_forget", lang),
                                            QDialogButtonBox.ButtonRole.DestructiveRole)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        self.done_btn.clicked.connect(self._on_done)
        self.forget_btn.clicked.connect(self._on_forget)
        buttons.rejected.connect(self.reject)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(buttons)
        layout.addLayout(row)

        self.view.load(QUrl(self.url))

    def _attach_page(self) -> None:
        from PySide6.QtWebEngineCore import QWebEnginePage

        page = QWebEnginePage(self.profile, self)
        self._page = page
        self.view.setPage(page)
        store = self.profile.cookieStore()
        store.cookieAdded.connect(self._on_cookie)
        store.cookieRemoved.connect(self._on_cookie_removed)

    # ------------------------------------------------------------- cookies
    def _on_cookie(self, cookie) -> None:
        name = bytes(cookie.name()).decode("utf-8", "replace")
        value = bytes(cookie.value()).decode("utf-8", "replace")
        self._cookies[name] = value

    def _on_cookie_removed(self, cookie) -> None:
        self._cookies.pop(bytes(cookie.name()).decode("utf-8", "replace"), None)

    # ------------------------------------------------------------- actions
    def _on_done(self) -> None:
        """Keep what the browser was given, and say what was kept.

        The count is the only thing shown - never a name and never a value.
        A dialog that prints a session cookie has handed the session to
        whoever is looking at the screen, and to whoever reads the
        screenshot afterwards.
        """
        site_session.save_cookies(self.host, self._cookies)
        self.saved = True
        self.status.setText(t("sign_in_site_saved", self.lang,
                              host=self.host, count=len(self._cookies)))
        self.accept()

    def _on_forget(self) -> None:
        site_session.forget(self.host)
        self._cookies.clear()
        self.saved = False
        self.status.setText(t("sign_in_site_forgotten", self.lang, host=self.host))

    def _keep_what_the_browser_has(self) -> None:
        """Save on the way out too, so a session cannot end up half-made.

        The persistent profile is written by QtWebEngine the moment the site
        sets a cookie, and closing the window does not undo that - so a
        person who signed in and then closed with the title-bar button would
        leave the *renderer* authenticated and the *fetcher* not, which is
        the exact split this whole feature exists to avoid. Pressing Done is
        still the way to be told it worked; this is the safety net under it.
        """
        if self.saved or not self._cookies:
            return
        site_session.save_cookies(self.host, self._cookies)
        self.saved = True

    def reject(self) -> None:  # noqa: D102 - Qt's name; see the helper above
        self._keep_what_the_browser_has()
        super().reject()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt's name
        self._keep_what_the_browser_has()
        # The profile owns a running renderer process; releasing it here
        # rather than at interpreter shutdown is what stops Qt's "profile
        # still in use" warning, which is a real warning about a real leak.
        try:
            store = self.profile.cookieStore()
            store.cookieAdded.disconnect(self._on_cookie)
            store.cookieRemoved.disconnect(self._on_cookie_removed)
        except Exception:  # noqa: BLE001 - already gone is fine
            pass
        # Order matters and Qt says so out loud: releasing a profile whose
        # page is still alive prints "Release of profile requested but
        # WebEnginePage still not deleted. Expect troubles!" - and the
        # troubles are a renderer process outliving the dialog.
        self.view.setPage(None)
        if self._page is not None:
            self._page.setParent(None)
            self._page.deleteLater()
            self._page = None
        super().closeEvent(event)
