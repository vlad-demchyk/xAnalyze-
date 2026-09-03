"""What a multilingual WordPress project declares about itself, against what it uses.

A taxonomy that WPML has not been told to translate is not half-translated:
`get_terms()` returns the source-language terms in **every** language, on
every page that lists them, and nothing in the markup says so. The default is
`0` - "Don't translate" - so the failure mode is silence, and it survives any
amount of translating done in the admin.

Measured on a real three-language site: five taxonomies in use, none declared,
and the one nobody had noticed drove a filter that offered Italian options on
the German page. After the declaration was added the same pass reports
nothing, which is the shape a rule should have - it goes quiet when the defect
is gone rather than when the code is rearranged.

**Two preconditions, both of them exclusions.** No `wpml-config.xml` in the
project means the project has not taken on this contract, and demanding
declarations from it would be inventing a requirement. And a taxonomy the
project never names is not this project's business: a parent theme registers
eighteen of them, of which a child theme uses four.
"""
from __future__ import annotations

import re
from pathlib import Path

from .base import BEST_PRACTICES, EXACT, Issue, MODERATE, SERIOUS

RULE_TAXONOMY_NOT_DECLARED = "i18n-taxonomy-not-declared"
RULE_COMPOSITE_ADMIN_TEXT = "i18n-composite-admin-text"

#: WordPress ships these and WPML handles them on its own; a project is not
#: expected to declare them.
_CORE_TAXONOMIES = frozenset({
    "category", "post_tag", "nav_menu", "link_category", "post_format",
    "wp_theme", "wp_template_part_area", "wp_pattern_category",
    "product_type", "product_visibility", "product_cat", "product_tag",
    "translation_priority",
})

#: Calls whose **first** string argument is a taxonomy name. `get_term_by` is
#: deliberately absent: its first argument is a field name (`slug`, `name`),
#: and reading it as a taxonomy reported a taxonomy called `slug`.
_TAXONOMY_FIRST_ARG = re.compile(
    r"(?:register_taxonomy|get_terms|taxonomy_exists|get_the_terms"
    r"|wp_get_post_terms|get_term_link|is_tax|has_term)"
    r"\(\s*\[?\s*['\"]([a-z][a-z0-9_]{2,})['\"]")
#: `'taxonomy' => 'tipi_luogo'` inside a `tax_query` or a `get_terms` array.
_TAXONOMY_KEY = re.compile(
    r"['\"]taxonomy['\"]\s*=>\s*['\"]([a-z][a-z0-9_]{2,})['\"]")
_DECLARED_RE = re.compile(r"<taxonomy[^>]*>\s*([^<\s]+)\s*</taxonomy>")

#: Keys the configuration hands to WPML whole.
_ADMIN_TEXTS_RE = re.compile(r"<admin-texts>(.*?)</admin-texts>", re.S)
_ADMIN_KEY_RE = re.compile(r'<key\s+name="([^"]+)"\s*/>')

#: The code taking a single stored value apart. A field whose value has to be
#: split is not one string: it is a record, and handing the record to a
#: translator hands them its separators and its URLs as well.
_TAKEN_APART_RE = re.compile(
    r"""(?:explode\s*\(\s*['"][|;,\t]['"]|json_decode\s*\(|preg_split\s*\()""")

#: How far from the key name the parsing has to sit to be the same field's.
#: Measured rather than chosen: at 1500 characters the one real case is found
#: and none of the other twenty keys in the same file produces anything.
_NEARBY = 1500

_SKIP_DIRS = ("/vendor/", "/node_modules/", "/.git/")


def _php_files(root: Path):
    for path in root.rglob("*.php"):
        text = str(path).replace("\\", "/")
        if any(part in text for part in _SKIP_DIRS):
            continue
        yield path


def scan(root) -> list:
    """Taxonomies the project uses without declaring them as translatable."""
    base = Path(root)
    config = base / "wpml-config.xml"
    if not config.is_file():
        return []
    try:
        declared = set(_DECLARED_RE.findall(config.read_text("utf-8", "ignore")))
    except OSError:
        return []

    php: dict = {}
    for path in _php_files(base):
        try:
            php[str(path.relative_to(base))] = path.read_text("utf-8", "ignore")
        except OSError:
            continue

    used: dict = {}
    for relative, text in php.items():
        for pattern in (_TAXONOMY_FIRST_ARG, _TAXONOMY_KEY):
            for match in pattern.finditer(text):
                name = match.group(1)
                if name in _CORE_TAXONOMIES:
                    continue
                used.setdefault(name, relative)

    issues = [Issue(
        rule_id=RULE_TAXONOMY_NOT_DECLARED, severity=SERIOUS,
        category=BEST_PRACTICES, confidence=EXACT, source=str(config),
        details={"taxonomy": name, "where": where}, engine="repo")
        for name, where in sorted(used.items()) if name not in declared]
    issues.extend(_composite_admin_texts(base, php))
    return issues


def _composite_admin_texts(base: Path, php: dict) -> list:
    """Option keys declared whole while the code stores a record in them.

    `<admin-texts>` says "translate this option value". When the value is a
    record - `label|URL` per line, or JSON - that instruction hands the
    translator the separators, the URLs and the structure, and one lost `|`
    removes the row from the page. The same fragility was solved twice on a
    real project by registering the parts instead; the third field was missed,
    and this is the check that would have named it.
    """
    config = base / "wpml-config.xml"
    try:
        text = config.read_text("utf-8", "ignore")
    except OSError:
        return []
    block = _ADMIN_TEXTS_RE.search(text)
    if not block:
        return []

    issues = []
    for key in sorted(set(_ADMIN_KEY_RE.findall(block.group(1)))):
        for path, body in php.items():
            index = body.find(key)
            if index < 0:
                continue
            window = body[max(0, index - _NEARBY):index + _NEARBY]
            match = _TAKEN_APART_RE.search(window)
            if not match:
                continue
            issues.append(Issue(
                rule_id=RULE_COMPOSITE_ADMIN_TEXT, severity=MODERATE,
                category=BEST_PRACTICES, confidence=EXACT, source=str(config),
                details={"key": key, "where": path,
                         "call": match.group(0).strip()}, engine="repo"))
            break
    return issues


def as_documents(root) -> list:
    """One document, addressed to the configuration file that needs the fix."""
    from .engine import DocumentReport

    issues = scan(root)
    if not issues:
        return []
    return [DocumentReport(source=issues[0].source, issues=issues,
                           elements_checked=1)]
