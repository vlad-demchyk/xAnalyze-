"""What has to be true before a rule reads a template.

Four normalisations stand between a framework's markup and the rules, and
each exists because its absence produced a whole class of confident, wrong
findings. They are tested here rather than only through the fixture pairs,
because a fixture proves the outcome and these prove the reason - and the
reason is what the next framework will be judged against.

The other half of the file is what must **not** happen. A normalisation that
invents structure is worse than one that is missing: a missing one produces
noise a person can see, and an inventing one produces silence they cannot.
"""
from __future__ import annotations

import unittest

from bs4 import BeautifulSoup

from audit.base import (
    is_binding, resolve_bound_attributes, resolve_text_directives,
    unwrap_template_text,
)
from audit.engine import _document_kind
from repo_scanner import mask_server_tags


def _soup(markup: str):
    document = BeautifulSoup(markup, "html.parser")
    resolve_bound_attributes(document)
    resolve_text_directives(document)
    unwrap_template_text(document)
    return document


class ABoundAttributeIsStillThatAttribute(unittest.TestCase):
    """Vue, Angular, Alpine, Svelte and Thymeleaf bind by renaming."""

    def test_each_syntax_gives_the_plain_name_back(self):
        cases = {
            "vue": '<img :alt="caption" :src="url">',
            "vue-long": '<img v-bind:alt="caption" v-bind:src="url">',
            "angular": '<img [alt]="caption" [src]="url">',
            "angular-attr": '<img [attr.alt]="caption" [attr.src]="url">',
            "alpine": '<img x-bind:alt="caption" x-bind:src="url">',
            "svelte": '<img bind:alt="caption" bind:src="url">',
            "thymeleaf": '<img th:alt="#{caption}" th:src="@{/a.png}">',
        }
        for name, markup in cases.items():
            with self.subTest(syntax=name):
                image = _soup(markup).find("img")
                self.assertTrue(is_binding(image.get("alt", "")),
                                f"{name}: alt did not survive as a binding")

    def test_a_literal_beats_a_binding_when_both_are_written(self):
        image = _soup('<img :alt="caption" alt="A view of the walls">').find("img")
        self.assertEqual(image["alt"], "A view of the walls")

    def test_an_xml_namespace_is_not_a_binding(self):
        """`xlink:href` and `xmlns:xlink` share the colon and mean nothing
        like it. Reading them as bindings would invent an `href`."""
        use = _soup('<use xlink:href="#icon"></use>').find("use")
        self.assertIsNone(use.get("href"))

    def test_an_htmx_attribute_is_not_a_binding(self):
        """`hx-get="/y"` is a behaviour, not "bind the `get` attribute".

        It was in the prefix list for one commit and invented a `get`
        attribute on every htmx element in existence.
        """
        span = _soup('<span hx-get="/y" hx-target="#out"></span>').find("span")
        self.assertIsNone(span.get("get"))
        self.assertIsNone(span.get("target"))


class TextThatArrivesAtRuntime(unittest.TestCase):
    """`<a href="/x" x-text="label"></a>` names itself; the file cannot show it."""

    def test_each_directive_gives_the_element_something_to_say(self):
        for directive in ("v-text", "x-text", "th:text", "ng-bind",
                          "data-i18n", "data-bind"):
            with self.subTest(directive=directive):
                link = _soup(f'<a href="/x" {directive}="label"></a>').find("a")
                self.assertTrue(link.get_text(strip=True),
                                f"{directive} left the link empty")

    def test_literal_text_is_left_alone(self):
        link = _soup('<a href="/x" x-text="label">Home</a>').find("a")
        self.assertEqual(link.get_text(strip=True), "Home")

    def test_an_ordinary_empty_link_stays_empty(self):
        """The finding this must not hide."""
        link = _soup('<a href="/x"><i class="icon" aria-hidden="true"></i></a>').find("a")
        self.assertEqual(link.get_text(strip=True), "")


class TemplateContentIsReadable(unittest.TestCase):
    """A Vue single-file component *is* a `<template>`."""

    def test_text_inside_a_template_is_visible(self):
        label = _soup('<template><label for="q">Search</label></template>').find("label")
        self.assertEqual(label.get_text(strip=True), "Search")

    def test_bs4_hides_it_without_the_fix(self):
        """The behaviour being worked around, pinned so it is not a mystery."""
        raw = BeautifulSoup('<template><label>Search</label></template>', "html.parser")
        self.assertEqual(raw.find("label").get_text(strip=True), "")


class ServerTagsThatAreNotText(unittest.TestCase):
    """The shapes an HTML parser reads as something other than text."""

    def test_every_covered_family_is_masked(self):
        cases = {
            "php": '<a href="<?php echo $u; ?>">x</a>',
            "php-short": '<a href="<?= $u ?>">x</a>',
            "erb-jsp-asp": '<a href="<%= root %>">x</a>',
            "twig-django-liquid": "<a href=\"{% url 'home' %}\">x</a>",
            "razor-block": '<div>@{ var x = 1; }</div>',
        }
        for name, markup in cases.items():
            with self.subTest(family=name):
                masked = mask_server_tags(markup)
                self.assertNotIn("<?", masked)
                self.assertNotIn("<%", masked)
                self.assertNotIn("{%", masked)
                self.assertEqual(len(masked), len(markup),
                                 "the mask moved an offset")

    def test_interpolation_is_deliberately_left_as_text(self):
        """`{{ label }}` is a link's only label, and a parser reads it as text.

        Masking it would take the label away and turn a correct element into
        an empty one - the defect this masking exists to prevent, backwards.
        """
        markup = '<a href="/x">{{ label }}</a>'
        self.assertEqual(mask_server_tags(markup), markup)


class APageIsWhatHasAPageInIt(unittest.TestCase):
    """`.html` is a naming convention; a doctype is evidence."""

    def test_a_finished_document_is_a_page(self):
        for markup in (
            "<!DOCTYPE html><html lang='en'><head><title>x</title></head>"
            "<body>x</body></html>",
            "<html><head></head><body>x</body></html>",
        ):
            with self.subTest(markup=markup[:24]):
                self.assertEqual(_document_kind("a.html", markup), "page")

    def test_a_root_without_the_halves_is_not_a_page(self):
        """A complete document is head and body inside a root, not one tag."""
        self.assertEqual(_document_kind("a.html", "<html><div>x</div></html>"),
                         "fragment")

    def test_a_component_template_is_not(self):
        """An Angular component template collected eight page-level findings
        for not being a document it was never going to be."""
        self.assertEqual(
            _document_kind("panel.component.html", '<button (click)="x()"></button>'),
            "fragment")

    def test_a_partial_is_not_either(self):
        self.assertEqual(_document_kind("_header.html", "<header><nav></nav></header>"),
                         "fragment")

    def test_a_non_page_suffix_is_never_a_page(self):
        self.assertEqual(_document_kind("Panel.tsx", "<!DOCTYPE html><html></html>"),
                         "fragment")


if __name__ == "__main__":
    unittest.main()
