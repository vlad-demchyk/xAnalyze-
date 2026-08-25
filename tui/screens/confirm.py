"""A yes/no modal, the one thing no screen in this app has needed before.

`RunScreen` runs a command to completion and shows a result screen - nothing
here has ever paused mid-flight to ask something. A dev-server install
prompt is the first case that does, and it is resolved *before* a run
starts (`FullscanScreen._run_fullscan` checks synchronously, on the UI
thread, before calling `start_run`), not from inside `tui.runner`'s worker -
that worker only ever reports a final result, and giving it a way to ask a
mid-run question would be a much larger change for one dialog.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ConfirmModal(ModalScreen[bool]):
    """Ask a yes/no question; dismiss with the answer.

    `App.push_screen(ConfirmModal(question), callback)` calls `callback`
    with the `True`/`False` this dismisses with - the same mechanism a
    caller would use for any modal result, not something built for this
    dialog specifically.
    """

    def __init__(self, question: str, *, yes_label: str = "Yes",
                no_label: str = "No") -> None:
        super().__init__()
        self._question = question
        self._yes_label = yes_label
        self._no_label = no_label

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-modal"):
            yield Static(self._question, id="confirm-question")
            with Horizontal():
                yield Button(self._yes_label, id="confirm-yes", variant="primary")
                yield Button(self._no_label, id="confirm-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-yes")

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(False)
