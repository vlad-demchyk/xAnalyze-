"""The method combo has to decide what actually runs.

This file exists because of one bug, and the bug was not a crash: the window
offered "offline / AI / both", normalised the choice, reported it in the
status bar - and then started every copy pass with whatever detector a
*second* combo happened to name. Choosing AI ran the offline engine and
presented its findings as the model's answer. Nothing failed, so nothing
said anything.

So these tests assert the connection itself, not the shape of the widgets:
what `MainWindow._detector_for_request` hands to the worker, for each method.

Headless: Qt runs on the offscreen platform.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from ui.main_window import MainWindow
    from analysis_modes import (
        AnalysisRequest, CHECK_ACCESSIBILITY, CHECK_AI_PATTERNS, METHOD_AI,
        METHOD_EMBEDDING, METHOD_LOCAL,
    )
    from detectors.judges import JUDGE_BY_PROVIDER
except Exception:  # noqa: BLE001 - no Qt here is a skip, not a failure
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 not available")
class MethodDecidesTheEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()
        # An account is a fact about this machine, not about the choice under
        # test: without pinning it, the request would normalise the AI method
        # away on a machine with nothing signed in, and the test would pass
        # for the wrong reason.
        self.window._ai_available = lambda: True
        # Picking an account in the toolbar writes it to settings, which is
        # the point of the control - but a test run must not edit the config
        # of whoever is running it.
        self.window.settings.save = lambda: None
        self.window._last_request = None
        self.window._retranslate_choices()
        self._select(self.window.checks_combo,
                     (CHECK_ACCESSIBILITY, CHECK_AI_PATTERNS))

    def _select(self, combo, value):
        index = combo.findData(MainWindow.choice_key(value))
        self.assertGreaterEqual(index, 0, f"{value} is not offered")
        combo.setCurrentIndex(index)

    def _select_provider(self, name):
        index = self.window.provider_combo.findData(name)
        self.assertGreaterEqual(index, 0, f"{name} is not offered")
        self.window.provider_combo.setCurrentIndex(index)

    def test_offline_only_runs_the_offline_engine(self):
        self._select(self.window.method_combo, (METHOD_LOCAL,))
        name, _config = self.window._detector_for_request()
        self.assertEqual(name, "offline")

    def test_ai_only_runs_the_judge_of_the_chosen_account(self):
        self._select(self.window.method_combo, (METHOD_AI,))
        for provider, judge in JUDGE_BY_PROVIDER.items():
            with self.subTest(provider=provider):
                self._select_provider(provider)
                name, _config = self.window._detector_for_request()
                self.assertEqual(name, judge)

    def test_hybrid_runs_both_and_carries_the_judge_with_it(self):
        self._select(self.window.method_combo, (METHOD_LOCAL, METHOD_AI))
        self._select_provider("xformat")
        name, config = self.window._detector_for_request()
        self.assertEqual(name, "hybrid")
        self.assertEqual(config["judge_name"], JUDGE_BY_PROVIDER["xformat"])
        # The judge half is configured like any other judge, or an xFormat
        # run would reach the default base URL instead of the chosen one.
        self.assertIn("base_url", config["judge_config"])

    def test_the_ai_method_never_silently_runs_the_offline_engine(self):
        """The regression itself, stated as one assertion."""
        self._select(self.window.method_combo, (METHOD_AI,))
        name, _config = self.window._detector_for_request()
        self.assertNotEqual(name, "offline")

    def test_no_account_is_refused_before_it_is_offered(self):
        """With nothing signed in, the AI entries are not in the combo at
        all - the window does not offer a method it would then substitute."""
        self.window._ai_available = lambda: False
        self.window._retranslate_choices()
        offered = [self.window.method_combo.itemData(i)
                   for i in range(self.window.method_combo.count())]
        self.assertEqual(offered, [
            MainWindow.choice_key((METHOD_LOCAL,)),
            MainWindow.choice_key((METHOD_EMBEDDING,)),
        ])
        self.assertFalse(self.window.method_combo.isEnabled())

    def test_a_stored_ai_method_with_no_account_is_stated_not_swallowed(self):
        """The other way in: a settings file that asks for the model pass on
        a machine that cannot pay for one. The request normalises back to
        offline and records why, which is what the status bar reads out."""
        request = AnalysisRequest(methods=(METHOD_LOCAL, METHOD_AI),
                                  ai_available=False).normalised()
        self.assertNotIn(METHOD_AI, request.methods)
        self.assertTrue(request.notes)

    def test_the_account_is_asked_for_only_when_a_model_reads(self):
        self._select(self.window.method_combo, (METHOD_LOCAL,))
        self.window._apply_mode_visibility()
        self.assertTrue(self.window.provider_combo.isHidden())

        self._select(self.window.method_combo, (METHOD_LOCAL, METHOD_AI))
        self.window._apply_mode_visibility()
        self.assertFalse(self.window.provider_combo.isHidden())

        # ... and not when no copy is judged at all: an accessibility-only
        # run has no text for a model to read.
        self._select(self.window.checks_combo, (CHECK_ACCESSIBILITY,))
        self.window._apply_mode_visibility()
        self.assertTrue(self.window.provider_combo.isHidden())

    def test_choosing_an_account_here_is_the_same_setting_the_dialog_writes(self):
        self._select(self.window.method_combo, (METHOD_AI,))
        self._select_provider("claude-code")
        self.assertEqual(self.window.settings.llm_provider, "claude-code")


if __name__ == "__main__":
    unittest.main()
