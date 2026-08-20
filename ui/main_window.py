from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QColor, QIcon, QKeySequence, QShortcut
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout,
    QFrame, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox,
    QPlainTextEdit, QPushButton, QSizePolicy, QSpinBox, QSplitter,
    QStackedWidget, QStatusBar, QTextEdit, QVBoxLayout, QWidget,
)

import config
import explanations
import suppression
import unicode_rules
from ui.app_state import AppState
from ui.view_model import MainViewModel
from audit import explanations as audit_explanations
from detectors.factory import DetectorFactory
from detectors.judges import PROVIDER_ORDER, judge_for_provider


def responsive_breakpoints():
    """The widths the audit runs at, imported lazily.

    Through a function rather than a module-level import because
    `audit.responsive` pulls in the driver, and the window must stay
    constructible on a machine where QtWebEngine is missing - the browser
    pass refuses itself with a sentence there, and a failed import at the
    top of this file would instead take the whole window down.
    """
    from audit.responsive import BREAKPOINTS
    return BREAKPOINTS
from file_writer import apply_replacements, build_plans
from analysis_modes import (
    CHECKS, CHECK_ACCESSIBILITY, CHECK_AI_PATTERNS, METHOD_AI, METHOD_LOCAL,
    METHODS, READER_BROWSER, READER_CODE, SOURCE_FILE, SOURCE_REPO,
    SOURCE_SITE, AnalysisRequest, available_readers, supports_browser,
)
from i18n.translations import t
from models import AnalysisResult, CodeBlock, Confidence, RepoAnalysisResult, TextBlock, TextSpan
from repo_scanner import (
    DEFAULT_IGNORE_PATTERNS, SCOPE_BOTH, SCOPE_CONTENT, SCOPE_TECHNICAL,
    _parse_ignore_text,
)
from ui import theme
from ui.code_preview import highlight_range
from ui.site_preview import build_highlight_js
from ui.widgets import (
    ROW_ROLE, EmptyState, FindingDelegate, FlowLayout, RowData, chip,
    diagnostics_message, divider, field, heading, muted, panel, restyle,
)
from ui.worker import (
    AnalysisWorker, AuditWorker, RepoAnalysisWorker, RewriteAllWorker,
    SingleBlockWorker, SingleRewriteWorker,
)

# Below this window width, the detail panel collapses from a persistent
# third column into an inline panel that expands under the clicked list row.
WIDE_BREAKPOINT = 1000

# Below this narrower width, the preview column (site render or source code)
# gives way too, leaving only the findings list. Two breakpoints rather than
# one: a single cutoff made the window jump from three columns straight to a
# squeezed two, since a column that "stays visible" but no longer fits its
# own minimum width doesn't read as staying - it reads as broken. Columns
# now fold one at a time, widest-dependency first: the detail column (which
# has an inline fallback already) goes first, the preview column (which has
# no substitute) goes only when there truly isn't room for it.
MEDIUM_BREAKPOINT = 620

#: Shipped design assets: the mark, in both themes, and the application icon.
#: Kept in the repository rather than reached for in the xFormat checkout, so
#: the app is the same whether it runs from source or from a bundle.
ASSETS = Path(__file__).resolve().parent / "design" / "assets"

#: This window's own tiny trilingual vocabulary for the styled-report button,
#: kept local rather than added to `i18n/translations.py`: this feature's
#: task boundary deliberately excludes that module, and three short strings
#: do not need the shared table's machinery (pluralisation, `t()` lookup) to
#: stay correct in uk/it/en.
_STYLED_REPORT_STRINGS = {
    "uk": dict(button="Стильний звіт", tooltip="Зберегти брендований звіт "
              "(PDF або HTML) для читання чи друку",
              done="Звіт збережено: {path}"),
    "it": dict(button="Report firmato", tooltip="Salva un report firmato "
              "(PDF o HTML) da leggere o stampare",
              done="Report salvato: {path}"),
    "en": dict(button="Styled report", tooltip="Save a branded report "
              "(PDF or HTML) to read or print",
              done="Report saved: {path}"),
}


def _styled_report_text(lang: str, key: str, **kwargs) -> str:
    strings = _STYLED_REPORT_STRINGS.get(lang, _STYLED_REPORT_STRINGS["en"])
    return strings[key].format(**kwargs)

MODE_WEB = "web"
MODE_REPO = "repo"
#: Auditing is a third source of findings, not a third detector: it reports
#: defects in the document (missing alt text, a broken heading order, a page
#: that ships 4 MB of JavaScript) rather than passages a person wrote. It
#: shares the toolbar's URL and depth fields because it asks about the same
#: site, and nothing else.
MODE_AUDIT = "audit"
#: Auditing one HTML file that is a whole page - a site built or exported into
#: a single self-contained file. Not repo mode: that reads fragments inside a
#: project, while this is a finished document, so it gets a `<head>` audit,
#: line numbers, and a real browser render from `file://`.
MODE_FILE = "file"

#: Severity mapped to the badge class the style sheet already paints for
#: confidence. One vocabulary of colour for the window, not two.
_SEVERITY_BADGE = {
    "critical": theme.CLASS_BADGE_HIGH,
    "serious": theme.CLASS_BADGE_HIGH,
    "moderate": theme.CLASS_BADGE_MEDIUM,
    "minor": theme.CLASS_BADGE_LOW,
}

#: Severity is the audit's name for the axis the finding delegate paints as
#: confidence. Mapped here rather than teaching the delegate a second
#: vocabulary, which would mean two ways to colour one row.
_SEVERITY_CONFIDENCE = {
    "critical": Confidence.HIGH,
    "serious": Confidence.HIGH,
    "moderate": Confidence.MEDIUM,
    "minor": Confidence.LOW,
}

# "Ignore this finding" is not routed through `i18n.translations.t()`: that
# module is another agent's territory while this feature is being built, and
# a made-up key would just show up on screen as the raw key. Plain English
# here, same as the code around it, rather than guessing at a translation
# that would need to be reconciled later anyway.
_IGNORE_FINDING_LABEL = "Ignore this finding"
_SUPPRESSED_NOTE = (
    "Score lowered: part of this finding was suppressed (a phrase, rule or "
    "signal you've already dismissed)."
)
_IGNORE_FINDING_TOOLTIP = (
    "Suppress this exact finding at the fingerprint level, so it does not "
    "reappear on a re-scan. Written to .xanalyze-ignore in the scanned "
    "folder, or to your personal settings when there is no folder to write "
    "into (a web scan)."
)


def _ask_account_later(window) -> None:
    """Ask about the account once the window is on screen.

    Deferred rather than skipped: the header should end up telling the truth,
    it just must not make startup wait for a round trip to do so.
    """
    from PySide6.QtCore import QTimer

    QTimer.singleShot(0, lambda: window._refresh_account_control(refresh=True))


#: "This has not been asked yet", distinct from "the answer is no".
_UNASKED = object()


def _browser_url(source: str) -> str:
    """The address to open for a document.

    A crawled page already is a URL; a file has to become an absolute one,
    because `file://page.html` is not something a browser can resolve.
    """
    if source.startswith(("http://", "https://", "file://")):
        return source
    from pathlib import Path
    return Path(source).resolve().as_uri()


class MainWindow(QMainWindow):
    def __init__(self, palette=None):
        super().__init__()
        self.settings = config.Settings.load()
        self.lang = self.settings.ui_language
        # The xFormat design-system palette in force. Passed in by main.py so
        # the app is styled before any widget exists; resolved here as well so
        # the window is still usable when constructed directly (tests, or a
        # future second window).
        self.palette_tokens = palette or theme.current_palette(self.settings.theme)
        #: The source being examined. What used to be `self.mode` is now
        #: derived from this and from the chosen checks, so downstream code
        #: that asks "which kind of run is this" still gets an answer.
        #: Cached answer to "is an xFormat account connected". `_UNASKED`
        #: rather than None because "not asked yet" and "signed out" are
        #: different states and only one of them is worth a round trip.
        self._account_cache = _UNASKED
        self.source = SOURCE_SITE
        #: The last request that actually ran, kept so a changed question can
        #: be answered from the pages already fetched. See
        #: `AnalysisRequest.reuses_extraction`.
        self._last_request = None
        #: The request whose fetch produced `_cached_pages` / `_cached_files`,
        #: and the documents themselves. Held apart from `_last_request`
        #: because a run can fail or be cancelled after the fetch succeeded.
        self._extraction_request = None
        self._cached_pages = None
        self._cached_files = None
        #: The scope the cached files were extracted under. A different scope
        #: extracts different text, so it invalidates them even though the
        #: source and the target are the same.
        self._cached_scope = None

        self.worker = None  # AnalysisWorker | RepoAnalysisWorker | None
        self._rewrite_worker: RewriteAllWorker | None = None
        # Every QThread this window starts is tracked here until it finishes.
        # Two reasons: a thread whose last Python reference is dropped gets
        # garbage-collected mid-run (which happened when a second "additional
        # analysis" click overwrote the first worker), and closeEvent needs
        # the full set so it can stop them — Qt aborts the process with
        # "QThread: Destroyed while thread is still running" otherwise.
        self._active_workers: list = []
        self.result: AnalysisResult | RepoAnalysisResult | None = None
        #: The audit's own result, kept apart from `self.result` rather than
        #: unioned into it: the two carry different objects, and a single
        #: attribute holding either is a type check at every use site.
        self.audit_result = None
        self.drafts: dict[tuple, str] = {}  # (block_id, start, end) -> replacement text

        self.current_preview_url: str | None = None       # web mode
        self.current_preview_path: str | None = None      # repo mode
        self._pending_highlight_dom_path: str | None = None
        #: The element's own opening tag, used when the selector no longer
        #: matches because the page's own scripts moved things around.
        self._pending_highlight_tag: str = ""
        self._expanded_item: QListWidgetItem | None = None
        self._last_selected_key: tuple | None = None
        self.wide_mode: bool | None = None  # forces first resizeEvent to initialize layout
        self.medium_mode: bool | None = None  # the second, narrower breakpoint; see MEDIUM_BREAKPOINT
        self.repo_ignore_patterns: list[str] = _parse_ignore_text(DEFAULT_IGNORE_PATTERNS)

        # -- MVVM: centralized state and business logic --
        self.app_state = AppState(self)
        self.view_model = MainViewModel(self.app_state, self.settings, self)
        self.view_model.repo_ignore_patterns = self.repo_ignore_patterns

        self.resize(1300, 800)
        icon = ASSETS / "app-icon.png"
        if icon.is_file():
            self.setWindowIcon(QIcon(str(icon)))
        self._build_ui()
        self._retranslate_ui()
        self._wire_app_state()
        self._setup_shortcuts()
        self._update_layout_mode(force=True)
        _ask_account_later(self)

    # ------------------------------------------------------------------ UI

    def _wire_app_state(self) -> None:
        """Connect toolbar combos to AppState and subscribe to changes.

        This is the MVVM wiring: combos write to AppState, AppState
        validates and normalises, then signals flow back to update the UI.
        """
        # -- combos -> AppState --
        self.mode_combo.currentIndexChanged.connect(self._on_mode_to_state)
        self.reader_combo.currentIndexChanged.connect(self._on_reader_to_state)
        self.checks_combo.currentIndexChanged.connect(self._on_checks_to_state)
        self.method_combo.currentIndexChanged.connect(self._on_method_to_state)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_to_state)

        # -- AppState -> UI updates --
        self.app_state.any_changed.connect(self._apply_mode_visibility)
        self.app_state.any_changed.connect(self._sync_source_from_state)

        # -- ViewModel -> UI updates --
        self.view_model.busy_changed.connect(self._on_busy_changed)
        self.view_model.buttons_changed.connect(self._update_repo_buttons_enabled)
        self.view_model.error.connect(self._on_vm_error)
        self.view_model.status_message.connect(self.status_bar.showMessage)
        self.view_model.web_result_ready.connect(self._on_vm_web_result)
        self.view_model.repo_result_ready.connect(self._on_vm_repo_result)
        self.view_model.audit_result_ready.connect(self._on_vm_audit_result)
        self.view_model.rewrite_ready.connect(self._on_rewrite_finished)

    def _setup_shortcuts(self) -> None:
        """Keyboard shortcuts for power users."""
        # Esc = Cancel running analysis
        esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc.activated.connect(self._on_cancel_clicked)
        # Ctrl+K / Cmd+K = Focus URL/path field
        focus_url = QShortcut(QKeySequence("Ctrl+K"), self)
        focus_url.activated.connect(self._focus_target_field)

    def _focus_target_field(self) -> None:
        """Focus the input field for the current source."""
        if self.app_state.source == SOURCE_REPO:
            self.repo_path_edit.setFocus()
        elif self.app_state.source == SOURCE_FILE:
            self.file_path_edit.setFocus()
        else:
            self.url_edit.setFocus()

    def _on_mode_to_state(self, _idx: int) -> None:
        data = self.mode_combo.currentData()
        if data:
            self.app_state.set_source(data)

    def _on_reader_to_state(self, _idx: int) -> None:
        data = self.reader_combo.currentData()
        if data:
            self.app_state.set_readers(self._decode_choice(data, (READER_CODE,)))

    def _on_checks_to_state(self, _idx: int) -> None:
        data = self.checks_combo.currentData()
        if data:
            self.app_state.set_checks(self._decode_choice(data, CHECKS))

    def _on_method_to_state(self, _idx: int) -> None:
        data = self.method_combo.currentData()
        if data:
            self.app_state.set_methods(self._decode_choice(data, (METHOD_LOCAL,)))

    def _on_provider_to_state(self, _idx: int) -> None:
        data = self.provider_combo.currentData()
        if data:
            self.app_state.set_provider(data)

    def _sync_source_from_state(self) -> None:
        """Keep the legacy self.source in sync during the transition."""
        self.source = self.app_state.source

    def _on_busy_changed(self, busy: bool) -> None:
        self.analyze_btn.setEnabled(not busy)
        self.cancel_btn.setEnabled(busy)

    def _on_vm_error(self, message: str) -> None:
        QMessageBox.warning(self, "", message)

    def _on_advanced_toggle(self, checked: bool) -> None:
        """Show or hide the advanced toolbar controls (reader, method, provider)."""
        self.advanced_row.setVisible(checked)
        lang = self.lang
        self.advanced_toggle.setText(
            t("advanced_hide", lang) if checked else t("advanced_show", lang))

    def _show_field_error(self, field: QLineEdit, message: str) -> None:
        """Highlight field and show error in status bar."""
        field.setProperty("class", "field-error")
        from ui import theme as _t
        _t.restyle(field)
        self.status_bar.showMessage(message)

    def _clear_field_error(self, field: QLineEdit) -> None:
        """Clear error highlight when user types."""
        field.setProperty("class", "")
        from ui import theme as _t
        _t.restyle(field)
        self.status_bar.clearMessage()

    def _on_vm_web_result(self, result) -> None:
        """ViewModel finished a web scan - update the UI."""
        self.result = result
        self._populate_flagged_list()
        n_flags = sum(1 for s in result.spans if s.confidence != Confidence.LOW)
        self.status_bar.showMessage(
            t("status_done", self.lang, pages=len(result.pages),
              blocks=len(result.blocks()), flags=n_flags))
        self._update_repo_buttons_enabled()

    def _on_vm_repo_result(self, result) -> None:
        """ViewModel finished a repo scan - update the UI."""
        self.result = result
        self._populate_flagged_list()
        n_flags = sum(1 for s in result.spans if s.confidence != Confidence.LOW)
        self.status_bar.showMessage(
            t("status_done", self.lang, pages=len(result.files),
              blocks=len(result.blocks()), flags=n_flags))
        self._update_repo_buttons_enabled()

    def _on_vm_audit_result(self, result) -> None:
        """ViewModel finished an audit - update the UI."""
        self.audit_result = result
        self._populate_audit_list()
        first = next((d for d in result.documents if not d.error), None)
        if first is not None:
            address = _browser_url(first.source)
            self.current_preview_url = address
            self.site_view.setUrl(QUrl(address))
        self._update_audit_buttons_enabled()
        self.status_bar.showMessage(
            audit_explanations.summary_line(result, self.lang))

    def _on_rewrite_finished(self, drafts: dict) -> None:
        """ViewModel finished bulk rewrite - update drafts and refresh list."""
        for key, text in drafts.items():
            self.drafts[key] = text
        self._populate_flagged_list()

    def _build_brand_header(self) -> QWidget:
        """The mark, the name, and the one line that says what the app does."""
        from PySide6.QtSvgWidgets import QSvgWidget

        bar = QWidget()
        bar.setProperty("class", theme.CLASS_BRAND)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(self.palette_tokens.space_sm)

        mark = ASSETS / ("logo-dark.svg" if theme.resolve_mode(self.settings.theme) == "dark"
                         else "logo-light.svg")
        if mark.is_file():
            self.brand_mark = QSvgWidget(str(mark))
            self.brand_mark.setFixedSize(QSize(22, 22))
            layout.addWidget(self.brand_mark)
        else:
            self.brand_mark = None

        self.brand_name = QLabel("XAnalyze")
        self.brand_name.setProperty("class", theme.CLASS_HEADING)
        layout.addWidget(self.brand_name)

        self.brand_tagline = muted()
        layout.addWidget(self.brand_tagline)
        layout.addStretch(1)

        # Account state belongs where it can be seen. It used to live inside
        # the settings dialog, which meant the one fact that decides whether
        # the AI assessment is available at all was three clicks away and
        # invisible from the window that offers it.
        self.account_label = muted()
        layout.addWidget(self.account_label)
        self.account_btn = QPushButton()
        self.account_btn.clicked.connect(self._on_account_clicked)
        layout.addWidget(self.account_btn)
        # Drawn from what is known, which at build time is nothing. The real
        # answer is asked once the window exists; see `_ask_account_later`.
        self._refresh_account_control(ask=False)
        return bar

    # ------------------------------------------------------------- account

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

    #: Which Lucide icon stands for which action. Kept next to the row it
    #: draws rather than in `ui/icons.py`: the file knows how to render an
    #: icon, this knows what the buttons mean.
    _ACTION_ICONS = (
        ("fix_unicode_btn", "eraser"),
        ("generate_list_btn", "list"),
        ("auto_replace_btn", "replace"),
        ("fix_on_disk_btn", "file-pen"),
        ("undo_fix_btn", "undo-2"),
        ("download_btn", "download"),
    )

    def _apply_action_icons(self) -> None:
        """Draw the action row as icons in the current theme's ink.

        Re-run on every theme change for the same reason `_repaint_brand` is:
        the icons are rasterised in one colour, and the colour that reads on
        a light sheet disappears on a dark one.
        """
        from ui import icons as icon_set

        if not icon_set.available():
            return
        ratio = self.devicePixelRatioF() or 1.0
        size = icon_set.DEFAULT_SIZE
        for attribute, name in self._ACTION_ICONS:
            button = getattr(self, attribute, None)
            if button is None:
                continue
            drawn = icon_set.icon(name, self.palette_tokens.text, size, ratio)
            if drawn is None:
                continue
            button.setIcon(drawn)
            button.setIconSize(QSize(size, size))
            # Cleared only now: until an icon is in hand, the label is the
            # only thing identifying the button.
            button.setText("")

    def _repaint_brand(self) -> None:
        """Swap the mark when the theme changes: the light logo on a dark
        canvas is invisible, which is the whole reason two files exist."""
        if getattr(self, "brand_mark", None) is None:
            return
        mark = ASSETS / ("logo-dark.svg"
                         if theme.resolve_mode(self.settings.theme) == "dark"
                         else "logo-light.svg")
        if mark.is_file():
            self.brand_mark.load(str(mark))

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        gap = self.palette_tokens.space_md
        root.setContentsMargins(gap, gap, gap, gap)
        root.setSpacing(gap)

        # A header strip with the mark and the product name. Not decoration:
        # this is one application in a family, and the thing that says so at a
        # glance is the mark, in the same indigo, in the same place as the web
        # app puts it.
        root.addWidget(self._build_brand_header())

        # The controls live on their own surface rather than floating on the
        # page canvas — the same "monolithic card on a warm canvas" the web
        # app uses to separate chrome from content.
        self.toolbar = QWidget()
        self.toolbar.setProperty("class", theme.CLASS_TOOLBAR)
        self.toolbar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # The toolbar carries the source, its fields, three choices, the
        # detector and three buttons. In a row that cannot wrap, a narrow window
        # answers that by clipping labels to nothing; this answers it by using a
        # second line.
        controls = FlowLayout(self.toolbar, margin=gap,
                              spacing=self.palette_tokens.space_sm)

        self.mode_label = QLabel()
        self.mode_combo = QComboBox()
        self.mode_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.mode_combo.setMinimumContentsLength(14)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        # --- web-mode controls ---
        web_controls = QWidget()
        web_layout = QHBoxLayout(web_controls)
        web_layout.setContentsMargins(0, 0, 0, 0)
        self.url_label = QLabel()
        self.url_edit = QLineEdit()
        self.url_edit.textChanged.connect(lambda: self._clear_field_error(self.url_edit))
        self.depth_label = QLabel()
        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(0, 5)
        self.depth_spin.setValue(self.settings.crawl_depth)
        for w in (self.url_label, self.url_edit, self.depth_label, self.depth_spin):
            web_layout.addWidget(w)
        web_layout.setStretch(1, 3)
        self.url_error = muted()
        self.url_error.setProperty("class", "field-error")
        self.url_error.setVisible(False)

        # --- repo-mode controls ---
        repo_controls = QWidget()
        repo_layout = QHBoxLayout(repo_controls)
        repo_layout.setContentsMargins(0, 0, 0, 0)
        self.repo_path_edit = QLineEdit()
        self.repo_path_edit.textChanged.connect(lambda: self._clear_field_error(self.repo_path_edit))
        self.browse_btn = QPushButton()
        self.browse_btn.clicked.connect(self._on_browse_clicked)
        self.exclusions_btn = QPushButton()
        self.exclusions_btn.clicked.connect(self._on_exclusions_clicked)
        self.scope_label = QLabel()
        self.scope_combo = QComboBox()
        self.scope_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.scope_combo.setMinimumContentsLength(12)
        self.scope_combo.currentIndexChanged.connect(self._on_scope_changed)
        for w in (self.repo_path_edit, self.browse_btn, self.exclusions_btn,
                  self.scope_label, self.scope_combo):
            repo_layout.addWidget(w)
        repo_layout.setStretch(0, 3)
        self.repo_error = muted()
        self.repo_error.setProperty("class", "field-error")
        self.repo_error.setVisible(False)

        # --- single-file controls ---
        file_controls = QWidget()
        file_layout = QHBoxLayout(file_controls)
        file_layout.setContentsMargins(0, 0, 0, 0)
        self.file_path_edit = QLineEdit()
        self.file_path_edit.textChanged.connect(lambda: self._clear_field_error(self.file_path_edit))
        self.file_browse_btn = QPushButton()
        self.file_browse_btn.clicked.connect(self._on_browse_file_clicked)
        file_layout.addWidget(self.file_path_edit)
        file_layout.addWidget(self.file_browse_btn)
        file_layout.setStretch(0, 3)
        self.file_error = muted()
        self.file_error.setProperty("class", "field-error")
        self.file_error.setVisible(False)

        self.source_controls_stack = QStackedWidget()
        self.source_controls_stack.addWidget(web_controls)   # index 0
        self.source_controls_stack.addWidget(repo_controls)  # index 1
        self.source_controls_stack.addWidget(file_controls)  # index 2

        # Which account reads the text, not which detector class to build.
        # The dropdown used to list backends by name, which made the method
        # combo beside it decorative: the backend carried the decision, so
        # "AI" with an offline backend selected ran the offline engine and
        # said nothing. The method decides *what runs* now, and this decides
        # *who pays* - see `_detector_for_request`.
        self.provider_label = QLabel()
        self.provider_combo = QComboBox()
        # Provider labels can be long ("Claude Code session"). Without this,
        # the combo's minimum size hint is set to fit its longest item, which
        # alone can keep the whole window from ever shrinking below ~1300px
        # and would silently defeat the narrow-window layout below.
        self.provider_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.provider_combo.setMinimumContentsLength(14)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        self._populate_providers()

        # Loading every page in a real browser costs seconds per page and is
        # the only way to see what JavaScript rendered, so it is the user's
        # call rather than a default. Off by default: a first audit should be
        # fast, and the static pass already reports most of what is wrong.
        # --- the three choices that used to be one -------------------------
        #
        # Reading, question and judge are independent of each other and of the
        # source. Kept as three combos rather than one list of combinations:
        # the combinations multiply (3 x 3 x 3), and the point of separating
        # them is that the user changes one without restating the other two.
        self.reader_label = QLabel()
        self.reader_combo = QComboBox()
        self.checks_label = QLabel()
        self.checks_combo = QComboBox()
        self.method_label = QLabel()
        self.method_combo = QComboBox()
        for combo in (self.reader_combo, self.checks_combo, self.method_combo):
            combo.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(12)
            combo.currentIndexChanged.connect(self._on_choice_changed)

        # --- advanced controls (hidden by default) ---
        self.advanced_toggle = QPushButton()
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setChecked(False)
        self.advanced_toggle.clicked.connect(self._on_advanced_toggle)
        self.advanced_toggle.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.analyze_btn = QPushButton()
        self.analyze_btn.setDefault(True)
        self.analyze_btn.clicked.connect(self._on_analyze_clicked)
        self.cancel_btn = QPushButton()
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        self.cancel_btn.setEnabled(False)
        self.settings_btn = QPushButton()
        self.settings_btn.clicked.connect(self._on_settings_clicked)

        # Toolbar keeps only what changes per scan. Language, API keys,
        # provider and endpoint mapping live in the Settings dialog, which
        # is what stops this row from growing unusable.
        controls.addWidget(self.mode_label)
        controls.addWidget(self.mode_combo)
        self.source_controls_stack.setMinimumWidth(200)
        self.source_controls_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        controls.addWidget(self.source_controls_stack)
        # Checks is always visible - it's the primary question
        controls.addWidget(self.checks_label)
        controls.addWidget(self.checks_combo)
        # Advanced toggle shows/hides reader, method, provider
        controls.addWidget(self.advanced_toggle)
        controls.addWidget(self.analyze_btn)
        controls.addWidget(self.cancel_btn)
        controls.addWidget(self.settings_btn)
        self.analyze_btn.setProperty("class", theme.CLASS_PRIMARY)
        root.addWidget(self.toolbar)

        # Advanced row (hidden by default) - below the main toolbar
        self.advanced_row = QWidget()
        self.advanced_row.setProperty("class", theme.CLASS_TOOLBAR)
        self.advanced_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        adv_layout = QHBoxLayout(self.advanced_row)
        adv_layout.setContentsMargins(gap, 0, gap, gap)
        adv_layout.setSpacing(self.palette_tokens.space_sm)
        for w in (self.reader_label, self.reader_combo,
                  self.method_label, self.method_combo,
                  self.provider_label, self.provider_combo):
            adv_layout.addWidget(w)
        adv_layout.addStretch(1)
        self.advanced_row.setVisible(False)
        root.addWidget(self.advanced_row)

        # --- three-column body -------------------------------------------------
        self.columns_splitter = QSplitter(Qt.Orientation.Horizontal)
        # A gap between the zones, not a seam: panels that touch read as one
        # wide panel with lines drawn in it, which is exactly the flat-sheet
        # look the surfaces exist to avoid.
        self.columns_splitter.setHandleWidth(gap)
        self.columns_splitter.setChildrenCollapsible(False)
        root.addWidget(self.columns_splitter, stretch=1)

        # Column 1: graphical copy of the site OR the raw source file being
        # analyzed, depending on mode.
        # Each column is a zone with its own surface and its own titled head,
        # the way the web app separates one part of a page from another. A Qt
        # window that paints three regions of one flat sheet reads as a
        # different product, however correct its colours are.
        self.col1, col1_layout, self.col1_header = panel()
        col1_layout.setContentsMargins(10, 10, 10, 10)

        self.col1_stack = QStackedWidget()
        self.site_view = QWebEngineView()
        self.site_view.loadFinished.connect(self._on_preview_loaded)
        # Chromium paints white until the page has something to draw, which in
        # a dark theme reads as a broken pane for the second or two a real site
        # takes to arrive.
        self.site_view.page().setBackgroundColor(QColor(self.palette_tokens.page_bg))
        self.col1_stack.addWidget(self.site_view)  # index 0: web

        self.code_view = QPlainTextEdit()
        self.code_view.setReadOnly(True)
        mono = self.code_view.font()
        # The design system's mono face, with Qt resolving its own fallback
        # when that family isn't installed.
        mono.setFamily(self.palette_tokens.font_mono)
        self.code_view.setFont(mono)
        self.col1_stack.addWidget(self.code_view)  # index 1: repo

        # The width switcher, above the preview rather than beside it: the
        # audit now runs at three widths (see `audit/responsive.py`), and a
        # finding labelled "found at mobile only" is not checkable in a
        # preview that is always desktop-shaped. These buttons constrain the
        # preview itself, so the reader sees the layout the finding came from.
        self.breakpoint_row = QWidget()
        breakpoint_layout = QHBoxLayout(self.breakpoint_row)
        breakpoint_layout.setContentsMargins(0, 0, 0, 6)
        breakpoint_layout.setSpacing(self.palette_tokens.space_sm)
        self.breakpoint_buttons = {}
        #: Which width the preview is pinned to, or None for the full column.
        self._preview_width_name = None
        for name, width, _height in responsive_breakpoints():
            button = QPushButton()
            button.setCheckable(True)
            button.clicked.connect(
                lambda _checked=False, chosen=name: self._on_breakpoint_clicked(chosen))
            breakpoint_layout.addWidget(button)
            self.breakpoint_buttons[name] = (button, width)
        breakpoint_layout.addStretch(1)
        col1_layout.addWidget(self.breakpoint_row)

        col1_layout.addWidget(self.col1_stack, stretch=1)
        self.columns_splitter.addWidget(self.col1)

        # Column 2: the list of flagged passages (+ repo-mode bulk actions).
        col2, col2_layout, self.flagged_header = panel()
        col2_layout.setContentsMargins(1, 0, 1, 1)

        self.flagged_list = QListWidget()
        self.flagged_list.setMouseTracking(True)  # so the delegate sees hover
        self.finding_delegate = FindingDelegate(self.palette_tokens, self.flagged_list)
        self.flagged_list.setItemDelegate(self.finding_delegate)
        self.flagged_list.itemClicked.connect(self._on_flagged_item_clicked)

        # An empty findings list is ambiguous — clean, not-yet-scanned and
        # "the crawler got nothing" all look identical as a blank list — so
        # the list is one page of a stack and an explanation is the other.
        self.empty_state = EmptyState()
        self.results_stack = QStackedWidget()
        self.results_stack.addWidget(self.flagged_list)   # index 0
        self.results_stack.addWidget(self.empty_state)    # index 1
        col2_layout.addWidget(self.results_stack, stretch=1)

        # Bulk actions. The unicode fix is offline and free, so it's offered
        # in both modes; the two LLM-backed buttons are repo-only.
        self.bulk_actions_row = QWidget()
        # Up to six buttons here, and which ones depends on the question asked.
        # A flow keeps their labels readable at any width instead of clipping
        # them all equally.
        bulk_layout = FlowLayout(self.bulk_actions_row,
                                 spacing=self.palette_tokens.space_sm)
        bulk_layout.setContentsMargins(12, 10, 12, 12)
        self.fix_unicode_btn = QPushButton()
        self.fix_unicode_btn.clicked.connect(self._on_fix_unicode_clicked)
        self.generate_list_btn = QPushButton()
        self.generate_list_btn.clicked.connect(self._on_generate_list_clicked)
        self.auto_replace_btn = QPushButton()
        self.auto_replace_btn.clicked.connect(self._on_auto_replace_clicked)
        # Writing an audit correction back into the file, and taking it back.
        # Both live next to each other on purpose: an action that edits
        # someone's source is only comfortable to press when the way out is
        # visible at the same moment.
        self.fix_on_disk_btn = QPushButton()
        self.fix_on_disk_btn.clicked.connect(self._on_fix_on_disk_clicked)
        self.undo_fix_btn = QPushButton()
        self.undo_fix_btn.clicked.connect(self._on_undo_fix_clicked)
        # One entry point for two different documents. They stay two
        # documents - an agent briefing (`cli._write_report`'s markdown/JSON)
        # and the branded PDF/HTML a person reads - because they are read by
        # different readers; what was merged is the *button*, since two
        # exports side by side made the row ask a question ("which of these
        # two is the report?") before the user had decided to export at all.
        self.download_btn = QPushButton()
        self.download_btn.clicked.connect(self._on_download_clicked)
        for b in (self.fix_unicode_btn, self.generate_list_btn, self.auto_replace_btn,
                  self.fix_on_disk_btn, self.undo_fix_btn, self.download_btn):
            bulk_layout.addWidget(b)
        col2_layout.addWidget(divider())
        col2_layout.addWidget(self.bulk_actions_row)
        # Kept as an alias so the repo-only visibility logic reads clearly.
        self.repo_actions_row = self.bulk_actions_row

        self.columns_splitter.addWidget(col2)

        # Column 3 (wide layout only): input box + actions for the selected passage.
        self.col3 = QWidget()
        self.detail_layout = QVBoxLayout(self.col3)
        self.detail_layout.setContentsMargins(0, 0, 0, 0)
        self.detail_layout.setSpacing(0)
        self.columns_splitter.addWidget(self.col3)

        self.columns_splitter.setSizes([450, 380, 380])

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self._apply_mode_visibility()

    def _populate_providers(self) -> None:
        """Offer every account, including ones not connected yet.

        Not filtered down to what is currently usable: the method combo
        already refuses the AI pass when nothing can pay for it, and a list
        that silently loses an entry is a worse answer than one whose entry
        explains, when picked, what it needs.
        """
        self.provider_combo.blockSignals(True)
        self.provider_combo.clear()
        for name in PROVIDER_ORDER:
            self.provider_combo.addItem(t(f"provider_{name}", self.lang), userData=name)
        idx = self.provider_combo.findData(self.settings.llm_provider)
        self.provider_combo.setCurrentIndex(max(idx, 0))
        self.provider_combo.blockSignals(False)

    def _on_provider_changed(self, _idx: int = 0) -> None:
        """The toolbar and the Settings dialog change one setting, not two.

        Writing it straight through means a provider picked here is the one
        `ai status`, the rewrite calls and the Settings dialog all report -
        two places holding two answers to "whose account pays" is how the
        window came to disagree with the CLI in the first place.
        """
        chosen = self.provider_combo.currentData()
        if chosen and chosen != self.settings.llm_provider:
            self.settings.llm_provider = chosen
            self.settings.save()
            self._account_cache = _UNASKED
            self._retranslate_choices()

    def _retranslate_ui(self) -> None:
        lang = self.lang
        self.setWindowTitle(t("app_title", lang))
        self.mode_label.setText(t("mode_label", lang))
        self.brand_tagline.setText(t("app_tagline", lang))
        current_mode_data = self.mode_combo.currentData() if self.mode_combo.count() else None
        self.mode_combo.blockSignals(True)
        self.mode_combo.clear()
        # One entry per source, not per source-and-question pair: "site audit"
        # and "web page" were the same site asked two questions, and offering
        # them as separate sources meant choosing the source twice.
        self.mode_combo.addItem(t("source_site", lang), userData=SOURCE_SITE)
        self.mode_combo.addItem(t("source_repo", lang), userData=SOURCE_REPO)
        self.mode_combo.addItem(t("source_file", lang), userData=SOURCE_FILE)
        idx = self.mode_combo.findData(current_mode_data or self.source)
        self.mode_combo.setCurrentIndex(max(idx, 0))
        self.mode_combo.blockSignals(False)
        self._retranslate_choices()
        self._refresh_account_control(ask=False)

        self.url_label.setText(t("url_label", lang))
        self.url_label.setToolTip(t("url_label_full", lang))
        self.url_edit.setPlaceholderText(t("url_placeholder", lang))
        self.depth_label.setText(t("depth_label", lang))
        self.depth_label.setToolTip(t("depth_label_full", lang))
        self.repo_path_edit.setPlaceholderText(t("repo_path_placeholder", lang))
        self.browse_btn.setText(t("browse_button", lang))
        self.exclusions_btn.setText(t("exclusions_button", lang))
        self.exclusions_btn.setToolTip(t("exclusions_button_full", lang))

        self.scope_label.setText(t("scope_label", lang))
        self.scope_label.setToolTip(t("scope_label_full", lang))
        current_scope = self.scope_combo.currentData() if self.scope_combo.count() else None
        self.scope_combo.blockSignals(True)
        self.scope_combo.clear()
        for value in (SCOPE_CONTENT, SCOPE_TECHNICAL, SCOPE_BOTH):
            self.scope_combo.addItem(t(f"scope_{value}", lang), userData=value)
            self.scope_combo.setItemData(
                self.scope_combo.count() - 1,
                t(f"scope_{value}_full", lang),
                Qt.ItemDataRole.ToolTipRole,
            )
        idx = self.scope_combo.findData(current_scope or self.settings.repo_scope)
        self.scope_combo.setCurrentIndex(max(idx, 0))
        self.scope_combo.blockSignals(False)
        self.scope_combo.setToolTip(t(f"scope_{self._repo_scope()}_full", lang))

        for name, (button, width) in self.breakpoint_buttons.items():
            label = t(f"breakpoint_{name}", lang)
            button.setText(label)
            button.setToolTip(t("breakpoint_tooltip", lang,
                                name=label, width=width))
        # Refilled, not just relabelled: the entries themselves are words.
        self._populate_providers()
        self.provider_label.setText(t("provider_label", lang))
        self.provider_label.setToolTip(t("provider_label_full", lang))
        self.provider_combo.setToolTip(t("provider_label_full", lang))
        self.file_path_edit.setPlaceholderText(t("file_path_placeholder", lang))
        self.file_browse_btn.setText(t("browse_button", lang))
        self.reader_label.setText(t("reader_label", lang))
        self.reader_label.setToolTip(t("reader_label_full", lang))
        self.checks_label.setText(t("checks_label", lang))
        self.checks_label.setToolTip(t("checks_label_full", lang))
        self.method_label.setText(t("method_label", lang))
        self.method_label.setToolTip(t("method_label_full", lang))
        self.analyze_btn.setText(t("analyze_button", lang))
        self.cancel_btn.setText(t("cancel_button", lang))
        self.settings_btn.setText(t("settings_button", lang))
        self.advanced_toggle.setText(
            t("advanced_hide", lang) if self.advanced_toggle.isChecked()
            else t("advanced_show", lang))
        self.flagged_header.setText(t("flagged_list_header", lang))
        self.col1_header.setText(t("site_preview_header", lang))
        # The action row is icons, and the words move into the tooltips: six
        # buttons of six different widths read as a heap rather than as a row,
        # and their labels are long in every language this app speaks. The
        # label is still set - and then cleared by `_apply_action_icons` only
        # if an icon was actually found - so a build without the icon files
        # degrades to the readable version instead of to six blank squares.
        for button, key, tip in (
            (self.fix_unicode_btn, "fix_unicode_button", "fix_unicode_tooltip"),
            (self.generate_list_btn, "generate_list_button", ""),
            (self.auto_replace_btn, "auto_replace_button", ""),
            (self.fix_on_disk_btn, "fix_on_disk_button", "fix_on_disk_tooltip"),
            (self.undo_fix_btn, "undo_fix_button", "undo_fix_tooltip"),
            (self.download_btn, "download_button", "download_tooltip"),
        ):
            label = t(key, lang)
            button.setText(label)
            # Tooltip: the long explanation where there is one, the label
            # itself where there is not - an icon with no tooltip at all is
            # a button that cannot be identified.
            button.setToolTip(f"{label} - {t(tip, lang)}" if tip else label)
        self._apply_action_icons()
        self.status_bar.showMessage(t("status_idle", lang))
        self._reset_detail_panel()

    def _on_breakpoint_clicked(self, chosen: str) -> None:
        """Show the preview at one width, or back at full width.

        Clicking the pressed button again releases it: the widths are a
        temporary way of looking at the page, not a mode to get stuck in.
        """
        # Decided from what was selected before, not from the button's own
        # checked state: a checkable button has already toggled itself by the
        # time this runs when a person clicks it, and has not when the same
        # action is invoked from anywhere else. Reading the remembered choice
        # makes both paths agree.
        release = self._preview_width_name == chosen
        self._preview_width_name = None if release else chosen
        for name, (other, _width) in self.breakpoint_buttons.items():
            other.setChecked(name == self._preview_width_name)
        width = self.breakpoint_buttons[chosen][1]
        self._apply_preview_width(None if release else width)

    def _apply_preview_width(self, width) -> None:
        """Constrain the preview to simulate a viewport width.

        Uses resize() like the audit driver does, not setMaximumWidth:
        the browser's CSS media queries respond to the actual widget size,
        and setMaximumWidth only constrains the container without changing
        the viewport that window.innerWidth reads.
        """
        if width is None:
            self.site_view.setMaximumWidth(16777215)  # Qt's own "no maximum"
            self.site_view.setMinimumWidth(0)
        else:
            # Find the matching height for this breakpoint
            height = 900  # default
            for name, bp_width, bp_height in responsive_breakpoints():
                if bp_width == width:
                    height = bp_height
                    break
            self.site_view.setMinimumWidth(int(width))
            self.site_view.setMaximumWidth(int(width))
            self.site_view.resize(int(width), int(height))

    def _repaint_preview_background(self) -> None:
        self.site_view.page().setBackgroundColor(QColor(self.palette_tokens.page_bg))

    def apply_palette(self, palette) -> None:
        """Adopt a new design-system palette at runtime.

        Called when the theme is switched in Settings. The style sheet is
        applied application-wide by `theme.apply_theme`; what has to happen
        here is everything QSS cannot reach — the delegate that paints the
        findings rows, and the monospaced face on the code preview.
        """
        self.palette_tokens = palette
        self.finding_delegate.set_palette(palette)
        self._repaint_preview_background()
        self._repaint_brand()
        self._apply_action_icons()
        mono = self.code_view.font()
        mono.setFamily(palette.font_mono)
        self.code_view.setFont(mono)
        for widget in (self.toolbar, self.empty_state):
            restyle(widget)
        self.flagged_list.viewport().update()

    def _on_settings_clicked(self) -> None:
        from ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self.settings, self.lang, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # Language may have changed in the dialog; re-apply everything.
            self.lang = self.settings.ui_language
            self._retranslate_ui()
            self._populate_flagged_list()

    # ------------------------------------------------------- responsive layout

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._update_layout_mode()

    # ------------------------------------------------------ thread lifecycle

    def _track_worker(self, worker) -> None:
        """Hold a reference until the thread finishes, so it can't be
        garbage-collected mid-run, and so closeEvent can find it."""
        self._active_workers.append(worker)
        worker.finished.connect(lambda: self._untrack_worker(worker))

    def _untrack_worker(self, worker) -> None:
        if worker in self._active_workers:
            self._active_workers.remove(worker)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        self.view_model.shutdown()
        for worker in list(self._active_workers):
            if hasattr(worker, "cancel"):
                worker.cancel()
        for worker in list(self._active_workers):
            if worker.isRunning():
                worker.wait(5000)
        self._persist_settings()
        super().closeEvent(event)

    def _persist_settings(self) -> None:
        self.settings.ui_language = self.lang
        self.settings.crawl_depth = self.depth_spin.value()
        self.settings.repo_scope = self._repo_scope()
        # The method, not a detector name: what to run is the user's choice,
        # and which class implements it is derived from it (see
        # `_detector_for_request`).
        method = self.method_combo.currentData()
        if method:
            self.settings.default_method = method
        provider = self.provider_combo.currentData()
        if provider:
            self.settings.llm_provider = provider
        self.settings.save()

    def _update_layout_mode(self, force: bool = False) -> None:
        wide = self.width() >= WIDE_BREAKPOINT
        medium = self.width() >= MEDIUM_BREAKPOINT
        if not force and wide == self.wide_mode and medium == self.medium_mode:
            return
        self.wide_mode = wide
        self.medium_mode = medium
        self.col3.setVisible(wide)
        # The preview column folds only once the detail column already has -
        # collapsing both together is the jump from three columns to one that
        # this second breakpoint exists to remove.
        self.col1.setVisible(medium)
        self._collapse_inline_detail()
        self._reset_detail_panel()

    # --------------------------------------------------------------- events

    @property
    def mode(self) -> str:
        """The kind of run, derived rather than chosen.

        Everything downstream - which preview to show, which buttons write to
        disk, how a clicked row is dispatched - was written against these four
        names, and they are still the right names for it. What changed is that
        the user no longer picks one: the source and the question together say
        which it is.
        """
        if self.source == SOURCE_REPO:
            return MODE_REPO
        if self.source == SOURCE_FILE:
            return MODE_FILE
        return MODE_AUDIT if self._chosen_checks() == (CHECK_ACCESSIBILITY,) else MODE_WEB

    def _text_row_kind(self) -> str:
        """How a copy finding's row is tagged, independently of the mode.

        A run over a site that asks both questions is `MODE_AUDIT` by the rule
        above, but its copy findings are still copy findings and must not be
        dispatched as audit issues.
        """
        return MODE_REPO if self.source == SOURCE_REPO else MODE_WEB

    @staticmethod
    def choice_key(values) -> str:
        """The combo's stored value for a set of choices.

        A string, not the tuple itself: Qt carries item data through QVariant,
        which turns a tuple into a list, and `findData` then never matches what
        was stored - so restoring the previous choice silently fell back to the
        first item every time the source changed.
        """
        return "+".join(values)

    @staticmethod
    def _decode_choice(data, fallback) -> tuple:
        if not data:
            return fallback
        if isinstance(data, str):
            return tuple(part for part in data.split("+") if part)
        return tuple(data)

    def _chosen_checks(self) -> tuple:
        return self._decode_choice(self.checks_combo.currentData(), CHECKS)

    def _chosen_readers(self) -> tuple:
        return self._decode_choice(self.reader_combo.currentData(), (READER_CODE,))

    def _chosen_methods(self) -> tuple:
        return self._decode_choice(self.method_combo.currentData(), (METHOD_LOCAL,))

    def _ai_available(self) -> bool:
        """Is there anything to pay for an AI pass with?

        Asked of the account state rather than of the provider combo: a key in
        settings, a signed-in xFormat subscription and a Claude Code session
        are three different answers to one question, and the window should not
        offer the pass when all three are absent.
        """
        try:
            import rewriter
            from llm.base import LLMUnavailable

            provider = rewriter.build_provider(self.settings, allow_auto=True)
            try:
                return bool(provider.auth_status().signed_in)
            except LLMUnavailable:
                return False
        except Exception:  # noqa: BLE001 - absence is an answer, not an error
            return False

    def current_request(self) -> AnalysisRequest:
        """What the four controls currently describe, made runnable."""
        return AnalysisRequest(
            source=self.source,
            target=self._current_target(),
            depth=self.depth_spin.value(),
            readers=self._chosen_readers(),
            checks=self._chosen_checks(),
            methods=self._chosen_methods(),
            ai_available=self._ai_available(),
        ).normalised()

    def _current_target(self) -> str:
        if self.source == SOURCE_REPO:
            return self.repo_path_edit.text().strip()
        if self.source == SOURCE_FILE:
            return self.file_path_edit.text().strip()
        return self.url_edit.text().strip()

    def _reusable_pages(self):
        """Pages an earlier run already fetched for this exact target, or None.

        This is the payoff of separating the axes: changing the question or the
        judge used to mean crawling the site again, which is the slowest
        possible way to answer a question about pages already on this machine.
        """
        request = self.current_request()
        if self._cached_pages and request.reuses_extraction(self._extraction_request):
            return self._cached_pages
        return None

    def _reusable_files(self):
        """The repository counterpart, with one extra condition.

        The scope decides what is extracted at all - copy, comments, or both -
        so a changed scope is a changed extraction and cannot be reused.
        """
        request = self.current_request()
        if (self._cached_files
                and self._cached_scope == self._repo_scope()
                and request.reuses_extraction(self._extraction_request)):
            return self._cached_files
        return None

    def _remember_extraction(self, request, *, pages=None, files=None,
                             scope=None) -> None:
        self._extraction_request = request
        if pages is not None:
            self._cached_pages = pages
        if files is not None:
            self._cached_files = files
            self._cached_scope = scope

    def _forget_extraction(self) -> None:
        """Drop the cache. Called when the source or the target changes: those
        are the two things the cached documents *are*."""
        self._extraction_request = None
        self._cached_pages = None
        self._cached_files = None
        self._cached_scope = None

    def _on_choice_changed(self, _idx: int = 0) -> None:
        """A changed question does not invalidate the fetched pages.

        This is the whole reason the axes were separated: switching from
        accessibility to copy, or from the offline engine to a model, used to
        mean crawling the site again. Only the source and the target clear the
        result now.
        """
        self._apply_mode_visibility()

    def _on_mode_changed(self, _idx: int) -> None:
        self.source = self.mode_combo.currentData() or SOURCE_SITE
        self._forget_extraction()
        self._retranslate_choices()
        self._apply_mode_visibility()
        # Switching source invalidates whatever was scanned before.
        self.result = None
        self.audit_result = None
        self.flagged_list.clear()
        self._expanded_item = None
        self._reset_detail_panel()
        self.status_bar.showMessage(t("status_idle", self.lang))

    def _retranslate_choices(self) -> None:
        """Fill the three choice combos for the source in force.

        Rebuilt on every source change rather than filled once and disabled,
        because what is *possible* changes with the source: a repository has
        no rendered form, so offering "in a browser" greyed out would be a
        control that exists only to be refused.
        """
        lang = self.lang
        readers = available_readers(self.source)
        options = [(t("reader_code", lang), self.choice_key((READER_CODE,)))]
        if READER_BROWSER in readers:
            options.append((t("reader_browser", lang), self.choice_key((READER_BROWSER,))))
            options.append((t("reader_both", lang), self.choice_key((READER_CODE, READER_BROWSER))))
        self._fill_combo(self.reader_combo, options)
        self.reader_combo.setEnabled(len(options) > 1)
        self.reader_combo.setToolTip(
            t("reader_label_full", lang) if len(options) > 1
            else t("reader_browser_unavailable", lang))

        # Both by default: one pass over the fetched pages answers both
        # questions, and a first run that silently examined only half of what
        # the tool checks is how a report gets trusted for the wrong reason.
        self._fill_combo(self.checks_combo, [
            (t("checks_both", lang), self.choice_key((CHECK_ACCESSIBILITY, CHECK_AI_PATTERNS))),
            (t("check_accessibility", lang), self.choice_key((CHECK_ACCESSIBILITY,))),
            (t("check_ai_patterns", lang), self.choice_key((CHECK_AI_PATTERNS,))),
        ])

        ai_ready = self._ai_available()
        method_options = [(t("method_local", lang), self.choice_key((METHOD_LOCAL,)))]
        if ai_ready:
            method_options.append((t("method_ai", lang), self.choice_key((METHOD_AI,))))
            method_options.append((t("method_both", lang), self.choice_key((METHOD_LOCAL, METHOD_AI))))
        # First fill of the session restores the stored method; every later
        # one keeps whatever is selected, which is what `_fill_combo` does on
        # its own. Split like this because the two cases are different
        # questions: "what did this user choose last time" and "is the
        # current choice still on offer".
        first_fill = self.method_combo.currentData() is None
        self._fill_combo(self.method_combo, method_options)
        if first_fill:
            stored = self.method_combo.findData(self.settings.default_method)
            if stored >= 0:
                self.method_combo.setCurrentIndex(stored)
        self.method_combo.setEnabled(ai_ready)
        self.method_combo.setToolTip(
            t("method_label_full", lang) if ai_ready
            else t("method_ai_unavailable", lang))

    @staticmethod
    def _fill_combo(combo, options) -> None:
        """Refill a combo, keeping the current choice if it is still offered."""
        previous = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        for label, value in options:
            combo.addItem(label, userData=value)
        index = combo.findData(previous) if previous is not None else -1
        combo.setCurrentIndex(max(index, 0))
        combo.blockSignals(False)

    def _apply_mode_visibility(self) -> None:
        is_repo = self.source == SOURCE_REPO
        is_file = self.source == SOURCE_FILE
        checks = self._chosen_checks()
        # What the run will actually look for, which is now a separate
        # question from where it looks.
        wants_copy = CHECK_AI_PATTERNS in checks
        wants_audit = CHECK_ACCESSIBILITY in checks
        is_audit = wants_audit
        # Auditing a site takes a URL and a depth, exactly like the web scan,
        # so it reuses those fields rather than growing a second pair beside
        # them. Auditing one file needs a path and nothing else.
        self.source_controls_stack.setCurrentIndex(
            2 if is_file else (1 if is_repo else 0))
        # A single file is previewed as a rendered page, not as source: it is
        # a page, and its markup is what the third column already shows.
        self.col1_stack.setCurrentIndex(1 if is_repo else 0)
        # The width switcher belongs to the rendered preview. A repository is
        # previewed as source, which has no layout to look at narrow.
        self.breakpoint_row.setVisible(not is_repo)
        # The detector belongs to the copy pass, so it follows the question
        # rather than the source. It used to be hidden whenever an audit was
        # selected, which meant that asking both questions at once left no way
        # to say which engine judged the copy.
        # ... and only when a model is actually going to read anything:
        # whose account pays is not a question an offline-only run has.
        wants_model = METHOD_AI in self._chosen_methods()
        self.provider_label.setVisible(wants_copy and wants_model)
        self.provider_combo.setVisible(wants_copy and wants_model)
        # The row is shared, but the two halves never appear together: three
        # buttons rewrite prose, three act on an audit, and offering both at
        # once would mean six buttons of which half do nothing.
        self.fix_unicode_btn.setVisible(wants_copy)
        self.fix_on_disk_btn.setVisible(wants_audit)
        self.undo_fix_btn.setVisible(wants_audit)
        self.download_btn.setVisible(wants_copy or wants_audit)
        # The row itself is always shown — the unicode fix works in both
        # modes — but the two file-writing buttons only apply to a repo.
        self.generate_list_btn.setVisible(is_repo and wants_copy)
        self.auto_replace_btn.setVisible(is_repo and wants_copy)
        self._update_repo_buttons_enabled()

    def _update_repo_buttons_enabled(self) -> None:
        has_flags = bool(
            self.result and self.mode == MODE_REPO
            and any(s.confidence != Confidence.LOW for s in self.result.spans)
        )
        self.generate_list_btn.setEnabled(has_flags)
        self.auto_replace_btn.setEnabled(has_flags)
        self.fix_unicode_btn.setEnabled(bool(self._unicode_spans()))
        self._update_audit_buttons_enabled()

    def _update_audit_buttons_enabled(self) -> None:
        """A button that writes to disk is only offered when it has something
        to write, and only for a file it can actually open."""
        from audit import fixer

        documents = self.audit_result.documents if self.audit_result else []
        local = [d for d in documents
                 if not d.source.startswith(("http://", "https://"))]
        writable = bool(local and any(
            issue.fix_snippet for d in local for issue in d.issues))
        self.fix_on_disk_btn.setEnabled(writable)
        self.undo_fix_btn.setEnabled(bool(fixer.backups_for(documents)))
        # Not gated on `self.mode == MODE_REPO` like the buttons above: a
        # styled report is offered for a web-text scan too, so this looks at
        # both result slots directly rather than reusing `has_flags`.
        self.download_btn.setEnabled(
            bool(documents) or bool(self.result and self.result.spans))

    def _active_unicode_categories(self):
        if not self.settings.unicode_check_enabled:
            return None
        return tuple(self.settings.unicode_categories or ())

    def _unicode_spans(self) -> list:
        """Every finding from the non-keyboard-character pass, in either mode.

        Selected on `details["source"]` rather than on the detector name:
        the character pass now runs inside the offline detector as well as
        standalone alongside a paid one, so its findings arrive under more
        than one detector name but always with the same source stamp.
        """
        if not self.result:
            return []
        return [s for s in self.result.spans
                if (s.details or {}).get("source") == "characters"]

    def _on_analyze_clicked(self) -> None:
        # Inline validation before starting
        if not self._validate_target():
            return
        self._sync_state_from_ui()
        self._reset_scan_ui()
        self._save_settings_from_combos()
        error = self.view_model.analyze()
        if error and error != "browser_failed":
            QMessageBox.warning(self, "", error)

    def _validate_target(self) -> bool:
        """Validate the current target field inline. Returns True if valid."""
        self._clear_all_field_errors()
        target = self._current_target()
        if target:
            return True
        lang = self.lang
        if self.app_state.source == SOURCE_REPO:
            self._show_field_error(self.repo_path_edit,
                                   t("no_repo_path", lang))
        elif self.app_state.source == SOURCE_FILE:
            self._show_field_error(self.file_path_edit,
                                   t("no_file_path", lang))
        else:
            self._show_field_error(self.url_edit,
                                   t("url_label_full", lang))
        return False

    def _clear_all_field_errors(self) -> None:
        """Clear all inline error indicators."""
        for field in (self.url_edit, self.repo_path_edit, self.file_path_edit):
            self._clear_field_error(field)

    def _sync_state_from_ui(self) -> None:
        """Push current widget values into AppState before an action."""
        self.app_state.set_target(self._current_target())
        self.app_state.set_depth(self.depth_spin.value())

    def _save_settings_from_combos(self) -> None:
        """Persist combo selections to settings."""
        self.settings.crawl_depth = self.depth_spin.value()
        method = self.method_combo.currentData()
        if method:
            self.settings.default_method = method
        provider = self.provider_combo.currentData()
        if provider:
            self.settings.llm_provider = provider
        self.settings.save()

    def _missing_target_message(self) -> str:
        if self.source == SOURCE_REPO:
            return t("no_repo_path", self.lang)
        if self.source == SOURCE_FILE:
            return t("no_file_path", self.lang)
        return t("url_label_full", self.lang)

    def _note_message(self, note: str) -> str:
        """A normalisation note as a sentence for the status bar.

        The request records notes in one language for the log; the window says
        the two the user can actually act on in theirs, and falls back to the
        raw note for anything else rather than swallowing it.
        """
        if "browser" in note:
            return t("reader_browser_unavailable", self.lang)
        if "AI pass" in note or "account or key" in note:
            return t("method_ai_unavailable", self.lang)
        return note

    def _start_copy_pass(self) -> None:
        """The AI-patterns question, over whichever source is selected."""
        if self.source == SOURCE_REPO:
            self._start_repo_analysis()
        elif self.source == SOURCE_FILE:
            # A rendered file is a page, and is read as one: the DOM the
            # browser built is not on disk, so the file reader cannot see it.
            if self._reusable_pages() is not None:
                self._start_web_analysis(root=_browser_url(
                    self.file_path_edit.text().strip()))
            else:
                self._start_file_copy_analysis()
        else:
            self._start_web_analysis()

    def _detector_for_request(self) -> tuple[str, dict]:
        """The engine the copy pass runs, worked out from the method.

        This is the fix for a silent failure, so it is worth stating what it
        replaces: the window used to take the engine straight from a
        dropdown of backend names, and never read the method choice at all.
        `AnalysisRequest.wants_ai` existed, was normalised, was reported in
        the status bar - and no code path consulted it. Choosing "AI" with
        the offline backend still selected ran the offline engine and
        presented its findings as the answer.

        Now the method decides what runs and the account decides who pays:

            offline only  -> the free local engine
            AI only       -> the judge for the selected account
            hybrid        -> both, merged (see `detectors/hybrid.py`)

        The request is the normalised one, so a method that asked for a model
        with no account behind it has already fallen back to offline here -
        with a note in the status bar saying so, rather than in silence.
        """
        request = self._last_request or self.current_request()
        judge = judge_for_provider(
            self.provider_combo.currentData() or self.settings.llm_provider)
        if request.wants_ai and request.wants_local:
            name = "hybrid"
        elif request.wants_ai:
            name = judge
        else:
            name = "offline"
        return name, self._detector_config_for(name, judge)

    def _detector_config_for(self, detector_name: str, judge_name: str = "") -> dict:
        """Per-detector construction arguments.

        Resolved through the factory first, so a legacy name stored in an
        old settings.json ("heuristic") is configured as what it actually
        builds ("offline") rather than falling through to no arguments.
        """
        resolved = DetectorFactory.resolve(detector_name)
        if resolved == "hybrid":
            # The hybrid owns the character pass through its offline half,
            # and its judge half is configured exactly like a bare judge -
            # by asking this same function, so there is one answer to "how
            # is an xFormat judge built" rather than two.
            judge = judge_name or judge_for_provider(self.settings.llm_provider)
            return {
                "categories": self._active_unicode_categories() or (),
                "judge_name": judge,
                "judge_config": self._detector_config_for(judge),
            }
        if resolved in ("claude-llm-judge", "claude-official-watermark"):
            return {"api_key": config.get_anthropic_api_key(), "model": self.settings.claude_model}
        if resolved == "xformat-llm-judge":
            return {
                "base_url": self.settings.xformat_base_url,
                "endpoints": self.settings.xformat_endpoints,
            }
        if resolved == "offline":
            # The character categories are a content decision the user makes
            # in Settings; style analysis is always on in this detector.
            return {"categories": self._active_unicode_categories() or ()}
        return {}

    def _reset_scan_ui(self) -> None:
        self.analyze_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.flagged_list.clear()
        self._expanded_item = None
        self.current_preview_url = None
        self.current_preview_path = None
        self.site_view.setHtml("", QUrl())
        self.code_view.setPlainText("")
        self._reset_detail_panel()

    def _start_web_analysis(self, root: str = "") -> None:
        """The copy pass over fetched pages.

        `root` overrides the URL field, for the one case where the pages did
        not come from that field: a single local file that was rendered in
        the browser.
        """
        url = root or self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "", t("url_label_full", self.lang))
            return
        if not url.startswith(("http://", "https://", "file://")):
            url = "https://" + url

        detector_name, detector_config = self._detector_for_request()
        self._reset_scan_ui()

        reused = self._reusable_pages()
        if reused is not None:
            self.status_bar.showMessage(t("status_reusing_pages", self.lang,
                                         count=len(reused)))

        self.worker = AnalysisWorker(
            pages=reused,
            root_url=url,
            depth=self.depth_spin.value(),
            detector_name=detector_name,
            detector_config=detector_config,
            max_pages=self.settings.max_pages,
            unicode_categories=self._active_unicode_categories(),
            settings=self.settings,
        )
        self.worker.crawling.connect(self._on_crawling)
        self.worker.detecting.connect(self._on_detecting)
        self.worker.finished_ok.connect(self._on_web_finished)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self._on_worker_thread_finished)
        self._track_worker(self.worker)
        self.worker.start()

    def _start_file_copy_analysis(self) -> None:
        """The copy question asked of one HTML file.

        The same worker as a repository, over a single named path: a file that
        was named is a file to read, so the extension list and the exclusions
        that a walk needs do not apply to it.
        """
        self._start_repo_analysis(self.file_path_edit.text().strip())

    def _start_repo_analysis(self, path: str | None = None) -> None:
        path = path if path is not None else self.repo_path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "", t("no_repo_path", self.lang))
            return

        detector_name, detector_config = self._detector_for_request()
        self._reset_scan_ui()

        self.worker = RepoAnalysisWorker(
            files=self._reusable_files(),
            root_dir=path,
            ignore_patterns=self.repo_ignore_patterns,
            detector_name=detector_name,
            detector_config=detector_config,
            unicode_categories=self._active_unicode_categories(),
            scope=self._repo_scope(),
            settings=self.settings,
        )
        self.worker.scanning.connect(self._on_scanning_repo)
        self.worker.detecting.connect(self._on_detecting)
        self.worker.finished_ok.connect(self._on_repo_finished)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self._on_worker_thread_finished)
        self._track_worker(self.worker)
        self.worker.start()

    # --------------------------------------------------------- suppression

    def _ignore_scan_root(self) -> str | None:
        """The folder a fingerprint suppression should be written into, or
        None when the current source has no folder at all.

        A repository scan has one, obviously; a single file's suppression
        also goes there, so a second finding in a sibling file lands in the
        same list instead of starting a second `.xanalyze-ignore` next to it.
        A site has no folder on this machine - see `_add_fingerprint_suppression`.
        """
        if self.source == SOURCE_REPO:
            path = self.repo_path_edit.text().strip()
            return path or None
        if self.source == SOURCE_FILE:
            path = self.file_path_edit.text().strip()
            return str(Path(path).parent) if path else None
        return None

    def _add_fingerprint_suppression(self, value: str) -> None:
        """Record "ignore this exact finding", in whichever list applies.

        The project's `.xanalyze-ignore` when the source is a folder or a
        file on disk - that is the shared, committed list `suppression.py`
        documents. A personal, cross-project setting otherwise, since a page
        fetched over the network has no folder to hold a project file in.
        """
        root = self._ignore_scan_root()
        if root:
            suppression.add_fingerprint_to_ignore_file(root, value)
            return
        fingerprints = list((self.settings.ignore or {}).get("fingerprints") or [])
        if value not in fingerprints:
            fingerprints.append(value)
            ignore = dict(self.settings.ignore or {})
            ignore["fingerprints"] = fingerprints
            self.settings.ignore = ignore
            self.settings.save()

    def _on_ignore_span_clicked(self, span: TextSpan, block) -> None:
        """"Ignore this finding": suppress it and drop it from the list
        immediately, with an honest recount - not a re-run of the scan."""
        self._add_fingerprint_suppression(suppression.span_fingerprint(span, block))
        if self.result is not None:
            self.result.spans = [s for s in self.result.spans if s is not span]
        self._collapse_inline_detail()
        self._reset_detail_panel()
        self._populate_flagged_list()
        self._update_repo_buttons_enabled()

    def _on_ignore_issue_clicked(self, issue) -> None:
        """The audit counterpart of `_on_ignore_span_clicked`."""
        self._add_fingerprint_suppression(suppression.issue_fingerprint(issue))
        if self.audit_result is not None:
            for document in self.audit_result.documents:
                if issue in document.issues:
                    document.issues = [i for i in document.issues if i is not issue]
        self._collapse_inline_detail()
        self._reset_detail_panel()
        self._populate_flagged_list()
        self._update_audit_buttons_enabled()

    def _build_ignore_button(self, on_click) -> QPushButton:
        button = QPushButton(_IGNORE_FINDING_LABEL)
        button.setToolTip(_IGNORE_FINDING_TOOLTIP)
        button.clicked.connect(on_click)
        return button

    # ------------------------------------------------------------------ audit

    def _on_browse_file_clicked(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self, t("mode_file", self.lang), "",
            "HTML (*.html *.htm *.xhtml);;" + t("all_files", self.lang) + " (*)")
        if path:
            self.file_path_edit.setText(path)

    def _start_audit(self) -> None:
        """Audit the chosen source: accessibility, SEO, performance, best
        practices. The source is a site in one mode and one packed HTML file
        in the other; everything downstream is identical."""
        if self.mode == MODE_FILE:
            target = self.file_path_edit.text().strip()
            if not target:
                QMessageBox.warning(self, "", t("no_file_path", self.lang))
                return
        else:
            target = self.url_edit.text().strip()
            if not target:
                QMessageBox.warning(self, "", t("url_label_full", self.lang))
                return
            if not target.startswith(("http://", "https://")):
                target = "https://" + target

        self.audit_result = None
        self._reset_scan_ui()
        self.worker = AuditWorker(
            pages=self._reusable_pages() if self.source == SOURCE_SITE else None,
            target=target,
            depth=self.depth_spin.value(),
            max_pages=self.settings.max_pages,
            is_page_file=self.mode == MODE_FILE,
            settings=self.settings,
        )
        self.worker.crawling.connect(self._on_crawling)
        self.worker.auditing.connect(self._on_auditing)
        self.worker.finished_ok.connect(self._on_audit_finished)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self._on_worker_thread_finished)
        self._track_worker(self.worker)
        self.worker.start()

    def _on_auditing(self, target: str) -> None:
        self.status_bar.showMessage(t("status_auditing", self.lang, target=target))

    def _on_audit_finished(self, result) -> None:
        self.audit_result = result
        if self._last_request is not None and self._last_request.wants_browser:
            self._run_browser_pass()
        self._populate_audit_list()
        # Show the audited page straight away rather than waiting for a click.
        # An empty white pane next to a full list of findings reads as
        # something having gone wrong, which is the opposite of what happened.
        first = next((d for d in result.documents if not d.error), None)
        if first is not None:
            address = _browser_url(first.source)
            self.current_preview_url = address
            self.site_view.setUrl(QUrl(address))
        # Recomputed here, not only when the mode changes: whether there is
        # anything to write, and whether there is anything to take back, are
        # both facts about the result that just arrived.
        self._update_audit_buttons_enabled()
        # The same sentence the CLI prints, from the same function: two
        # wordings of one summary is two things to keep true.
        self.status_bar.showMessage(
            audit_explanations.summary_line(result, self.lang))
        if getattr(self, "_pending_copy_pass", False):
            # The second half of a both-questions run. `_reset_scan_ui` would
            # wipe the audit rows that just arrived, so the copy pass appends
            # to them instead: `_populate_flagged_list` puts the audit findings
            # back first.
            self._pending_copy_pass = False
            self._start_copy_pass()

    def _render_crawl(self, url: str):
        """Crawl with a browser in the loop, on this thread.

        Returns the pages, or None when the user should be told rather than
        given a silently worse reading. The point of doing this at all: a page
        whose copy is written by JavaScript has nothing to read in the response,
        and until now the tool could only say so.
        """
        from audit import driver
        from crawler import RENDER_AUTO, CrawlConfig, crawl

        usable, reason = driver.available()
        if not usable:
            QMessageBox.information(self, t("reader_browser", self.lang), reason)
            return None

        config = CrawlConfig(max_depth=self.depth_spin.value(),
                             max_pages=self.settings.max_pages,
                             render_mode=RENDER_AUTO)

        def progress(page_url: str, _depth: int) -> None:
            self.status_bar.showMessage(
                t("status_browser_pass", self.lang, url=page_url))

        try:
            with driver.html_renderer() as render:
                return crawl(url, config, progress_cb=progress, render=render)
        except Exception as exc:  # noqa: BLE001 - a failed browser is worth a
            # sentence, not a traceback: the run can still be repeated without
            # one, and the user is the one who chose to use it.
            QMessageBox.warning(self, t("reader_browser", self.lang), str(exc))
            return None

    def _render_single_file(self, path: str):
        """The DOM a browser builds for one local file, as one page.

        Returns None when the user should be told rather than handed a
        quietly worse reading - the same contract as `_render_crawl`.
        """
        from audit import driver
        from crawler import page_from_html

        if not path:
            QMessageBox.warning(self, "", t("no_file_path", self.lang))
            return None
        usable, reason = driver.available()
        if not usable:
            QMessageBox.information(self, t("reader_browser", self.lang), reason)
            return None
        address = _browser_url(path)
        self.status_bar.showMessage(
            t("status_browser_pass", self.lang, url=address))
        try:
            with driver.html_renderer() as render:
                html = render(address) or ""
        except Exception as exc:  # noqa: BLE001 - see `_render_crawl`
            QMessageBox.warning(self, t("reader_browser", self.lang), str(exc))
            return None
        if not html:
            QMessageBox.warning(self, t("reader_browser", self.lang),
                                t("reader_browser_empty", self.lang))
            return None
        return [page_from_html(html, address)]

    def _run_browser_pass(self) -> None:
        """Re-audit each page in a real browser, on this thread.

        On this thread on purpose: QtWebEngine is only usable from the thread
        that owns the application, so there is no version of this that runs in
        `AuditWorker`. The driver pumps the event loop while it waits, which is
        why the window stays repainted through a pass that takes seconds per
        page.
        """
        from audit import browser as browser_mod
        from audit import driver

        usable, reason = driver.available()
        if not usable:
            QMessageBox.information(self, t("browser_pass_label", self.lang), reason)
            return

        targets = [d for d in self.audit_result.documents if not d.error]
        if not targets:
            return

        suppressions = suppression.Suppressions.load(self.settings, None)
        options = browser_mod.BrowserAuditOptions(
            exclude=list(suppressions.selectors),
            disabled_rules=list(suppressions.rules),
            # Only a file the user picked themselves may read its neighbours
            # on disk; a page off the network never may.
            allow_local_files=self.mode == MODE_FILE,
        )
        # Every width, not just the one this screen happens to be: the point
        # of asking a browser at all is to see what a visitor sees, and a
        # visitor on a phone is shown a different document. The merge keeps
        # the list the same length - a finding present at several widths is
        # one row that records them - so this costs time, not noise. See
        # `audit/responsive.py`.
        from dataclasses import replace

        from audit import responsive

        sizes = responsive.BREAKPOINTS
        runner = driver.BrowserAuditRunner(
            replace(options, viewport=(sizes[0][1], sizes[0][2])))
        try:
            for document in targets:
                self.status_bar.showMessage(t("status_browser_pass_widths",
                                              self.lang, url=document.source,
                                              n=len(sizes)))
                page_audit = responsive.audit_responsive(
                    _browser_url(document.source), sizes, options, runner=runner)
                if page_audit.error:
                    continue
                document.issues = browser_mod.deduplicate(
                    list(document.issues) + list(page_audit.issues),
                    markup=getattr(page_audit, "html", "") or "")
        finally:
            runner.close()


    # ------------------------------------------------- writing an audit back

    def _on_fix_on_disk_clicked(self) -> None:
        """Write the corrections the audit already knows, into the files.

        Two tiers, and the difference is stated before anything is written:
        corrections that follow from the markup go in unattended, while ones
        that encode a judgement - is this image decorative, what does this
        page promise - are only written when a model has been asked to supply
        the words, and are named as the model's afterwards.
        """
        from audit import fix_ai, fixer

        if self.audit_result is None:
            return
        ready, pending, skipped = fixer.plan_fixes(self.audit_result.documents)

        page_text = self._audited_text()
        filled, pending = fix_ai.fill_locally(pending, page_text)
        ready += filled

        use_ai = False
        if pending:
            answer = QMessageBox.question(
                self, t("fix_on_disk_button", self.lang),
                t("fix_confirm_body", self.lang,
                  ready=len(ready), pending=len(pending)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
            )
            if answer == QMessageBox.StandardButton.Cancel:
                return
            use_ai = answer == QMessageBox.StandardButton.Yes
        elif not ready:
            QMessageBox.information(self, t("fix_on_disk_button", self.lang),
                                    t("fix_nothing_ready", self.lang))
            return

        written_by_model = []
        if use_ai:
            import rewriter

            try:
                provider = rewriter.build_provider(self.settings)
                filled, pending = fix_ai.describe(pending, page_text, provider,
                                                  self.lang)
                ready += filled
                written_by_model = [p.rule_id for p in filled]
            except rewriter.LLMUnavailable as exc:
                QMessageBox.warning(self, t("fix_on_disk_button", self.lang), str(exc))

        outcome = fixer.apply_fixes(ready)
        outcome.skipped.extend(skipped)
        for plan in pending:
            outcome.skipped.append(
                fixer.SkippedFix(plan.rule_id, plan.path, plan.line, plan.needs_input))

        self._report_fix_outcome(outcome, written_by_model)
        self._reaudit_after_fix()

    def _on_undo_fix_clicked(self) -> None:
        from audit import fixer

        paths = fixer.backups_for(self.audit_result.documents if self.audit_result else [])
        if not paths:
            return
        restored, problems = fixer.restore(paths)
        message = t("undo_done", self.lang, files=len(restored))
        if problems:
            message += "\n\n" + "\n".join(problems)
        QMessageBox.information(self, t("undo_fix_button", self.lang), message)
        self._reaudit_after_fix()

    def _on_download_clicked(self) -> None:
        """Ask which report, then write it.

        The question is only asked when there is a choice: with only an audit
        or only a text scan in hand one of the two documents cannot be built,
        and offering it would be a dialog whose second option is an error
        message waiting to happen.
        """
        has_audit = bool(self.audit_result and self.audit_result.documents)
        has_text = bool(self.result and self.result.spans)
        if not has_audit and not has_text:
            return
        if not has_audit:
            self._on_styled_report_clicked()
            return

        box = QMessageBox(self)
        box.setWindowTitle(t("download_button", self.lang))
        box.setText(t("download_which", self.lang))
        styled = box.addButton(_styled_report_text(self.lang, "button"),
                               QMessageBox.ButtonRole.AcceptRole)
        agent = box.addButton(t("export_report_button", self.lang),
                              QMessageBox.ButtonRole.AcceptRole)
        # The briefing is the technical one, so the reader-facing document is
        # the default: it is what someone who clicked "Download" without a
        # further thought most likely meant.
        box.setDefaultButton(styled)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is styled:
            self._on_styled_report_clicked()
        elif clicked is agent:
            self._on_export_report_clicked()

    def _on_export_report_clicked(self) -> None:
        """Save a briefing another tool - or a coding agent - can act on."""
        if self.audit_result is None:
            return
        path, _filter = QFileDialog.getSaveFileName(
            self, t("export_report_button", self.lang), "audit-report.md",
            "Markdown (*.md);;JSON (*.json)")
        if not path:
            return
        import cli

        class _Args:
            report = path
        try:
            cli._write_report(self.audit_result, _Args(), self.lang, None)
        except OSError as exc:
            QMessageBox.warning(self, t("export_report_button", self.lang), str(exc))
            return
        QMessageBox.information(self, t("export_report_button", self.lang),
                                t("export_report_done", self.lang, path=path))

    def _on_styled_report_clicked(self) -> None:
        """Save the branded, print-ready report - the same findings the
        list already shows, laid out as a document instead of a list.

        Independent of `_on_export_report_clicked`: that one always reads
        `self.audit_result` and writes the agent briefing; this one builds
        from whichever result(s) this run actually has, text or audit or
        both (a "both questions" run merges the two into one document, its
        audit findings first - same order `_populate_flagged_list` uses).
        """
        has_text = bool(self.result and self.result.spans)
        has_audit = bool(self.audit_result and self.audit_result.documents)
        if not has_text and not has_audit:
            return
        path, _filter = QFileDialog.getSaveFileName(
            self, _styled_report_text(self.lang, "button"), "scan-report.pdf",
            "PDF (*.pdf);;HTML (*.html)")
        if not path:
            return

        from report.export import write_styled_report
        from report.model import from_accessibility, from_text_analysis

        model = from_accessibility(self.audit_result, lang=self.lang) if has_audit else None
        if has_text:
            text_model = from_text_analysis(self.result, drafts=self.drafts)
            if model is None:
                model = text_model
            else:
                model.findings.extend(text_model.findings)
        try:
            write_styled_report(path, model, self.lang)
        except (OSError, RuntimeError) as exc:
            QMessageBox.warning(self, _styled_report_text(self.lang, "button"), str(exc))
            return
        QMessageBox.information(self, _styled_report_text(self.lang, "button"),
                                _styled_report_text(self.lang, "done", path=path))

    def _report_fix_outcome(self, outcome, written_by_model) -> None:
        lines = [t("fix_done", self.lang, applied=len(outcome.applied),
                   files=len(outcome.files_changed))]
        if written_by_model:
            lines.append(t("fix_done_by_model", self.lang,
                           rules=", ".join(sorted(set(written_by_model)))))
        if outcome.skipped:
            lines.append("")
            lines.append(t("fix_left_alone", self.lang, count=len(outcome.skipped)))
            for item in outcome.skipped[:6]:
                lines.append(f"  {item.rule_id}: {item.reason}")
        for error in outcome.errors:
            lines.append(error)
        QMessageBox.information(self, t("fix_on_disk_button", self.lang),
                                "\n".join(lines))

    def _audited_text(self) -> str:
        """The words of the audited files, for anything that has to read them."""
        import re

        parts = []
        for document in (self.audit_result.documents if self.audit_result else []):
            if document.source.startswith(("http://", "https://")):
                continue
            try:
                with open(document.source, encoding="utf-8", errors="replace") as handle:
                    parts.append(re.sub(r"<[^>]+>", " ", handle.read()))
            except OSError:
                continue
        return " ".join(parts)

    def _reaudit_after_fix(self) -> None:
        """Re-read the files so the list matches what is now on disk.

        Leaving the old findings on screen after writing to the file would
        show work as outstanding that has just been done, which is the one
        thing a fix button must not do.
        """
        if self.audit_result is None:
            return
        self._start_audit()

    def _populate_audit_list(self) -> None:
        self.flagged_list.clear()
        self._expanded_item = None
        if not self._add_audit_rows():
            self._show_audit_empty_state()
            return
        self.results_stack.setCurrentIndex(0)

    def _add_audit_rows(self) -> int:
        """Append the audit findings to the list and say how many there were.

        Separate from clearing the list because a run can ask both questions,
        and then the copy pass finishes second and must add to these rows
        rather than replace them.
        """
        if self.audit_result is None:
            return 0
        issues = self.audit_result.issues()
        if not issues:
            return 0

        self.results_stack.setCurrentIndex(0)
        self.flagged_list.setItemDelegate(self.finding_delegate)
        for issue in issues:
            explanation = audit_explanations.render(issue, self.lang)
            item = QListWidgetItem()
            item.setText(explanation.title)
            item.setData(ROW_ROLE, RowData(
                badge=t(f"severity_{issue.severity}", self.lang),
                # The delegate colours a row by confidence, and severity is
                # the audit's word for the same axis. Mapped rather than
                # given the delegate a second vocabulary to paint.
                confidence=_SEVERITY_CONFIDENCE.get(issue.severity, Confidence.MEDIUM),
                score=0.0,
                text=explanation.title,
                has_draft=False,
                is_character=False,
            ))
            item.setToolTip(explanation.found)
            item.setData(Qt.ItemDataRole.UserRole, (MODE_AUDIT, issue, None))
            self.flagged_list.addItem(item)
        return len(issues)

    def _show_audit_empty_state(self) -> None:
        """An audit with no findings is a result, not a blank screen — and it
        is not a clean bill of health either, which the body text has to say
        rather than imply."""
        self.results_stack.setCurrentIndex(1)
        if self.audit_result is None:
            self.empty_state.show_message(
                t("empty_no_scan_title", self.lang),
                t("empty_no_scan_body", self.lang),
            )
            return
        checked = len(self.audit_result.documents)
        unreadable = [d for d in self.audit_result.documents if d.error]
        if checked and not unreadable:
            self.empty_state.show_message(
                t("empty_audit_clean_title", self.lang),
                t("empty_audit_clean_body", self.lang, documents=checked),
            )
            return
        lines = [t("empty_audit_unreadable_body", self.lang), ""]
        for document in unreadable[:5]:
            lines.append(document.source)
            lines.append(document.error)
            lines.append("")
        self.empty_state.show_message(
            t("empty_audit_unreadable_title", self.lang), "\n".join(lines).strip())

    def _on_audit_item_clicked(self, issue) -> None:
        """Show the finding in its document, and the explanation beside it.

        "Show" means the element, not the page: a list of findings next to a
        page scrolled to the top leaves the reader to hunt for the thing the
        row is about. Which preview does the showing depends on what the
        document is - a page gets outlined in the browser, a source file gets
        its line highlighted.
        """
        if self.source == SOURCE_REPO:
            self._show_audit_issue_in_code(issue)
        else:
            self._show_audit_issue_in_page(issue)
        if self.wide_mode:
            self._clear_layout(self.detail_layout)
            self.detail_layout.addWidget(self._build_audit_detail_widget(issue))
        else:
            # In a narrow window there is no third column, so the explanation
            # expands under the row that was clicked - the same behaviour the
            # text scan has always had.
            self._toggle_audit_detail(self.flagged_list.currentItem(), issue)

    #: Elements a finding can name that cannot be pointed at on screen.
    #: `<head>` has no rendered box, and outlining `<html>` outlines
    #: everything, which points at nothing.
    _UNSHOWABLE_ELEMENTS = ("head", "html")

    @staticmethod
    def _element_of(snippet: str) -> str:
        """The element name a snippet opens with, or "".

        Findings about the document as a whole carry no selector - they are
        about an element that is missing, so there is nothing to select - but
        they do say which container they were raised against (`<body>…</body>`),
        and that is enough to point at.
        """
        import re
        match = re.match(r"\s*<([a-zA-Z][\w:-]*)", snippet or "")
        return match.group(1).lower() if match else ""

    def _audit_target(self, issue) -> str:
        """The CSS selector this finding can be shown at, or "" if none can.

        Written as its own function because the answer is not "issue.selector":
        five of the eight findings a plain page produces (no h1, no canonical,
        no meta description, no Open Graph, no structured data) have an empty
        selector and no line, since what they report is something *absent*.
        Clicking those used to do nothing at all - no highlight, no message,
        no reason given - which is what "some findings are not clickable"
        turned out to mean.
        """
        if issue.selector:
            return issue.selector
        element = self._element_of(issue.snippet)
        if not element or element in self._UNSHOWABLE_ELEMENTS:
            return ""
        return element

    def _show_audit_issue_in_page(self, issue) -> None:
        address = _browser_url(issue.source)
        target = self._audit_target(issue)
        # Held until the page reports itself loaded: highlighting a document
        # that is still arriving finds nothing and leaves no trace of trying.
        self._pending_highlight_dom_path = target
        self._pending_highlight_tag = issue.snippet or ""
        if not target:
            # Said rather than left silent: the finding is about the document,
            # and a click that quietly does nothing reads as a broken row.
            self.status_bar.showMessage(t("audit_document_level", self.lang))
        if self.current_preview_url != address:
            self.current_preview_url = address
            self.site_view.setUrl(QUrl(address))
        else:
            self._run_pending_highlight()

    def _show_audit_issue_in_code(self, issue) -> None:
        """A repository finding lives on a line of a file, so show that line -
        and when it has no line, show the file anyway.

        The early return that used to stand here made every document-level
        finding in repository mode do nothing when clicked, including the case
        where the file was not even open in the preview yet.
        """
        from pathlib import Path

        from ui.code_preview import highlight_line

        try:
            text = Path(issue.source).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            self.status_bar.showMessage(str(exc))
            return
        if self.current_preview_path != issue.source:
            self.current_preview_path = issue.source
            self.code_view.setPlainText(text)
        self.col1_stack.setCurrentIndex(1)
        if issue.line:
            highlight_line(self.code_view, issue.line, self._highlight_color())
        else:
            self.status_bar.showMessage(t("audit_document_level", self.lang))

    def _toggle_audit_detail(self, item, issue) -> None:
        """Expand the finding under its row, or collapse it if already open."""
        if item is None:
            return
        if self._expanded_item is item:
            self._collapse_inline_detail()
            return
        self._collapse_inline_detail()
        detail = self._build_audit_detail_widget(issue)
        # Bounded: an explanation with four blocks and two code samples is
        # taller than a list row has any business being, and a row that fills
        # the window hides the findings the user is comparing it against.
        detail.setMaximumHeight(460)
        self.flagged_list.setItemWidget(item, detail)
        item.setSizeHint(QSize(0, min(detail.sizeHint().height(), 460)))
        self._expanded_item = item

    def _build_audit_detail_widget(self, issue) -> QWidget:
        """One finding, laid out as the four questions it answers.

        What was found, why it matters, how to fix it, and - when the check
        cannot be certain - what would make it a false positive. Four boxed
        blocks rather than four paragraphs: someone who already believes the
        finding wants only the third one, and should not have to read the
        first two to reach it.

        Under them, where the rule knows the corrected markup, the correction
        itself and a button that writes exactly that one element. The button
        is here rather than only in the toolbar because this is the moment
        the user has decided about *this* finding, and making them then find
        it again in a batch is how a fix list stops being used.
        """
        from PySide6.QtWidgets import QScrollArea

        explanation = audit_explanations.render(issue, self.lang)
        container, body, _title = panel(t("detail_panel_title", self.lang))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(self.palette_tokens.space_sm)

        title = heading(explanation.title)
        title.setWordWrap(True)
        layout.addWidget(title)

        # The identity of the finding, as chips: severity, where it is, and
        # who found it. A row of small facts reads faster than a sentence
        # that has to be parsed to get at the same three things.
        # A flow, not a row: chips used to push the column's minimum width to
        # the sum of their own, so the third column could not be narrowed and a
        # long selector made the whole window unshrinkable.
        chips_host = QWidget()
        chips = FlowLayout(chips_host, spacing=6)
        severity_chip = QLabel(t(f"severity_{issue.severity}", self.lang))
        severity_chip.setProperty("class", _SEVERITY_BADGE[issue.severity])
        chips.addWidget(severity_chip)
        # The tail of the selector, short enough not to dictate how narrow the
        # column may become. The whole of it is on the chip as a tooltip: it is
        # worth having, just not worth 300 pixels of minimum width.
        if issue.line:
            where = f"{t('detail_line', self.lang)} {issue.line}"
            where_full = where
        else:
            where_full = issue.selector or Path(issue.source).name
            where = where_full[-28:]
            if len(where_full) > 28:
                where = "…" + where
        where_chip = chip(where)
        where_chip.setToolTip(where_full)
        chips.addWidget(where_chip)
        chips.addWidget(chip(issue.rule_id))
        if issue.engine and issue.engine != "static":
            chips.addWidget(chip(issue.engine))
        layout.addWidget(chips_host)

        layout.addWidget(divider())

        for label_key, text_body in (("audit_found", explanation.found),
                                     ("audit_why", explanation.why),
                                     ("audit_fix", explanation.fix),
                                     ("audit_caveat", explanation.caveat)):
            if text_body:
                layout.addWidget(field(t(label_key, self.lang), text_body))

        if issue.snippet:
            layout.addWidget(self._evidence(t("detail_element", self.lang),
                                            issue.snippet))
        if issue.fix_snippet:
            layout.addWidget(self._evidence(t("detail_replacement", self.lang),
                                            issue.fix_snippet))

        confirmations = (issue.details or {}).get("also_found_by")
        if confirmations:
            layout.addWidget(muted(t("audit_also_found_by", self.lang,
                                     engines=", ".join(confirmations))))

        layout.addStretch(1)
        scroll.setWidget(inner)
        body.addWidget(scroll, stretch=1)

        actions = self._detail_actions(issue)
        if actions is not None:
            body.addWidget(divider())
            body.addWidget(actions)

        body.addWidget(divider())
        ignore_row = QWidget()
        ignore_layout = QHBoxLayout(ignore_row)
        ignore_layout.setContentsMargins(14, 10, 14, 12)
        ignore_layout.addStretch(1)
        ignore_layout.addWidget(
            self._build_ignore_button(lambda: self._on_ignore_issue_clicked(issue)))
        body.addWidget(ignore_row)
        return container

    def _evidence(self, label_text: str, markup: str) -> QWidget:
        """Markup shown as evidence: readable, selectable, not editable."""
        holder = QWidget()
        holder.setProperty("class", theme.CLASS_FIELD)
        holder.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(4)
        caption = QLabel(label_text.upper())
        caption.setProperty("class", theme.CLASS_FIELD_LABEL)
        layout.addWidget(caption)
        view = QPlainTextEdit(markup)
        view.setProperty("class", theme.CLASS_CODE)
        view.setReadOnly(True)
        view.setMaximumHeight(84)
        layout.addWidget(view)
        return holder

    def _detail_actions(self, issue):
        """The row of things that can be done about this one finding.

        Absent entirely when there is nothing to do: a disabled button with a
        tooltip explaining why it is disabled is a worse answer than the
        sentence that replaces it here.
        """
        from audit import fixer

        if not issue.fix_snippet or issue.source.startswith(("http://", "https://")):
            return None

        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(self.palette_tokens.space_sm)

        held_back = fixer.DECISION_RULES.get(issue.rule_id, "")
        if held_back:
            note = muted(t("detail_needs_decision", self.lang))
            note.setWordWrap(True)
            layout.addWidget(note, stretch=1)
        else:
            layout.addStretch(1)

        button = QPushButton(t("detail_fix_this", self.lang))
        button.setProperty("class", theme.CLASS_ACCENT)
        button.setToolTip(t("detail_fix_this_tooltip", self.lang))
        button.clicked.connect(lambda: self._fix_single_issue(issue))
        layout.addWidget(button)
        return row

    def _fix_single_issue(self, issue) -> None:
        """Write one correction, for the finding in front of the user."""
        from audit import fix_ai, fixer
        from audit.engine import DocumentReport

        document = DocumentReport(source=issue.source)
        document.issues = [issue]
        ready, pending, skipped = fixer.plan_fixes([document])

        if pending:
            filled, pending = fix_ai.fill_locally(pending, self._audited_text())
            ready += filled

        if pending:
            plan = pending[0]
            answer = QMessageBox.question(
                self, t("detail_fix_this", self.lang),
                t("detail_decide_body", self.lang, reason=plan.needs_input),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            import rewriter

            try:
                provider = rewriter.build_provider(self.settings)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, t("detail_fix_this", self.lang), str(exc))
                return
            filled, pending = fix_ai.describe(pending, self._audited_text(),
                                              provider, self.lang)
            ready += filled

        if not ready:
            reason = (skipped[0].reason if skipped
                      else (pending[0].needs_input if pending else ""))
            QMessageBox.information(self, t("detail_fix_this", self.lang),
                                    reason or t("fix_nothing_ready", self.lang))
            return

        outcome = fixer.apply_fixes(ready)
        if outcome.errors:
            QMessageBox.warning(self, t("detail_fix_this", self.lang),
                                "\n".join(outcome.errors))
            return
        self.status_bar.showMessage(
            t("fix_done", self.lang, applied=len(outcome.applied),
              files=len(outcome.files_changed)))
        self._reaudit_after_fix()


    def _repo_scope(self) -> str:
        return self.scope_combo.currentData() or self.settings.repo_scope or SCOPE_CONTENT

    def _on_scope_changed(self, _idx: int) -> None:
        """Changing the scope invalidates the results: a findings list built
        from comments has nothing to say about a scan of page copy, and
        leaving it on screen would invite acting on the wrong one."""
        self.settings.repo_scope = self._repo_scope()
        self.scope_combo.setToolTip(t(f"scope_{self.settings.repo_scope}_full", self.lang))
        if self.mode == MODE_REPO and self.result is not None:
            self.result = None
            self._populate_flagged_list()
            self._reset_detail_panel()
            self.status_bar.showMessage(t("status_idle", self.lang))

    def _on_browse_clicked(self) -> None:
        path = QFileDialog.getExistingDirectory(self, self.browse_btn.text())
        if path:
            self.repo_path_edit.setText(path)

    def _on_exclusions_clicked(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle(t("exclusions_dialog_title", self.lang))
        layout = QVBoxLayout(dlg)
        editor = QPlainTextEdit()
        editor.setPlainText("\n".join(self.repo_ignore_patterns))
        layout.addWidget(editor)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)
        dlg.resize(520, 420)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.repo_ignore_patterns = _parse_ignore_text(editor.toPlainText())

    def _on_cancel_clicked(self) -> None:
        self.view_model.cancel()
        self.cancel_btn.setEnabled(False)

    def _on_crawling(self, url: str, depth: int) -> None:
        self.status_bar.showMessage(t("status_crawling", self.lang, url=url, depth=depth))

    def _on_scanning_repo(self, rel_path: str) -> None:
        self.status_bar.showMessage(t("status_scanning_repo", self.lang, path=rel_path))

    def _on_detecting(self, detector_label: str) -> None:
        self.status_bar.showMessage(t("status_detecting", self.lang, detector=detector_label))

    def _on_web_finished(self, result: AnalysisResult) -> None:
        self.result = result
        # Remembered on success only: a cancelled or failed fetch has nothing
        # worth answering the next question from.
        self._remember_extraction(self._last_request, pages=result.pages)
        self._populate_flagged_list()
        n_flags = sum(1 for s in result.spans if s.confidence != Confidence.LOW)
        self.status_bar.showMessage(
            t("status_done", self.lang, pages=len(result.pages), blocks=len(result.blocks()), flags=n_flags)
        )
        self._update_repo_buttons_enabled()

    def _on_repo_finished(self, result: RepoAnalysisResult) -> None:
        self.result = result
        self._remember_extraction(self._last_request, files=result.files,
                                  scope=self._repo_scope())
        self._populate_flagged_list()
        n_flags = sum(1 for s in result.spans if s.confidence != Confidence.LOW)
        self.status_bar.showMessage(
            t("status_done", self.lang, pages=len(result.files), blocks=len(result.blocks()), flags=n_flags)
        )
        self._update_repo_buttons_enabled()

    def _on_failed(self, message: str) -> None:
        self.status_bar.showMessage(t("status_error", self.lang, error=message))
        QMessageBox.critical(self, "", message)

    def _on_worker_thread_finished(self) -> None:
        self.analyze_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    # ------------------------------------------------------------- column 2

    @staticmethod
    def _is_character_span(span: TextSpan) -> bool:
        return (span.details or {}).get("source") == "characters"

    @staticmethod
    def _copy_key(span: TextSpan, block) -> tuple:
        """What makes two findings in two files the same finding: the flagged
        text and what it becomes. Not the file, which is the thing that
        varies, and not the offsets, which differ between a source file and
        its compiled twin."""
        return (block.text[span.start:span.end], span.replacement,
                (span.details or {}).get("source", span.detector_name))

    def _copy_counts(self, spans, blocks_by_id) -> dict:
        counts: dict = {}
        for span in spans:
            block = blocks_by_id.get(span.block_id)
            if block is None:
                continue
            key = self._copy_key(span, block)
            counts[key] = counts.get(key, 0) + 1
        return counts

    def _span_label(self, span: TextSpan, block) -> str:
        """One line describing a flagged span.

        A non-keyboard character often has no visible glyph at all — a
        zero-width joiner rendered as-is would leave the row looking blank —
        so those rows show what was found plus a little surrounding text
        instead of the raw characters. The surrounding text is what makes
        the row identifiable when the same invisible character occurs a
        dozen times on a page.
        """
        raw = block.text[span.start:span.end]
        if self._is_character_span(span):
            before = block.text[max(0, span.start - 20):span.start].replace("\n", " ")
            after = block.text[span.end:span.end + 20].replace("\n", " ")
            names = span.explanation.split("] ", 1)[-1]
            if len(names) > 70:
                names = names[:69] + "…"
            return f"{names}   ·   …{before}⟦{raw}⟧{after}…"
        snippet = raw.strip().replace("\n", " ")
        snippet = snippet[:89] + "…" if len(snippet) > 90 else snippet
        kind = getattr(block, "kind", None)
        # Only labelled when more than one kind can be on screen at once —
        # in a pure content scan every row is markup or an injected string
        # and the prefix would be noise on every line.
        if kind and self._repo_scope() == SCOPE_BOTH:
            return f"[{t('kind_' + kind, self.lang)}] {snippet}"
        return snippet

    def _populate_flagged_list(self) -> None:
        self.flagged_list.clear()
        self._expanded_item = None
        # A both-questions run put its audit findings here first; they are part
        # of the same result and must not disappear when the copy pass lands.
        audit_rows = (self._add_audit_rows()
                      if self._last_request is not None
                      and self._last_request.wants_accessibility else 0)
        if not self.result:
            if not audit_rows:
                self._show_empty_state()
            return
        flagged = [s for s in self.result.spans if s.confidence != Confidence.LOW]
        flagged.sort(key=lambda s: s.score, reverse=True)
        if not flagged:
            if not audit_rows:
                self._show_empty_state()
            return

        self.results_stack.setCurrentIndex(0)
        blocks_by_id = {b.block_id: b for b in self.result.blocks()}
        item_to_reselect = None
        # Copies of one file - source, compiled output, deployed folder -
        # produce the same defect once each. They stay in `self.result.spans`
        # because each is a real file a fix has to edit; what the list shows
        # is one row per distinct text, with the rest counted on it. See
        # `duplicates.py`.
        copies = self._copy_counts(flagged, blocks_by_id)
        shown_keys: set = set()
        for span in flagged:
            block = blocks_by_id.get(span.block_id)
            if block is None:
                continue
            copy_key = self._copy_key(span, block)
            if copy_key in shown_keys:
                continue
            shown_keys.add(copy_key)
            key = (span.block_id, span.start, span.end)
            item = QListWidgetItem()
            # The row is painted by FindingDelegate rather than rendered from
            # this string, so the confidence badge can be a real coloured
            # pill instead of "[high · 0.95]" typed into the label. The plain
            # text is still set, because that is what keyboard search,
            # accessibility tooling and a copied selection read.
            label = self._span_label(span, block)
            extra = copies.get(copy_key, 1) - 1
            if extra:
                label += "   ·   " + t("finding_copies", self.lang, n=extra)
            item.setText(label)
            item.setData(ROW_ROLE, RowData(
                badge=f"{t('confidence_' + span.confidence.value, self.lang)} {span.score:.2f}",
                confidence=span.confidence,
                score=span.score,
                text=item.text(),
                has_draft=key in self.drafts,
                is_character=self._is_character_span(span),
            ))
            item.setToolTip(span.explanation)
            item.setData(Qt.ItemDataRole.UserRole, (self._text_row_kind(), span, block))
            self.flagged_list.addItem(item)
            if self._last_selected_key and key[0] == self._last_selected_key[0]:
                item_to_reselect = (item, span, block)

        # Best-effort: if a passage was expanded (narrow layout) or shown in
        # the detail column (wide layout) and a re-analysis just rebuilt the
        # list, put the same block back in front of the user instead of
        # silently collapsing everything.
        if item_to_reselect and not self.wide_mode:
            self._expand_item(*item_to_reselect)
        elif item_to_reselect and self.wide_mode:
            self._populate_detail_column(item_to_reselect[1], item_to_reselect[2])

    def _show_empty_state(self) -> None:
        """Explain an empty findings list instead of leaving it blank.

        Three different situations produce no rows, and they need different
        answers. "Nothing scanned yet" is an instruction. "Scanned, nothing
        flagged" is a result, and has to say plainly that it is not proof of
        anything. "Scanned but the crawler got no text" is the one that is
        actually a problem, and it is the reason `PageDiagnostics` exists —
        without it, a JavaScript-rendered site is indistinguishable from a
        clean one.
        """
        self.results_stack.setCurrentIndex(1)
        if not self.result:
            self.empty_state.show_message(
                t("empty_no_scan_title", self.lang),
                t("empty_no_scan_body", self.lang),
            )
            return

        blocks = len(self.result.blocks())
        if blocks:
            units = (len(self.result.pages) if isinstance(self.result, AnalysisResult)
                     else len(self.result.files))
            body = t("empty_clean_body", self.lang, blocks=blocks, pages=units)
            # A clean result from a truncated walk is not a clean result. The
            # sentence goes here rather than only in the status bar because
            # this pane is what a reader is looking at when they conclude the
            # repository is fine.
            body += self._truncation_notice()
            self.empty_state.show_message(t("empty_clean_title", self.lang), body)
            return

        if isinstance(self.result, RepoAnalysisResult):
            self.empty_state.show_message(
                t("empty_repo_no_text_title", self.lang),
                t("empty_repo_no_text_body", self.lang, files=len(self.result.files)),
            )
            return

        self.empty_state.show_message(
            t("empty_no_text_title", self.lang),
            self._crawl_diagnosis(),
        )

    def _truncation_notice(self) -> str:
        """The sentence a partial walk owes the reader, or "" when it read
        everything. Empty string rather than None so it can be concatenated
        without a branch at every call site."""
        walk = getattr(self.result, "diagnostics", None)
        if walk is None or not getattr(walk, "truncated", False):
            return ""
        return "\n\n" + t("scan_truncated", self.lang, limit=walk.limit,
                           files=walk.files_read)

    def _crawl_diagnosis(self) -> str:
        """Per-page reasons the crawl produced no text.

        Only pages that actually yielded nothing are listed: on a multi-page
        crawl the interesting output is which pages failed and why, not a
        repetition of the ones that worked. The advice line is added only
        for the client-rendered case, because it is the only one with a
        concrete next step from inside this app.
        """
        lines = [t("empty_no_text_body", self.lang), ""]
        empty_pages = [p for p in self.result.pages if not p.blocks]
        for page in empty_pages[:5]:
            message = diagnostics_message(page, self.lang)
            lines.append(page.url)
            lines.append(message or t("crawl_reason_no_text", self.lang))
            lines.append("")
        if len(empty_pages) > 5:
            lines.append(t("pages_with_problems", self.lang, n=len(empty_pages)))
        if any("js-rendered" in (p.diagnostics.reasons or []) for p in empty_pages):
            lines.append(t("crawl_advice_js", self.lang))
        return "\n".join(lines).strip()

    def _on_flagged_item_clicked(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        kind, span, block = data
        if kind == MODE_AUDIT:
            self._on_audit_item_clicked(span)
            return
        self._last_selected_key = (span.block_id, span.start, span.end)
        if kind == MODE_WEB:
            self._load_preview_and_highlight(block)
        else:
            self._load_code_preview_and_highlight(block)
        if self.wide_mode:
            self._populate_detail_column(span, block)
        else:
            self._toggle_inline_detail(item, span, block)

    # ------------------------------------------------------------- column 1

    def _load_preview_and_highlight(self, block: TextBlock) -> None:
        if not self.result:
            return
        page = next((p for p in self.result.pages if p.url == block.page_url), None)
        if page is None or not page.raw_html:
            return
        self._pending_highlight_dom_path = block.dom_path
        self._pending_highlight_tag = ""
        if self.current_preview_url != block.page_url:
            self.current_preview_url = block.page_url
            self.site_view.setHtml(page.raw_html, QUrl(block.page_url))
        else:
            self._run_pending_highlight()

    def _on_preview_loaded(self, _ok: bool) -> None:
        self._run_pending_highlight()

    def _highlight_color(self) -> QColor:
        """The one red used everywhere something is pointed at: the HIGH
        confidence badge, the code preview's highlight, and the site
        preview's outline. Derived from the palette rather than each of the
        three carrying its own hard-coded hex, so a token change moves all
        three together instead of two of the three."""
        color = QColor(self.palette_tokens.error)
        color.setAlpha(70)
        return color

    def _run_pending_highlight(self) -> None:
        if self._pending_highlight_dom_path:
            self.site_view.page().runJavaScript(build_highlight_js(
                self._pending_highlight_dom_path,
                getattr(self, "_pending_highlight_tag", ""),
                color=self.palette_tokens.error))

    def _load_code_preview_and_highlight(self, block: CodeBlock) -> None:
        if not self.result:
            return
        file_result = next((f for f in self.result.files if f.path == block.file_path), None)
        if file_result is None or file_result.raw_text is None:
            return
        if self.current_preview_path != block.file_path:
            self.current_preview_path = block.file_path
            self.code_view.setPlainText(file_result.raw_text)
        highlight_range(self.code_view, block.start, block.end, self._highlight_color())

    # ------------------------------------------------------------- column 3

    def _reset_detail_panel(self) -> None:
        self._clear_layout(self.detail_layout)
        placeholder = muted(t("select_prompt", self.lang))
        self.detail_layout.addWidget(placeholder)

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _populate_detail_column(self, span: TextSpan, block) -> None:
        self._clear_layout(self.detail_layout)
        self.detail_layout.addWidget(self._build_detail_widget(span, block))

    def _collapse_inline_detail(self) -> None:
        if self._expanded_item is not None:
            self.flagged_list.setItemWidget(self._expanded_item, None)
            self._expanded_item.setSizeHint(QSize())
            self._expanded_item = None

    def _toggle_inline_detail(self, item: QListWidgetItem, span: TextSpan, block) -> None:
        if self._expanded_item is item:
            self._collapse_inline_detail()
            return
        self._expand_item(item, span, block)

    def _expand_item(self, item: QListWidgetItem, span: TextSpan, block) -> None:
        if self._expanded_item is not None and self._expanded_item is not item:
            self.flagged_list.setItemWidget(self._expanded_item, None)
            self._expanded_item.setSizeHint(QSize())

        header = QLabel(item.text())
        # The same class the panel titles use, not an ad-hoc bold: an inline
        # expansion is standing in for the third column's own title, and
        # inventing a second "this is a heading" style for it is exactly the
        # kind of small divergence that adds up to "nothing quite matches".
        header.setProperty("class", theme.CLASS_HEADING)
        header.setWordWrap(True)
        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(6, 6, 6, 6)
        wrapper_layout.addWidget(header)
        wrapper_layout.addWidget(self._build_detail_widget(span, block))
        self.flagged_list.setItemWidget(item, wrapper)
        item.setSizeHint(wrapper.sizeHint())
        self._expanded_item = item

    def _build_detail_widget(self, span: TextSpan, block) -> QWidget:
        lang = self.lang
        key = (block.block_id, span.start, span.end)
        original = block.text[span.start:span.end]
        is_repo_block = isinstance(block, CodeBlock)

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)

        if is_repo_block:
            source_label = QLabel(t("source_file", lang, path=block.file_path, line=block.line_number))
        else:
            source_label = QLabel(t("source_page", lang, url=block.page_url))
        source_label.setWordWrap(True)
        layout.addWidget(source_label)

        original_caption = muted(t("detail_original_label", lang))
        layout.addWidget(original_caption)
        original_view = QLabel(original)
        original_view.setWordWrap(True)
        original_view.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(original_view)

        # --- why this was flagged, and what to replace it with --------------
        # The score alone tells the user nothing they can act on. This turns
        # the detector's structured record into sentences in their language,
        # and — when the correction follows a rule rather than taste — offers
        # the corrected text directly, with no model call and no cost.
        explanation = explanations.render(span, block.text, lang)
        layout.addWidget(muted(t("detail_why_header", lang)))
        why_label = QLabel(explanation.as_text())
        why_label.setWordWrap(True)
        why_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(why_label)

        # `suppression.py` already lowers the score and drops the reasons the
        # user ruled out before this panel ever sees the span
        # (`details["suppressed"]`); what was missing was saying so here -
        # otherwise a lowered score with no visible cause reads as the
        # detector being unsure, not as a decision the user already made.
        if (span.details or {}).get("suppressed"):
            note = muted(_SUPPRESSED_NOTE)
            note.setProperty("class", theme.CLASS_MUTED)
            layout.addWidget(note)

        edit_box = QTextEdit()
        edit_box.setPlainText(self.drafts.get(key, original))
        edit_box.setPlaceholderText(t("replace_placeholder", lang))
        edit_box.setMaximumHeight(120)
        layout.addWidget(edit_box)

        if explanation.suggestion is not None:
            layout.addWidget(muted(t("detail_suggestion_header", lang)))
            suggestion_view = QLabel(
                explanation.suggestion if explanation.suggestion
                else t("suggest_delete", lang)
            )
            suggestion_view.setWordWrap(True)
            suggestion_view.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            layout.addWidget(suggestion_view)
            use_btn = QPushButton(t("detail_use_suggestion", lang))
            # Fills the draft box rather than applying anything: the offline
            # suggestion is a starting point the user still edits and saves,
            # exactly like a model-generated one.
            use_btn.clicked.connect(
                lambda _=False, text=explanation.suggestion: edit_box.setPlainText(text)
            )
            layout.addWidget(use_btn)
        layout.addWidget(muted(explanation.suggestion_note))

        btn_row = QHBoxLayout()
        save_btn = QPushButton(t("replace_save", lang))
        save_btn.setProperty("class", theme.CLASS_PRIMARY)
        save_btn.setToolTip(t("replace_save", lang))
        analyze_btn = QPushButton(t("detail_analyze_button", lang))
        analyze_btn.setToolTip(t("detail_analyze_tooltip", lang))
        refactor_btn = QPushButton(t("detail_refactor_button", lang))
        refactor_btn.setToolTip(t("detail_refactor_tooltip", lang))
        ignore_btn = self._build_ignore_button(
            lambda: self._on_ignore_span_clicked(span, block))
        btn_row.addWidget(save_btn)
        btn_row.addWidget(analyze_btn)
        btn_row.addWidget(refactor_btn)
        btn_row.addWidget(ignore_btn)
        layout.addLayout(btn_row)

        note = muted(t("replace_note", lang) if not is_repo_block else "")
        layout.addWidget(note)

        save_btn.clicked.connect(lambda: self._save_draft(key, edit_box.toPlainText()))
        analyze_btn.clicked.connect(lambda: self._run_additional_analysis(block, span))
        refactor_btn.clicked.connect(lambda: self._run_refactor(edit_box.toPlainText(), block, edit_box))

        return w

    # ------------------------------------------------------------- actions

    def _save_draft(self, key: tuple, text: str) -> None:
        self.drafts[key] = text
        for i in range(self.flagged_list.count()):
            item = self.flagged_list.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            if not data:
                continue
            _kind, span, block = data
            if (span.block_id, span.start, span.end) == key:
                current = item.text()
                if not current.startswith("✎ "):
                    item.setText("✎ " + current)

    def _run_additional_analysis(self, block, span: TextSpan) -> None:
        detector_name, detector_config = self._detector_for_request()
        self.status_bar.showMessage(t("detail_analyzing", self.lang))

        worker = SingleBlockWorker(block, detector_name, detector_config)
        worker.finished_ok.connect(lambda spans: self._on_additional_analysis_done(block, detector_name, spans))
        worker.failed.connect(self._on_failed)
        worker.finished.connect(lambda: self.status_bar.showMessage(t("status_idle", self.lang)))
        self._track_worker(worker)
        worker.start()

    def _on_additional_analysis_done(self, block, detector_name: str, spans: list[TextSpan]) -> None:
        if not self.result:
            return
        self.result.spans = [
            s for s in self.result.spans
            if not (s.block_id == block.block_id and s.detector_name == detector_name)
        ]
        self.result.spans.extend(spans)
        self._populate_flagged_list()
        self._update_repo_buttons_enabled()

    def _run_refactor(self, draft_text: str, block, edit_box=None) -> None:
        """Rewrite this one passage through the configured provider and drop
        the result straight into the edit box, so it can be reviewed and
        adjusted before anything is saved or written to disk."""
        source_text = draft_text.strip() or block.text
        self.status_bar.showMessage(t("detail_analyzing", self.lang))

        worker = SingleRewriteWorker(source_text, getattr(block, "language_hint", None), self.settings)

        def on_ok(result: str) -> None:
            if edit_box is not None:
                edit_box.setPlainText(result)
            self.status_bar.showMessage(t("status_idle", self.lang))

        worker.finished_ok.connect(on_ok)
        worker.failed.connect(self._on_failed)
        self._track_worker(worker)
        worker.start()

    # -------------------------------------------------- repo bulk actions

    def _repo_flagged_items(self) -> list[tuple[CodeBlock, TextSpan]]:
        if not self.result or self.mode != MODE_REPO:
            return []
        blocks_by_id = {b.block_id: b for b in self.result.blocks()}
        items = []
        for span in self.result.spans:
            if span.confidence == Confidence.LOW:
                continue
            block = blocks_by_id.get(span.block_id)
            if block is not None:
                items.append((block, span))
        return items

    def _on_fix_unicode_clicked(self) -> None:
        """Fill in a corrected draft for every non-keyboard character found.

        Entirely local: the replacement for each character is fixed by the
        rule table, so there's no model call, no cost, and no waiting. In
        repo mode the drafts then flow into "Auto-replace in files" like
        any other; in web mode they're drafts to copy out.
        """
        spans = self._unicode_spans()
        if not spans:
            return
        blocks_by_id = {b.block_id: b for b in self.result.blocks()}
        filled = 0
        for span in spans:
            block = blocks_by_id.get(span.block_id)
            if block is None or span.replacement is None:
                continue
            # Use the correction the detector already worked out. It knew the
            # surrounding word; this code does not, and recomputing it from
            # the isolated span would turn homoglyph fixes into no-ops.
            original = block.text[span.start:span.end]
            if span.replacement != original:
                self.drafts[(block.block_id, span.start, span.end)] = span.replacement
                filled += 1
        self._populate_flagged_list()
        self._update_repo_buttons_enabled()
        QMessageBox.information(self, "", t("unicode_fixed_summary", self.lang, n=filled))

    def _on_generate_list_clicked(self) -> None:
        self._run_bulk_rewrite(auto_replace=False)

    def _on_auto_replace_clicked(self) -> None:
        items = self._repo_flagged_items()
        if not items:
            return
        message = t("confirm_auto_replace", self.lang, n=len(items))
        # Rewriting a comment is a different decision from rewriting a
        # heading, so the confirmation says how many of each are in the batch
        # rather than presenting one undifferentiated count.
        comments = sum(1 for b, _ in items if getattr(b, "kind", "") == "technical")
        if comments:
            message += "\n\n" + t("confirm_auto_replace_technical", self.lang, n=comments)
        reply = QMessageBox.question(self, "", message)
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._run_bulk_rewrite(auto_replace=True)

    def _run_bulk_rewrite(self, auto_replace: bool) -> None:
        items = self._repo_flagged_items()
        if not items:
            return
        missing = [(b, s) for (b, s) in items if (b.block_id, s.start, s.end) not in self.drafts]

        if not missing:
            self._after_bulk_rewrite({}, auto_replace)
            return

        # Fail here, before spending anything, if the configured provider
        # can't actually be used — otherwise the first of N billable calls
        # is what tells the user they're not signed in.
        try:
            import rewriter
            provider = rewriter.build_provider(self.settings)
            status = provider.auth_status()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "", str(exc))
            return
        if not status.signed_in:
            QMessageBox.warning(
                self, "",
                t("settings_not_signed_in", self.lang, detail=status.detail)
                + "\n\n" + t("settings_button", self.lang),
            )
            return

        self.generate_list_btn.setEnabled(False)
        self.auto_replace_btn.setEnabled(False)
        worker = RewriteAllWorker(missing, self.settings)
        worker.progress.connect(
            lambda done, total: self.status_bar.showMessage(t("rewriting_status", self.lang, done=done, total=total))
        )
        worker.finished_ok.connect(lambda results: self._after_bulk_rewrite(results, auto_replace))
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_rewrite_worker_finished)
        self._rewrite_worker = worker
        self._track_worker(worker)
        self.cancel_btn.setEnabled(True)
        worker.start()

    def _on_rewrite_worker_finished(self) -> None:
        self.generate_list_btn.setEnabled(True)
        self.auto_replace_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.status_bar.showMessage(t("status_idle", self.lang))

    def _after_bulk_rewrite(self, results: dict, auto_replace: bool) -> None:
        for key, text in results.items():
            self.drafts[key] = text
        self._populate_flagged_list()
        if auto_replace:
            self._do_auto_replace()
        else:
            self._offer_export_list()

    def _do_auto_replace(self) -> None:
        if not self.result:
            return
        blocks_by_id = {b.block_id: b for b in self.result.blocks()}
        plans = build_plans(blocks_by_id, self.result.spans, self.drafts)
        result = apply_replacements(plans)
        QMessageBox.information(
            self, "",
            t("auto_replace_summary", self.lang,
              applied=result.passages_applied, files=len(result.files_changed),
              stale=len(result.passages_skipped_stale), errors=len(result.errors)),
        )
        self._refresh_repo_raw_text_after_write(result.files_changed)

    def _refresh_repo_raw_text_after_write(self, changed_files: list[str]) -> None:
        if not self.result or not isinstance(self.result, RepoAnalysisResult):
            return
        changed = set(changed_files)
        for f in self.result.files:
            if f.path in changed:
                try:
                    with open(f.path, "r", encoding="utf-8") as fh:
                        f.raw_text = fh.read()
                except OSError:
                    pass
        if self.current_preview_path in changed:
            f = next((f for f in self.result.files if f.path == self.current_preview_path), None)
            if f is not None and f.raw_text is not None:
                self.code_view.setPlainText(f.raw_text)

    def _offer_export_list(self) -> None:
        reply = QMessageBox.question(self, "", t("export_list_prompt", self.lang))
        if reply != QMessageBox.StandardButton.Yes:
            return
        path, _ = QFileDialog.getSaveFileName(self, "", "xanalyze-review.md", "Markdown (*.md)")
        if not path:
            return
        self._export_list_to_file(path)
        QMessageBox.information(self, "", t("export_list_saved", self.lang, path=path))

    def _export_list_to_file(self, path: str) -> None:
        if not self.result:
            return
        blocks_by_id = {b.block_id: b for b in self.result.blocks()}
        lines = ["# AI content review list", ""]
        for span in sorted(self.result.spans, key=lambda s: -s.score):
            if span.confidence == Confidence.LOW:
                continue
            block = blocks_by_id.get(span.block_id)
            if block is None:
                continue
            key = (block.block_id, span.start, span.end)
            original = block.text[span.start:span.end]
            draft = self.drafts.get(key, "")
            location = (
                f"{block.file_path}:{block.line_number}" if isinstance(block, CodeBlock)
                else block.page_url
            )
            lines.append(f"## {location} ({span.confidence.value}, {span.score:.2f})")
            lines.append("")
            lines.append(f"- original: {original}")
            lines.append(f"- suggested: {draft}")
            lines.append("")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
