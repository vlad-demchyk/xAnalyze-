"""Which files a repository scan found things in, and where they are.

The preview column showed one file at a time and nothing else: whichever
file the selected finding happened to be in, with no way to see that the
twenty-one findings sit in nine files out of four hundred, and no way to go
to a file without first finding a finding that lives there. On a repository
that is the wrong way round. The question is "where is the work
concentrated", and the answer is a shape - three files in `src/components`,
two in `src/locales` - not a scroll position.

So the column becomes the files (artboard 3f), grouped by folder, each with
the number of findings in it, over the code view that was already there.
Selecting a file opens it; the findings list is unchanged.

Files with nothing in them are counted, not listed. Four hundred rows with
a zero beside them is a directory listing, and the one number that matters -
how much of the repository came back clean - is easier to read as a number
than as four hundred rows to scroll past.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from i18n.translations import t
from ui import theme

#: The item data carrying a file's path, so a selection does not have to be
#: parsed back out of the row's text.
PATH_ROLE = Qt.ItemDataRole.UserRole


def _folder_of(path: str) -> str:
    """The folder a file is in, as the design writes it: with a trailing
    slash, and the repository root as an empty string."""
    head, _sep, _tail = path.replace("\\", "/").rpartition("/")
    return f"{head}/" if head else ""


class RepoFilesPanel(QWidget):
    """The files a repository scan found something in, grouped by folder."""

    def __init__(self, palette, lang: str = "en", parent=None):
        super().__init__(parent)
        self.palette_ = palette
        self.lang = lang
        self.counts: dict = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        self.title = QLabel()
        self.title.setProperty("class", theme.CLASS_FIELD_LABEL)
        outer.addWidget(self.title)

        self.tree = QTreeWidget()
        # No frame: it sits inside a panel that already draws the edge, and
        # two rounded rectangles a pixel apart look like a mistake - the
        # same reason `QListWidget` has none.
        self.tree.setFrameShape(QTreeWidget.Shape.NoFrame)
        self.tree.setColumnCount(2)
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setIndentation(12)
        self.tree.setUniformRowHeights(True)
        # A path is longer than this column at every width, and a horizontal
        # scrollbar here would eat a row and widen the column that the whole
        # window's minimum width is measured from.
        self.tree.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # From the right, because the rows people click carry a bare file
        # name and a name is recognised by its head: `ElideLeft` turned
        # `index.html` into `...ex.html`. The folder rows lose their tail
        # instead, which is why they carry the full path on the tooltip.
        self.tree.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.tree.setMinimumWidth(0)
        outer.addWidget(self.tree, stretch=1)

        self.footer = QLabel()
        self.footer.setProperty("class", theme.CLASS_MUTED)
        self.footer.setWordWrap(True)
        outer.addWidget(self.footer)

        self.retranslate(lang)

    # -- content ---------------------------------------------------------

    def retranslate(self, lang: str) -> None:
        self.lang = lang
        self.title.setText(t("repo_files_title", lang))
        self._set_footer()

    def show_result(self, result, flagged_blocks) -> None:
        """`flagged_blocks` is the blocks that actually became findings.

        Passed in rather than recomputed, so this panel counts exactly what
        the findings list shows. Counting `result.spans` here instead would
        put a number on screen that the list beside it does not match - low
        confidence is a finding to one and not to the other.
        """
        self.tree.clear()
        self.counts = {}
        for block in flagged_blocks:
            self.counts[block.file_path] = self.counts.get(block.file_path, 0) + 1

        by_folder: dict = {}
        for path in sorted(self.counts):
            by_folder.setdefault(_folder_of(path), []).append(path)

        for folder in sorted(by_folder):
            parent = QTreeWidgetItem(self.tree, [folder or "/", ""])
            parent.setFirstColumnSpanned(True)
            parent.setFlags(Qt.ItemFlag.ItemIsEnabled)
            parent.setToolTip(0, folder or "/")
            for path in by_folder[folder]:
                name = path.replace("\\", "/").rpartition("/")[2] or path
                child = QTreeWidgetItem(parent, [name, str(self.counts[path])])
                child.setData(0, PATH_ROLE, path)
                child.setToolTip(0, path)
                child.setTextAlignment(1, Qt.AlignmentFlag.AlignRight
                                       | Qt.AlignmentFlag.AlignVCenter)
            parent.setExpanded(True)
        self.tree.resizeColumnToContents(1)

        # The same count the summary strip uses, for the same reason: two
        # denominators on one screen is the window contradicting itself.
        # `files_read` when the walk recorded it, the list's own length
        # otherwise.
        walk = getattr(result, "diagnostics", None) if result is not None else None
        total = (getattr(walk, "files_read", 0) or
                 (len(result.files) if result is not None else 0))
        self._set_footer(clean=max(total - len(self.counts), 0))

    def _set_footer(self, clean: int | None = None) -> None:
        if clean is None:
            clean = getattr(self, "_clean", 0)
        self._clean = clean
        self.footer.setText(t("repo_files_clean", self.lang, count=clean)
                            if clean else "")
        self.footer.setVisible(bool(clean))

    def selected_path(self) -> str:
        item = self.tree.currentItem()
        return item.data(0, PATH_ROLE) or "" if item is not None else ""

    def apply_palette(self, palette) -> None:
        self.palette_ = palette


class RepoFilesMixin:
    """Wiring for the file column. Reads the facade like the other mixins."""

    def _build_repo_files(self) -> QWidget:
        self.repo_files = RepoFilesPanel(self.palette_tokens, self.lang)
        self.repo_files.tree.itemSelectionChanged.connect(
            self._on_repo_file_selected)
        return self.repo_files

    def refresh_repo_files(self) -> None:
        """Recount the file column from the findings the list is showing."""
        from models import Confidence, RepoAnalysisResult

        if not isinstance(self.result, RepoAnalysisResult):
            return
        blocks = {block.block_id: block for block in self.result.blocks()}
        flagged = [blocks[span.block_id] for span in self.result.spans
                   if span.confidence != Confidence.LOW
                   and span.block_id in blocks]
        self.repo_files.show_result(self.result, flagged)

    def _on_repo_file_selected(self) -> None:
        """Open the chosen file in the preview under the list.

        Only the file: no highlight, because nothing has been pointed at
        yet. Highlighting the first finding in it would be the window
        choosing which of six passages the reader meant.
        """
        path = self.repo_files.selected_path()
        if not path or not getattr(self, "result", None):
            return
        found = next((f for f in self.result.files if f.path == path), None)
        if found is None or found.raw_text is None:
            return
        self.current_preview_path = path
        self.code_view.setPlainText(found.raw_text)
