"""Where copy is, and where it only looks like it is.

The two failures these cover were the same bug seen from opposite sides: a
component file was read as if it were prose, and the locale file holding the
actual prose was not read at all.
"""
import unittest

import repo_scanner as rs


def _texts(source, name="src/Panel.tsx", scope="content"):
    return [b.text for b in rs._extract_blocks(source, name, scope)]


COMPONENT = '''
import { useState } from "react";

export function Panel({ items }) {
  const [open, setOpen] = useState<boolean>(false);
  const box = useRef<HTMLDivElement>(null);
  // The list is virtualised, so a plain map would drop rows.
  return <section className="panel">
    <h2>Saved documents</h2>
    <p>{items.length} files kept on this device</p>
    <button onClick={() => setOpen(!open)}>{t("panel.toggle")}</button>
  </section>;
}
'''


class CodeIsNotCopy(unittest.TestCase):
    def test_a_generic_parameter_is_not_a_tag(self):
        # `useState<boolean>(false)` ends in `>` and is followed by code.
        for text in _texts(COMPONENT):
            self.assertNotIn("useState", text)
            self.assertNotIn("useRef", text)

    def test_a_comment_is_not_copy(self):
        self.assertFalse([t for t in _texts(COMPONENT) if "virtualised" in t])

    def test_the_comment_is_still_there_for_the_technical_scope(self):
        found = _texts(COMPONENT, scope="technical")
        self.assertTrue([t for t in found if "virtualised" in t])

    def test_real_rendered_text_survives(self):
        found = _texts(COMPONENT)
        self.assertIn("Saved documents", found)
        self.assertIn("files kept on this device", found)

    def test_a_translation_key_is_not_judged_as_prose(self):
        self.assertNotIn("panel.toggle", _texts(COMPONENT))

    def test_a_single_word_key_is_still_read_as_copy(self):
        # Projects that use English as their key language write `t("Download")`,
        # and that string is the copy.
        self.assertIn("Download now", _texts('t("Download now")'))


class LocaleFiles(unittest.TestCase):
    def test_recognised_by_folder_and_by_name(self):
        self.assertTrue(rs.is_locale_file("apps/web/src/locales/uk.json"))
        self.assertTrue(rs.is_locale_file("config/locales/en.yml"))
        self.assertTrue(rs.is_locale_file("i18n/pt_BR.json"))

    def test_configuration_is_not_a_locale_file(self):
        self.assertFalse(rs.is_locale_file("package.json"))
        self.assertFalse(rs.is_locale_file("tsconfig.json"))
        self.assertFalse(rs.is_locale_file("apps/web/vite.config.ts"))

    def test_json_values_are_copy_and_keys_are_not(self):
        source = '{"nav": {"features": "Функції"}, "hero": {"title": "Один застосунок"}}'
        found = _texts(source, "src/locales/uk.json")
        self.assertIn("Функції", found)
        self.assertIn("Один застосунок", found)
        self.assertNotIn("nav", found)

    def test_a_placeholder_does_not_disqualify_a_string(self):
        # The brace rule belongs to the markup path: `{count}` in a locale
        # string is deliberate.
        found = _texts('{"found": "Знайдено {count} файлів у теці"}', "locales/uk.json")
        self.assertIn("Знайдено {count} файлів у теці", found)

    def test_yaml_locales_are_read_too(self):
        found = _texts("en:\n  greeting: Welcome back to the workspace\n",
                       "config/locales/en.yml")
        self.assertIn("Welcome back to the workspace", found)

    def test_offsets_point_at_the_original_text(self):
        source = '{"title": "Один застосунок для документів"}'
        block = rs._extract_blocks(source, "locales/uk.json", "content")[0]
        self.assertEqual(source[block.start:block.end], block.text)


if __name__ == "__main__":
    unittest.main()
