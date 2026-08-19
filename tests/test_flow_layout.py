"""A row that wraps, checked at several widths.

The bug this replaces was not cosmetic: a row that cannot wrap answers "not
enough width" by clipping its children, so the toolbar's labels vanished and
the findings column could not be narrowed past the sum of its chips.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget
    from ui.widgets import FlowLayout
except Exception:  # noqa: BLE001
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 not available")
class Wrapping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _host(self, labels):
        host = QWidget()
        layout = FlowLayout(host, spacing=6)
        for text in labels:
            layout.addWidget(QLabel(text))
        return host, layout

    def test_a_narrow_width_costs_height_instead_of_content(self):
        _host, layout = self._host(["image-alt", "axe-core", "line 42",
                                    "serious", "also found by htmlcs"])
        wide = layout.heightForWidth(900)
        narrow = layout.heightForWidth(200)
        self.assertGreater(narrow, wide)

    def test_the_minimum_width_is_the_widest_item_not_their_sum(self):
        _host, layout = self._host(["short", "a rather longer chip label here"])
        widest = max(layout.itemAt(i).sizeHint().width()
                     for i in range(layout.count()))
        total = sum(layout.itemAt(i).sizeHint().width()
                    for i in range(layout.count()))
        self.assertLess(layout.minimumSize().width(), total)
        self.assertGreaterEqual(layout.minimumSize().width(), widest)

    def test_items_of_different_heights_are_centred_on_their_line(self):
        host = QWidget()
        layout = FlowLayout(host, spacing=6)
        label = QLabel("Method:")
        button = QPushButton("a taller control")
        layout.addWidget(label)
        layout.addWidget(button)
        host.resize(600, layout.heightForWidth(600))
        host.show()
        self.app.processEvents()
        # Centres within a pixel: an odd height difference rounds down.
        self.assertLessEqual(
            abs((label.y() + label.height() / 2)
                - (button.y() + button.height() / 2)), 1.0)

    def test_a_hidden_widget_takes_no_room(self):
        host, layout = self._host(["one", "two", "three"])
        host.resize(400, 100)
        host.show()
        self.app.processEvents()
        before = layout.itemAt(2).widget().x()
        layout.itemAt(1).widget().hide()
        host.resize(401, 100)  # force a re-layout
        self.app.processEvents()
        self.assertLess(layout.itemAt(2).widget().x(), before)


if __name__ == "__main__":
    unittest.main()
