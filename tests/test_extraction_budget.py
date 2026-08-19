"""Extraction has to finish, on any input, in time proportional to its size.

This exists because it once did not. The tag pattern's attribute region was an
alternation whose branches could all match the same character, so a `<` that is
never closed - ordinary in TypeScript, where `<` is also an operator - made the
matcher try every combination before it could fail. One 4 KB component file
turned a seven-second scan into one that never finished, and nothing in the
output said which file or why.

The guard is a budget rather than a pattern review: the shape that caused it is
fixed, and what has to stay true is the property, not the fix.
"""
import time
import unittest

import repo_scanner as rs

#: Generous on purpose. The point is to catch a blow-up, not to police
#: milliseconds on a loaded machine.
BUDGET_SECONDS = 2.0

#: An unclosed tag with attributes that mix quotes and braces - the exact shape
#: JSX produces and the one the old pattern could not fail on quickly.
UNCLOSED = "<Composer prop={a} name='x' " + "attr={value} " * 40


def _time_extraction(text: str) -> float:
    start = time.time()
    rs._extract_blocks(text, "src/Probe.tsx", "content")
    return time.time() - start


class Budget(unittest.TestCase):
    def test_an_unclosed_tag_does_not_stall_the_scan(self):
        self.assertLess(_time_extraction(UNCLOSED), BUDGET_SECONDS)

    def test_generics_and_comparisons_are_cheap(self):
        source = ("function pick<T extends object>(xs: T[]) {\n"
                  "  return xs.filter((x) => count(x) > 2 && count(x) < 9);\n"
                  "}\n") * 200
        self.assertLess(_time_extraction(source), BUDGET_SECONDS)

    def test_doubling_the_input_does_not_square_the_work(self):
        """Linear enough: four times the size must not cost sixteen times.

        Stated as a ratio because absolute timings on a shared machine mean
        little, while a superlinear ratio is exactly the failure mode.
        """
        small = UNCLOSED * 4
        large = UNCLOSED * 16
        # Warm up, so import-time and cache effects land outside the measurement.
        _time_extraction(small)
        small_time = max(_time_extraction(small), 0.001)
        large_time = _time_extraction(large)
        self.assertLess(large_time / small_time, 16,
                        "extraction time is growing faster than the input")

    def test_a_locale_file_of_real_size_stays_fast(self):
        entries = ",".join(f'"key{i}": "Знайдено {{count}} файлів у теці"'
                           for i in range(4000))
        self.assertLess(_time_extraction("{" + entries + "}"), BUDGET_SECONDS)


if __name__ == "__main__":
    unittest.main()
