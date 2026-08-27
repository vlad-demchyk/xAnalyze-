"""One template, one problem - however the framework spells the element.

`issue_identity` compares markup, so anything a framework stamps into it
splits one finding into one finding per page. Measured on the twelve
identifier styles real sites actually serve: nine of the twelve were
splitting, and only WordPress's hex suffix, Vue's scoped attribute and MUI's
longer counters were being caught.

Both directions are tested, and the second matters more: over-masking merges
findings that really are different, and a wrongly merged problem hides a real
one. Two images missing `alt` must stay two problems.
"""
import unittest

from audit.base import Issue
from duplicates import group_issues

#: Real identifier styles, one pair each: the same element rendered twice.
GENERATED = {
    "radix": ('<button id="radix-:r3:" aria-controls="radix-:r4:">Menu</button>',
              '<button id="radix-:r7:" aria-controls="radix-:r8:">Menu</button>'),
    "react-use-id": ('<input id=":R1mcq:" name="q">', '<input id=":R2abc:" name="q">'),
    "mui-short": ('<input id="mui-12" type="text">', '<input id="mui-47" type="text">'),
    "mui-long": ('<input id="mui-12345" type="text">', '<input id="mui-98765" type="text">'),
    "emotion": ('<div class="css-1q2w3e"><img src="a.png"></div>',
                '<div class="css-9z8y7x"><img src="a.png"></div>'),
    "styled-components": ('<div class="sc-bdVaJa hUyXlM"><img src="a.png"></div>',
                          '<div class="sc-bdVaJa kXwZpQ"><img src="a.png"></div>'),
    "svelte": ('<img class="hero svelte-1x2y3z" src="a.png">',
               '<img class="hero svelte-9a8b7c" src="a.png">'),
    "astro": ('<img class="astro-j7pv25f6" src="a.png">',
              '<img class="astro-k2mn88qq" src="a.png">'),
    "vue-scoped": ('<img data-v-7ba5bd90 src="a.png">', '<img data-v-1f2e3d4c src="a.png">'),
    "angular": ('<img _ngcontent-ng-c123 src="a.png">', '<img _ngcontent-ng-c987 src="a.png">'),
    "wordpress": ('<button aria-controls="page-toc-panel-6a8c2c05ce8bd">T</button>',
                  '<button aria-controls="page-toc-panel-9b1d3e77af21">T</button>'),
    "ember": ('<div id="ember123"><img src="a.png"></div>',
              '<div id="ember456"><img src="a.png"></div>'),
}

#: Pairs that differ in something a person chose. Every one of these is two
#: problems and must stay two rows.
AUTHORED = {
    "different images": ('<img src="hero.png">', '<img src="team.png">'),
    "different links": ('<a href="/about"></a>', '<a href="/pricing"></a>'),
    "tailwind spacing": ('<div class="mt-4 text-2xl"><img src="a.png"></div>',
                         '<div class="mt-8 text-2xl"><img src="a.png"></div>'),
    "bootstrap columns": ('<div class="col-md-6"><img src="a.png"></div>',
                          '<div class="col-md-4"><img src="a.png"></div>'),
    "real ids": ('<input id="email" name="email">', '<input id="phone" name="phone">'),
    "different headings": ('<h2>Prices</h2>', '<h2>Contact</h2>'),
    "different labels": ('<button aria-label="Open menu"></button>',
                         '<button aria-label="Close"></button>'),
}


def _pair(first: str, second: str) -> list:
    return [Issue(rule_id="image-alt", severity="critical", snippet=markup,
                  source=f"https://x/{index}")
            for index, markup in enumerate((first, second))]


class GeneratedIdentifiersDoNotSplitAProblem(unittest.TestCase):
    def test_every_framework_style_groups(self):
        for name, (first, second) in GENERATED.items():
            with self.subTest(framework=name):
                self.assertEqual(len(group_issues(_pair(first, second))), 1,
                                 f"{name} splits one template into two findings")


class WhatThePersonWroteStillSeparates(unittest.TestCase):
    def test_authored_differences_stay_apart(self):
        for name, (first, second) in AUTHORED.items():
            with self.subTest(case=name):
                self.assertEqual(len(group_issues(_pair(first, second))), 2,
                                 f"{name} merged two different problems into one")


if __name__ == "__main__":
    unittest.main()
