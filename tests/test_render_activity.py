"""The watchdog stops on the absence of progress, not on elapsed time.

Both of this project's earlier answers were wrong in the same way. A fixed
30s ceiling killed a 158-page report that finishes in 108 seconds and cost a
46-minute run its entire output; removing the ceiling let a wedged render
hang the writer with nothing in any log. Neither measured whether the render
was working, because elapsed time cannot.

The tests below are about that distinction, so they drive the decision
directly with a fake clock and a fake process rather than through Qt: the
part worth testing is "what counts as progress", and needing a
`QApplication` to ask would mean it was not testable at all.
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from report import activity
from report.activity import (
    ActivityWatch, RenderProcessGone, Stalled, parse_cputime,
)


class ParseCpuTime(unittest.TestCase):
    """`ps` prints three different shapes depending on the platform."""

    def test_darwin_centiseconds(self):
        self.assertAlmostEqual(parse_cputime(" 0:01.75 "), 1.75)

    def test_linux_whole_seconds(self):
        self.assertAlmostEqual(parse_cputime("00:12"), 12.0)

    def test_hours_appear_on_a_long_lived_process(self):
        self.assertAlmostEqual(parse_cputime("34:00.31"), 34 * 60 + 0.31)
        self.assertAlmostEqual(parse_cputime("2:05:00"), 2 * 3600 + 300)

    def test_empty_is_not_zero(self):
        """`ps` printing nothing means "not measured", not "did nothing".

        Conflating the two would report a stall the moment `ps` was absent,
        which is the fixed-timer behaviour this module replaces.
        """
        self.assertIsNone(parse_cputime(""))
        self.assertIsNone(parse_cputime("   "))

    def test_garbage_is_not_measured(self):
        self.assertIsNone(parse_cputime("error: no such process"))
        self.assertIsNone(parse_cputime("1:2:3:4"))


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class Progress(unittest.TestCase):
    def setUp(self):
        self.clock = _Clock()
        self.cpu = {"value": 5.0}
        self._real = activity.cpu_seconds
        activity.cpu_seconds = lambda pid: self.cpu["value"]
        self.watch = ActivityWatch(stall_seconds=30.0, clock=self.clock)
        self.watch._pid = 4242
        # What `attach` does: take the first reading, so the first poll
        # compares against something. Without this the first poll is progress
        # by definition, which is right in production and useless in a test.
        self.watch._cpu = self.cpu["value"]
        self.watch.observable = True

    def tearDown(self):
        activity.cpu_seconds = self._real

    def test_a_render_burning_cpu_is_never_stopped(self):
        """The 108-second print, in miniature."""
        for _ in range(200):
            self.clock.advance(1.5)
            self.cpu["value"] += 0.9
            self.assertIsNone(self.watch.poll())

    def test_a_render_burning_cpu_slowly_is_still_not_stopped(self):
        """Linux reports whole seconds; a slow renderer must survive that."""
        for tick in range(100):
            self.clock.advance(1.5)
            if tick % 10 == 0:      # one second of CPU per fifteen elapsed
                self.cpu["value"] += 1.0
            self.assertIsNone(self.watch.poll())

    def test_silence_past_the_window_stops_it(self):
        self.clock.advance(29.0)
        self.assertIsNone(self.watch.poll())
        self.clock.advance(2.0)
        reason = self.watch.poll()
        self.assertIsInstance(reason, Stalled)

    def test_the_reason_names_the_phase_not_a_ceiling(self):
        self.watch.set_phase("printing")
        self.clock.advance(60.0)
        message = str(self.watch.poll())
        self.assertIn("printing", message)
        self.assertIn("CPU time", message)
        self.assertNotIn("timed out", message)

    def test_the_elapsed_time_is_reported_as_silence_not_as_runtime(self):
        self.clock.advance(90.0)
        self.assertIn("90s", str(self.watch.poll()))

    def test_entering_a_phase_counts_as_progress(self):
        """The load's quiet tail must not be charged to the printer."""
        self.clock.advance(29.0)
        self.watch.set_phase("printing")
        self.clock.advance(29.0)
        self.assertIsNone(self.watch.poll())

    def test_load_progress_alone_keeps_it_alive(self):
        self.cpu["value"] = 5.0        # CPU flat: only the signal moves
        for step in range(1, 40):
            self.clock.advance(20.0)
            self.watch.note_progress(step)
            self.assertIsNone(self.watch.poll())

    def test_a_repeated_progress_value_is_not_progress(self):
        for _ in range(4):
            self.clock.advance(20.0)
            self.watch.note_progress(50)   # same value: nothing happened
        self.assertIsInstance(self.watch.poll(), Stalled)


class Unobservable(unittest.TestCase):
    """No pid, or no `ps`: the watch must say so rather than pretend."""

    def setUp(self):
        self.clock = _Clock()
        self._real = activity.cpu_seconds
        activity.cpu_seconds = lambda pid: None
        self.watch = ActivityWatch(stall_seconds=30.0, clock=self.clock)

    def tearDown(self):
        activity.cpu_seconds = self._real

    def test_it_admits_it_could_not_watch_the_process(self):
        self.clock.advance(60.0)
        reason = self.watch.poll()
        self.assertIsInstance(reason, Stalled)
        self.assertIn("could not be watched", str(reason))

    def test_load_progress_still_keeps_it_alive(self):
        """Degraded, not disabled: one signal left is still a signal."""
        for step in range(1, 20):
            self.clock.advance(20.0)
            self.watch.note_progress(step)
            self.assertIsNone(self.watch.poll())

    def test_observable_is_false_and_says_which_claim_was_made(self):
        self.watch.poll()
        self.assertFalse(self.watch.observable)


class DeadRenderProcess(unittest.TestCase):
    def test_a_dead_render_process_stops_the_render_at_once(self):
        watch = ActivityWatch()
        stops = []
        watch._on_stop = stops.append
        watch.set_phase("printing")
        watch._on_render_gone("CrashTermination", 139)
        self.assertEqual(len(stops), 1)
        self.assertIsInstance(stops[0], RenderProcessGone)

    def test_the_reason_carries_the_status_and_the_exit_code(self):
        watch = ActivityWatch()
        watch._on_stop = lambda reason: None
        watch.set_phase("printing")
        watch._on_render_gone("AbnormalTermination", 9)
        message = str(watch.stopped_because)
        self.assertIn("AbnormalTermination", message)
        self.assertIn("9", message)
        self.assertIn("printing", message)

    def test_it_stops_only_once(self):
        """A handler that tears the page down must not be re-entered."""
        watch = ActivityWatch()
        stops = []
        watch._on_stop = stops.append
        watch._on_render_gone("CrashTermination", 1)
        watch._stop_with(Stalled("later"))
        self.assertEqual(len(stops), 1)


class NoProcessToWatch(unittest.TestCase):
    """`cpu_seconds` guards its own inputs, so a missing pid is not a crash."""

    def test_pid_zero_is_not_measured(self):
        self.assertIsNone(activity.cpu_seconds(0))

    def test_a_negative_pid_is_not_measured(self):
        self.assertIsNone(activity.cpu_seconds(-1))

    def test_a_pid_that_does_not_exist_is_not_measured(self):
        self.assertIsNone(activity.cpu_seconds(2 ** 30))

    def test_this_process_is_measurable(self):
        """The mechanism has to work on the machine running the tests.

        Without this, every other test here could pass against a `ps` that
        never answers, and the watch would be running degraded in production
        with nothing to say so.
        """
        self.assertIsNotNone(activity.cpu_seconds(os.getpid()))


class RendererIntegration(unittest.TestCase):
    """A real render, watched, with a window far shorter than a ceiling.

    Two seconds would have failed a 108-second print outright. It passes here
    because the render keeps making progress, which is the whole claim.
    """

    def test_a_real_render_survives_a_two_second_stall_window(self):
        try:
            from report.pdf import PdfRenderer
        except Exception:  # noqa: BLE001 - no Qt here is a skip
            self.skipTest("PySide6 not available")
        html = "<h1>report</h1>" + "".join(
            f"<p>finding {i}: something worth printing</p>" for i in range(400))
        with PdfRenderer(stall_seconds=2.0) as renderer:
            data = renderer.render(html)
        self.assertTrue(data.startswith(b"%PDF-"))

    def test_the_renderer_carries_the_window_it_was_given(self):
        try:
            from report.pdf import PdfRenderer
        except Exception:  # noqa: BLE001
            self.skipTest("PySide6 not available")
        self.assertEqual(PdfRenderer(stall_seconds=7.0).stall_seconds, 7.0)


if __name__ == "__main__":
    unittest.main()
