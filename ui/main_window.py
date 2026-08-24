from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QColor, QIcon, QKeySequence, QShortcut
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout,
    QFrame, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QSpinBox, QSplitter,
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
    CHECKS, CHECK_ACCESSIBILITY, CHECK_AI_PATTERNS, METHOD_AI, METHOD_EMBEDDING, METHOD_LOCAL,
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
from ui.window_parts.account import (
    AccountMixin, _UNASKED, _ask_account_later,
)
from ui.window_parts.audit_panel import AuditPanelMixin
from ui.window_parts.bulk_rewrite import BulkRewriteMixin
from ui.window_parts.report_export import (
    ReportExportMixin, _styled_report_text,
)
from ui.window_parts.findings_panel import FindingsPanelMixin
from ui.window_parts.runs_panel import RunsPanel
from ui.window_parts.shared import (
    MODE_AUDIT, MODE_FILE, MODE_REPO, MODE_WEB, _SEVERITY_BADGE,
    _SEVERITY_CONFIDENCE, _SUPPRESSED_NOTE, _browser_url,
)
from ui.widgets import (
    ROW_ROLE, EmptyState, FindingDelegate, FlowLayout, RowData, chip,
    diagnostics_message, divider, field, heading, muted, panel, restyle,
)
from ui.worker import (
    AnalysisWorker, RepoAnalysisWorker, RewriteAllWorker,
    SingleBlockWorker, SingleRewriteWorker,
)

#: How many characters a combo in the controls column reserves room for.
#: Every combo uses the same number: a column where each dropdown is a
#: different width reads as misalignment rather than as information, and the
#: longest label ("Claude Code session") does not have to fit - the popup
#: shows it in full.
_COMBO_CHARS = 10

#: Width of the controls column. Wide enough that a URL field and a
#: provider name are both readable without abbreviation, narrow enough to
#: leave a three-column body room at 1300px - the window's default width.
SIDEBAR_WIDTH = 268

#: What the column shrinks to once the body has folded to a single column.
#: At that point the window is being used as a list of findings, and a
#: full-width form beside it would leave the list unusable.
SIDEBAR_WIDTH_NARROW = 200

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

# Translated like everything else now. It was hardcoded English, with a
# comment explaining that the translations file belonged to someone else at
# the time - so the one button on the detail card that was not in the user's
# language sat next to eight that were.


class MainWindow(AccountMixin, AuditPanelMixin, FindingsPanelMixin,
                 ReportExportMixin, BulkRewriteMixin, RunsPanel,
                 QMainWindow):
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
        # The run's state - which request ran, and which documents its fetch
        # produced - lives on the view model and is read from there through
        # the properties below. It used to be duplicated here, and the copy
        # on this side was never written to: `analyze()` records the request
        # on the view model, so the window's `_last_request` stayed None for
        # the life of the process. Three visible consequences, all reported
        # as separate faults: an audit's findings never appeared in a
        # both-questions run (the list gated them on this value), the browser
        # pass never ran (`_on_audit_finished` gates on it too), and the
        # extraction cache never hit, so changing the question re-crawled the
        # whole site. One owner instead.

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
        self._sync_choices_to_state()
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
        self.checks_combo.currentIndexChanged.connect(self._on_checks_to_state)
        self.method_combo.currentIndexChanged.connect(self._on_method_to_state)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_to_state)

        # -- fields -> AppState --
        # As they are edited, not only when Analyze is pressed. The state was
        # pushed once, inside `_on_analyze_clicked`, so until the first run
        # `AppState.target` was empty - and anything that asked the view
        # model what the current request was got a request for nothing. That
        # is what made the extraction cache never match: the window compared
        # a request with a target against one without.
        for field_widget in (self.url_edit, self.repo_path_edit,
                             self.file_path_edit):
            field_widget.textChanged.connect(self._sync_target_to_state)
        self.depth_spin.valueChanged.connect(self.app_state.set_depth)
        self.scope_combo.currentIndexChanged.connect(self._sync_scope_to_state)

        # -- AppState -> UI updates --
        self.app_state.any_changed.connect(self._apply_mode_visibility)
        self.app_state.any_changed.connect(self._sync_source_from_state)
        # The account is asked for after the window is on screen, so the
        # answer arrives later than the combo that depends on it. Rebuilt when
        # it does; before this, an account found at startup did not add the AI
        # entries until the user signed in and out again.
        self.app_state.ai_available_changed.connect(
            lambda _ready: self._retranslate_choices())

        # -- ViewModel -> UI updates --
        self.view_model.busy_changed.connect(self._on_busy_changed)
        self.view_model.buttons_changed.connect(self._update_repo_buttons_enabled)
        self.view_model.error.connect(self._on_vm_error)
        self.view_model.status_message.connect(self.status_bar.showMessage)
        self.view_model.web_result_ready.connect(self._on_vm_web_result)
        self.view_model.repo_result_ready.connect(self._on_vm_repo_result)
        self.view_model.audit_result_ready.connect(self._on_vm_audit_result)
        self.view_model.rewrite_ready.connect(self._on_rewrite_finished)
        self.view_model.browser_pass_needed.connect(self._run_browser_pass)
        self.view_model.fix_confirm_needed.connect(self._on_fix_confirm_needed)
        self.view_model.fix_outcome.connect(self._on_fix_outcome)
        self.view_model.undo_outcome.connect(self._on_undo_outcome)
        self.view_model.download_choice_needed.connect(self._on_download_choice_needed)
        self.view_model.unicode_fixed.connect(self._on_unicode_fixed)

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
            # The target belongs to the source: switching from a site to a
            # folder means the state must now hold the folder's path, not the
            # URL still sitting in the other field.
            self._sync_target_to_state()

    def _sync_choices_to_state(self) -> None:
        """Push what the combos currently show into the state, once.

        `_fill_combo` blocks signals while it rebuilds - otherwise every
        refill would look like a user choice - so the first fill of the
        session never reached `AppState`. The state then answered with its own
        constructor defaults, and "both questions", which is what the combo
        showed, became "AI patterns only", which is what actually ran.
        """
        self._on_mode_to_state(0)
        self._on_checks_to_state(0)
        self._on_method_to_state(0)
        self._on_provider_to_state(0)
        self._sync_target_to_state()
        self._sync_scope_to_state()
        self.app_state.set_depth(self.depth_spin.value())

    def _sync_target_to_state(self, _text: str = "") -> None:
        self.app_state.set_target(self._current_target())

    def _sync_scope_to_state(self, _idx: int = 0) -> None:
        self.app_state.set_scope(self._repo_scope())

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
        field.style().unpolish(field)
        field.style().polish(field)
        self.status_bar.showMessage(message)

    def _clear_field_error(self, field: QLineEdit) -> None:
        """Clear error highlight when user types."""
        field.setProperty("class", "")
        field.style().unpolish(field)
        field.style().polish(field)
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
        # Four things in one row need about 500px; the column has 268. So the
        # header stacks: the mark and the name on one line, then the tagline,
        # then the account. Each of those wraps rather than clipping - a
        # tagline cut mid-word is worse than a tagline on two lines.
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(self.palette_tokens.space_1)

        title_row = QWidget()
        title_layout = QHBoxLayout(title_row)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(self.palette_tokens.space_sm)

        mark = ASSETS / ("logo-dark.svg" if theme.resolve_mode(self.settings.theme) == "dark"
                         else "logo-light.svg")
        if mark.is_file():
            self.brand_mark = QSvgWidget(str(mark))
            self.brand_mark.setFixedSize(QSize(22, 22))
            title_layout.addWidget(self.brand_mark)
        else:
            self.brand_mark = None

        self.brand_name = QLabel("XAnalyze")
        self.brand_name.setProperty("class", theme.CLASS_HEADING)
        title_layout.addWidget(self.brand_name)
        title_layout.addStretch(1)
        layout.addWidget(title_row)

        self.brand_tagline = muted()
        self.brand_tagline.setWordWrap(True)
        layout.addWidget(self.brand_tagline)

        # Account state belongs where it can be seen. It used to live inside
        # the settings dialog, which meant the one fact that decides whether
        # the AI assessment is available at all was three clicks away and
        # invisible from the window that offers it.
        account_row = QWidget()
        account_layout = QHBoxLayout(account_row)
        account_layout.setContentsMargins(0, 0, 0, 0)
        account_layout.setSpacing(self.palette_tokens.space_sm)
        self.account_label = muted()
        self.account_label.setWordWrap(True)
        account_layout.addWidget(self.account_label, stretch=1)
        self.account_btn = QPushButton()
        self.account_btn.clicked.connect(self._on_account_clicked)
        account_layout.addWidget(self.account_btn)
        layout.addWidget(account_row)
        # Drawn from what is known, which at build time is nothing. The real
        # answer is asked once the window exists; see `_ask_account_later`.
        self._refresh_account_control(ask=False)
        return bar

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
        # A left column of controls beside the results, not a strip of them
        # above. Every control is the same object it was as a toolbar - the
        # panels, the mixins and the tests all address these widgets by name -
        # only the geometry changed: a form reads top to bottom, and a row
        # that has to wrap to fit eleven controls reads in no direction at
        # all. The sidebar also gives each control room for its label, which
        # the wrapping row could only afford by abbreviating them away.
        root = QHBoxLayout(central)
        gap = self.palette_tokens.space_md
        root.setContentsMargins(gap, gap, gap, gap)
        root.setSpacing(gap)

        # The controls live on their own surface rather than floating on the
        # page canvas — the same "monolithic card on a warm canvas" the web
        # app uses to separate chrome from content.
        self.toolbar = QWidget()
        self.toolbar.setProperty("class", theme.CLASS_TOOLBAR)
        self.toolbar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        controls = QVBoxLayout(self.toolbar)
        controls.setContentsMargins(gap, gap, gap, gap)
        controls.setSpacing(self.palette_tokens.space_sm)

        # A header strip with the mark and the product name. Not decoration:
        # this is one application in a family, and the thing that says so at a
        # glance is the mark, in the same indigo, in the same place as the web
        # app puts it.
        controls.addWidget(self._build_brand_header())

        self.mode_label = QLabel()
        self.mode_combo = QComboBox()
        self.mode_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.mode_combo.setMinimumContentsLength(_COMBO_CHARS)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        # --- web-mode controls ---
        # Stacked, not in a row. Four controls side by side need about 520px
        # to stay readable, which is twice the column's width - the row fitted
        # only by squeezing the URL field down to a few characters.
        web_controls = QWidget()
        web_layout = QVBoxLayout(web_controls)
        web_layout.setContentsMargins(0, 0, 0, 0)
        web_layout.setSpacing(self.palette_tokens.space_1)
        self.url_label = QLabel()
        self.url_edit = QLineEdit()
        self.url_edit.textChanged.connect(lambda: self._clear_field_error(self.url_edit))
        self.depth_label = QLabel()
        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(0, 5)
        self.depth_spin.setValue(self.settings.crawl_depth)
        for w in (self.url_label, self.url_edit, self.depth_label, self.depth_spin):
            web_layout.addWidget(w)
        self.url_error = muted()
        self.url_error.setProperty("class", "field-error")
        self.url_error.setVisible(False)

        # --- repo-mode controls ---
        repo_controls = QWidget()
        repo_layout = QVBoxLayout(repo_controls)
        repo_layout.setContentsMargins(0, 0, 0, 0)
        repo_layout.setSpacing(self.palette_tokens.space_1)
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
        self.scope_combo.setMinimumContentsLength(_COMBO_CHARS)
        self.scope_combo.currentIndexChanged.connect(self._on_scope_changed)
        repo_layout.addWidget(self.repo_path_edit)
        # These two are short and belong together - the only pair worth a row.
        repo_buttons = QWidget()
        repo_buttons_layout = QHBoxLayout(repo_buttons)
        repo_buttons_layout.setContentsMargins(0, 0, 0, 0)
        repo_buttons_layout.setSpacing(self.palette_tokens.space_1)
        repo_buttons_layout.addWidget(self.browse_btn)
        repo_buttons_layout.addWidget(self.exclusions_btn)
        repo_layout.addWidget(repo_buttons)
        repo_layout.addWidget(self.scope_label)
        repo_layout.addWidget(self.scope_combo)
        self.repo_error = muted()
        self.repo_error.setProperty("class", "field-error")
        self.repo_error.setVisible(False)

        # --- single-file controls ---
        file_controls = QWidget()
        file_layout = QVBoxLayout(file_controls)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(self.palette_tokens.space_1)
        self.file_path_edit = QLineEdit()
        self.file_path_edit.textChanged.connect(lambda: self._clear_field_error(self.file_path_edit))
        self.file_browse_btn = QPushButton()
        self.file_browse_btn.clicked.connect(self._on_browse_file_clicked)
        file_layout.addWidget(self.file_path_edit)
        file_layout.addWidget(self.file_browse_btn)
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
        self.provider_combo.setMinimumContentsLength(_COMBO_CHARS)
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
        # Reader combo hidden - auto-determined by source
        self.reader_label = QLabel()
        self.reader_label.setVisible(False)
        self.reader_combo = QComboBox()
        self.reader_combo.setVisible(False)
        self.checks_label = QLabel()
        self.checks_combo = QComboBox()
        self.method_label = QLabel()
        self.method_combo = QComboBox()
        for combo in (self.checks_combo, self.method_combo):
            combo.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(_COMBO_CHARS)
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

        # The sidebar keeps only what changes per scan. Language, API keys and
        # endpoint mapping live in the Settings dialog, which is what stops
        # this column from growing unusable.
        self.source_controls_stack.setMinimumWidth(0)
        self.source_controls_stack.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        for widget in (self.mode_label, self.mode_combo,
                       self.source_controls_stack,
                       self.checks_label, self.checks_combo):
            controls.addWidget(widget)

        # The advanced controls: a container rather than a second row, so
        # showing them extends the column instead of pushing the results
        # down. Same widget, same name, same `setVisible` from
        # `_on_advanced_toggle`.
        self.advanced_row = QWidget()
        adv_layout = QVBoxLayout(self.advanced_row)
        adv_layout.setContentsMargins(0, 0, 0, 0)
        adv_layout.setSpacing(self.palette_tokens.space_sm)
        for w in (self.method_label, self.method_combo,
                  self.provider_label, self.provider_combo):
            adv_layout.addWidget(w)
        self.advanced_row.setVisible(False)

        controls.addWidget(self.advanced_toggle)
        controls.addWidget(self.advanced_row)

        # The catalogue of runs, below the controls and above the buttons:
        # it is about work that already happened, so it must not sit between
        # the target and Analyze, and it must not be the thing that scrolls
        # off the bottom either.
        controls.addWidget(self._build_runs_panel())
        controls.addStretch(1)
        controls.addWidget(self.analyze_btn)
        controls.addWidget(self.cancel_btn)
        controls.addWidget(self.settings_btn)
        self.analyze_btn.setProperty("class", theme.CLASS_PRIMARY)

        # Scrolled, because the column's content grows: the advanced block,
        # the repository fields and a long provider list together are taller
        # than a laptop window in its smallest usable size, and controls that
        # fall off the bottom of a fixed column cannot be reached at all.
        self.sidebar_scroll = QScrollArea()
        self.sidebar_scroll.setWidgetResizable(True)
        self.sidebar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        # Both scrollbars are allowed rather than suppressed, and that is
        # what keeps the window resizable. With `widgetResizable` on, a
        # scroll area that may not scroll horizontally inherits its
        # content's minimum width as its own - so a fixed-width column of
        # combos raised the *window's* minimum width and the narrow layout
        # became unreachable, taking the responsive fold with it.
        self.sidebar_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.sidebar_scroll.setWidget(self.toolbar)
        # Max, not fixed: the column keeps its comfortable width whenever
        # there is room and gives way when there is not.
        self.sidebar_scroll.setMinimumWidth(0)
        self.sidebar_scroll.setSizePolicy(QSizePolicy.Policy.Preferred,
                                          QSizePolicy.Policy.Expanding)

        # --- controls column beside the body -----------------------------------
        #
        # A splitter rather than two items in the box layout, for two
        # reasons. A box layout gives a non-stretching child exactly its
        # size hint, so the column came out at whatever width its widgets
        # happened to need (184px) instead of the width it was designed for -
        # and forcing the hint up with a minimum width raised the *window's*
        # minimum width with it, which is what made the narrow layout
        # unreachable the first time. A splitter takes an explicit size,
        # squeezes to a child's minimum when the window shrinks, and lets
        # someone widen the column if they want to see a long path in full.
        self.body_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.body_splitter.setHandleWidth(gap)
        self.body_splitter.addWidget(self.sidebar_scroll)
        root.addWidget(self.body_splitter, stretch=1)

        # --- three-column body -------------------------------------------------
        self.columns_splitter = QSplitter(Qt.Orientation.Horizontal)
        # A gap between the zones, not a seam: panels that touch read as one
        # wide panel with lines drawn in it, which is exactly the flat-sheet
        # look the surfaces exist to avoid.
        self.columns_splitter.setHandleWidth(gap)
        self.columns_splitter.setChildrenCollapsible(False)
        self.body_splitter.addWidget(self.columns_splitter)
        # The controls column keeps its width; everything else goes to the
        # body. Index 1 is the only stretching child, so widening the window
        # widens the results rather than the form.
        self.body_splitter.setStretchFactor(0, 0)
        self.body_splitter.setStretchFactor(1, 1)
        self.body_splitter.setSizes([SIDEBAR_WIDTH, 1000])

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
        # A panel with a head, like the other two columns. It was a bare
        # widget, so its contents floated directly on the page canvas while
        # its neighbours sat on titled surfaces - which read as a column that
        # had failed to render rather than as a third zone.
        self.col3, self.detail_layout, self.detail_header = panel()
        self.detail_layout.setContentsMargins(0, 0, 0, 0)
        self.detail_layout.setSpacing(0)
        self.columns_splitter.addWidget(self.col3)

        self.columns_splitter.setSizes([450, 380, 380])

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self._apply_mode_visibility()
        # A blank white pane is the one thing the empty state exists to
        # prevent, and it was exactly what the window opened with: the state
        # was only ever shown after a scan produced no rows, never before the
        # first scan.
        self._show_empty_state()

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
        self.detail_header.setText(t("detail_header", lang))
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
        # The controls column narrows with the body. A fixed 268px form
        # beside a single 350px findings list is a window where neither half
        # works.
        wanted = SIDEBAR_WIDTH if medium else SIDEBAR_WIDTH_NARROW
        self.body_splitter.setSizes(
            [wanted, max(1, self.width() - wanted - self.palette_tokens.space_md)])
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

    # The combos are the input device; `AppState` is the answer. Reading the
    # widget here as well gave the window a second opinion about what the
    # user had chosen, and the two were compared against each other.

    def _chosen_checks(self) -> tuple:
        return self.app_state.checks

    def _chosen_readers(self) -> tuple:
        return self.app_state.readers

    def _chosen_methods(self) -> tuple:
        return self.app_state.methods

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
        """The run the current choices describe.

        Delegated: the view model builds this from `AppState`, and a second
        builder here - reading the combos directly - meant the window and the
        view model could describe different runs at the same moment. They
        did, and comparing one against the other is what stopped the
        extraction cache from ever matching.
        """
        return self.view_model.current_request()

    def _current_target(self) -> str:
        if self.source == SOURCE_REPO:
            return self.repo_path_edit.text().strip()
        if self.source == SOURCE_FILE:
            return self.file_path_edit.text().strip()
        return self.url_edit.text().strip()

    # ------------------------------------------- run state, owned elsewhere
    #
    # Read-only views onto the view model. The window needs these values -
    # the findings list asks whether the run wanted an audit, the audit
    # handler asks whether it wanted a browser - but it must not hold a
    # second copy of them. See the note in `__init__`.

    @property
    def _last_request(self):
        """The request that actually ran, or None before the first run."""
        return self.view_model._last_request

    @property
    def _extraction_request(self):
        return self.view_model._extraction_request

    @property
    def _cached_pages(self):
        return self.view_model._cached_pages

    @property
    def _cached_files(self):
        return self.view_model._cached_files

    @property
    def _cached_scope(self):
        return self.view_model._cached_scope

    def _reusable_pages(self):
        """Pages an earlier run already fetched for this exact target, or None.

        This is the payoff of separating the axes: changing the question or the
        judge used to mean crawling the site again, which is the slowest
        possible way to answer a question about pages already on this machine.
        """
        return self.view_model._reusable_pages()

    def _reusable_files(self):
        """The repository counterpart, with one extra condition.

        The scope decides what is extracted at all - copy, comments, or both -
        so a changed scope is a changed extraction and cannot be reused.
        """
        return self.view_model._reusable_files()

    def _remember_extraction(self, request, *, pages=None, files=None,
                             scope=None) -> None:
        self.view_model._remember_extraction(request, pages=pages, files=files,
                                             scope=scope)

    def _forget_extraction(self) -> None:
        """Drop the cache. Called when the source or the target changes: those
        are the two things the cached documents *are*."""
        self.view_model.forget_extraction()

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

        ai_ready = self.app_state.ai_available
        method_options = [
            (t("method_local", lang), self.choice_key((METHOD_LOCAL,))),
            (t("method_embedding", lang), self.choice_key((METHOD_EMBEDDING,))),
        ]
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
        for edit in (self.url_edit, self.repo_path_edit, self.file_path_edit):
            self._clear_field_error(edit)

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
        elif request.wants_embedding:
            name = "embedding"
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
        if resolved == "embedding":
            # Embedding detector uses sentence-transformers, no API key needed
            return {}
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
        button = QPushButton(t("ignore_finding", self.lang))
        button.setToolTip(t("ignore_finding_hint", self.lang))
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
        practices. Reached from the re-audit after a fix (see
        `ui.window_parts.report_export`); the first audit of a run goes
        through the view model. Both build the worker with the same function,
        because when they built it separately they were separately wrong -
        see `ui.worker.audit_worker_for`."""
        from ui.worker import audit_worker_for

        worker, refusal = audit_worker_for(
            self.source,
            target=self._current_target(),
            depth=self.depth_spin.value(),
            max_pages=self.settings.max_pages,
            pages=self._reusable_pages() if self.source == SOURCE_SITE else None,
            ignore_patterns=self.repo_ignore_patterns,
            settings=self.settings,
        )
        if worker is None:
            QMessageBox.warning(self, "", self._missing_target_message()
                                if refusal == "no_target"
                                else t("url_label_full", self.lang))
            return

        self.audit_result = None
        self._reset_scan_ui()
        self.worker = worker
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

    # -- ViewModel signal handlers -----------------------------------------
    def _on_fix_confirm_needed(self, ready_count: int, pending_count: int) -> None:
        answer = QMessageBox.question(
            self, t("fix_on_disk_button", self.lang),
            t("fix_confirm_body", self.lang, ready=ready_count, pending=pending_count),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return
        use_ai = answer == QMessageBox.StandardButton.Yes
        self.view_model.apply_fix_with_ai(use_ai)

    def _on_fix_outcome(self, message: str, written_by_model: list) -> None:
        QMessageBox.information(self, t("fix_on_disk_button", self.lang), message)
        self._reaudit_after_fix()

    def _on_undo_outcome(self, message: str) -> None:
        QMessageBox.information(self, t("undo_fix_button", self.lang), message)
        self._reaudit_after_fix()

    def _on_download_choice_needed(self, has_audit: bool, has_text: bool) -> None:
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
        box.setDefaultButton(styled)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is styled:
            self._on_styled_report_clicked()
        elif clicked is agent:
            self._on_export_report_clicked()

    def _on_unicode_fixed(self, filled: int) -> None:
        self._populate_flagged_list()
        self._update_repo_buttons_enabled()
        QMessageBox.information(self, "", t("unicode_fixed_summary", self.lang, n=filled))
