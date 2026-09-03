"""A taxonomy the project uses without telling WPML to translate it.

The default is "do not translate", so the failure is silent: terms come back
in the source language in every language and the markup looks fine. This pass
reads the project's own declaration against the project's own code, which is
why it needs neither a site nor a database.
"""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from audit import i18n_wpml

RULE = "i18n-taxonomy-not-declared"

CONFIG = ('<?xml version="1.0"?><wpml-config><taxonomies>{}</taxonomies>'
          "{}</wpml-config>")


class _Project:
    def __enter__(self):
        self._dir = TemporaryDirectory()
        self.root = Path(self._dir.name)
        return self

    def __exit__(self, *exc):
        self._dir.cleanup()

    def config(self, *declared, admin_texts=()):
        body = "".join(f'<taxonomy translate="1">{n}</taxonomy>'
                       for n in declared)
        texts = ""
        if admin_texts:
            keys = "".join(f'<key name="{k}" />' for k in admin_texts)
            texts = f"<admin-texts>{keys}</admin-texts>"
        (self.root / "wpml-config.xml").write_text(CONFIG.format(body, texts))
        return self

    def php(self, name, body):
        (self.root / name).write_text(f"<?php\n{body}\n")
        return self

    def found(self):
        return sorted(i.details["taxonomy"] for i in i18n_wpml.scan(self.root)
                      if i.rule_id == RULE)

    def composite(self):
        return sorted(i.details["key"] for i in i18n_wpml.scan(self.root)
                      if i.rule_id == "i18n-composite-admin-text")


class WhatTheProjectUsesWithoutDeclaring(unittest.TestCase):

    def test_an_undeclared_taxonomy_is_reported(self):
        with _Project() as p:
            p.config("argomenti").php(
                "archive.php", "get_terms( array( 'taxonomy' => 'tipi_luogo' ) );")
            self.assertEqual(p.found(), ["tipi_luogo"])

    def test_every_call_shape_is_read(self):
        with _Project() as p:
            p.config().php("a.php", """
                register_taxonomy( 'esperienze_tag', array( 'post' ) );
                $t = get_terms( 'tipi_evento' );
                if ( taxonomy_exists( 'argomenti' ) ) { }
                $x = array( 'taxonomy' => 'tipi_luogo', 'field' => 'slug' );
                if ( is_tax( 'meccanica_tag' ) ) { }
            """)
            self.assertEqual(p.found(), ["argomenti", "esperienze_tag",
                                         "meccanica_tag", "tipi_evento",
                                         "tipi_luogo"])

    def test_a_declared_taxonomy_is_silent(self):
        with _Project() as p:
            p.config("tipi_luogo").php("a.php", "get_terms( 'tipi_luogo' );")
            self.assertEqual(p.found(), [])


class TheExclusionsThatKeepItQuiet(unittest.TestCase):

    def test_a_project_without_the_config_is_left_alone(self):
        # No `wpml-config.xml` means the project never took on this
        # contract; asking it to declare things would invent a requirement.
        with _Project() as p:
            p.php("a.php", "get_terms( 'tipi_luogo' );")
            self.assertEqual(p.found(), [])

    def test_core_taxonomies_are_not_the_project_to_declare(self):
        with _Project() as p:
            p.config().php("a.php", """
                get_terms( 'category' );
                get_terms( 'post_tag' );
                get_terms( 'product_cat' );
            """)
            self.assertEqual(p.found(), [])

    def test_get_term_by_takes_a_field_name_first(self):
        # `get_term_by( 'slug', … )`: reading the first argument as a
        # taxonomy reported a taxonomy called `slug` on a real theme.
        with _Project() as p:
            p.config().php(
                "a.php", "get_term_by( 'slug', $slug, 'tipi_luogo' );")
            self.assertEqual(p.found(), [])

    def test_a_taxonomy_the_project_never_names_is_not_its_business(self):
        # A parent theme registers eighteen; a child theme uses four.
        with _Project() as p:
            p.config().php("a.php", "echo 'nothing taxonomic here';")
            self.assertEqual(p.found(), [])

    def test_vendor_directories_are_not_the_project(self):
        with _Project() as p:
            p.config()
            (p.root / "vendor").mkdir()
            (p.root / "vendor" / "lib.php").write_text(
                "<?php get_terms( 'their_taxonomy' );")
            self.assertEqual(p.found(), [])


class ARecordHandedOverAsAString(unittest.TestCase):
    """`<admin-texts>` says "translate this value". A value the code has to
    take apart is a record, and translating it hands over its separators."""

    def test_a_key_whose_value_is_split_is_reported(self):
        with _Project() as p:
            p.config(admin_texts=("footer_links",)).php(
                "helpers.php",
                "$raw = dci_get_option( 'footer_links', 'theme' );\n"
                "foreach ( explode( '|', $raw ) as $part ) { }")
            self.assertEqual(p.composite(), ["footer_links"])

    def test_a_json_blob_counts_too(self):
        with _Project() as p:
            p.config(admin_texts=("cta_items",)).php(
                "helpers.php",
                "$rows = json_decode( get_option( 'cta_items' ), true );")
            self.assertEqual(p.composite(), ["cta_items"])

    def test_a_plain_string_key_is_silent(self):
        with _Project() as p:
            p.config(admin_texts=("footer_phone",)).php(
                "helpers.php", "echo esc_html( dci_get_option( 'footer_phone' ) );")
            self.assertEqual(p.composite(), [])

    def test_parsing_far_from_the_key_is_not_the_same_field(self):
        with _Project() as p:
            p.config(admin_texts=("footer_phone",)).php(
                "helpers.php",
                "echo dci_get_option( 'footer_phone' );\n" + ("// filler\n" * 400)
                + "$x = explode( '|', $unrelated );")
            self.assertEqual(p.composite(), [])

    def test_no_admin_texts_block_means_nothing_to_check(self):
        with _Project() as p:
            p.config().php("helpers.php", "$x = explode( '|', $raw );")
            self.assertEqual(p.composite(), [])


if __name__ == "__main__":
    unittest.main()
