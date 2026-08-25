"""What a media file says about how it was made.

This is deliberately not an AI-image detector, and most of what is pinned
down here is that distinction. There is no honest way to look at pixels and
say a model drew them; what there is, is a set of fields generators write
into the file themselves. Reading a statement a file makes about itself is a
fact in the same sense a zero-width character is a fact - and the moment it
is worded as "this is AI", the product starts lying exactly where it used to
be careful.

The sentence that has to survive every future change to this module: the
absence of every field below means nothing at all. A screenshot, a re-save
or an upload through most platforms strips all of them.

One real hole is nailed shut here too. XMP was being read through
`Image.getxmp()`, which needs `defusedxml` - not installed - so it returned
nothing and warned once per file. The strongest field this module reads was
silently unavailable in every build, which is precisely the kind of quiet
gap the module exists to close. It reads the packet out of the raw bytes
now, which also means no XML parser is exposed to an untrusted file.
"""
from __future__ import annotations

import struct
import tempfile
import unittest
import zlib
from unittest import mock
from pathlib import Path

from PIL import Image, PngImagePlugin

import audit.media as media
from audit.explanations import render


def png(path: Path, **text) -> Path:
    meta = PngImagePlugin.PngInfo()
    for key, value in text.items():
        meta.add_text(key, value)
    Image.new("RGB", (8, 8), "red").save(path, pnginfo=meta or None)
    return path


def jpeg(path: Path, *, software: str = "") -> Path:
    exif = Image.Exif()
    if software:
        exif[0x0131] = software
    Image.new("RGB", (8, 8), "blue").save(path, exif=exif.tobytes())
    return path


def with_xmp(path: Path, packet: bytes) -> Path:
    """A real APP1 XMP segment, the way a producer writes one."""
    raw = path.read_bytes()
    payload = b"http://ns.adobe.com/xap/1.0/\x00" + packet
    segment = b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload
    path.write_bytes(raw[:2] + segment + raw[2:])
    return path


def with_png_chunk(path: Path, kind: bytes, data: bytes = b"") -> Path:
    """A real ancillary PNG chunk, so the file stays a readable PNG.

    Splicing bytes into the header instead makes the image unreadable, and
    the reader then answers "unreadable" - correctly, but about a different
    question than the one being asked.
    """
    raw = path.read_bytes()
    chunk = (struct.pack(">I", len(data)) + kind + data
             + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))
    #: 8-byte signature + the whole IHDR chunk (4 + 4 + 13 + 4).
    at = 8 + 25
    path.write_bytes(raw[:at] + chunk + raw[at:])
    return path


IPTC_AI = (b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF><rdf:Description>'
           b'<Iptc4xmpExt:DigitalSourceType>'
           b'http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia'
           b'</Iptc4xmpExt:DigitalSourceType>'
           b'</rdf:Description></rdf:RDF></x:xmpmeta>')


class Temp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)


class WhatAFileSays(Temp):
    def test_the_iptc_claim_is_the_strongest_thing_read(self):
        """`trainedAlgorithmicMedia` is the standard's own term for it, and
        it is the field Google Images reads."""
        found = media.read_provenance(
            with_xmp(jpeg(self.dir / "a.jpg"), IPTC_AI))
        self.assertEqual(found.kind, media.DECLARED_AI)
        self.assertEqual(found.marker, "xmp:DigitalSourceType")

    def test_the_claim_is_read_as_an_attribute_too(self):
        """Producers write it both ways about equally often."""
        packet = (b'<x:xmpmeta><rdf:Description '
                  b'Iptc4xmpExt:DigitalSourceType="trainedAlgorithmicMedia"/>'
                  b'</x:xmpmeta>')
        found = media.read_provenance(
            with_xmp(jpeg(self.dir / "b.jpg"), packet))
        self.assertEqual(found.kind, media.DECLARED_AI)

    def test_xmp_is_read_without_an_xml_parser(self):
        """It used to go through `Image.getxmp()`, which needs `defusedxml`
        - not installed - so this field was silently unavailable. Reading
        the packet directly also leaves no parser exposed to a hostile
        file, which is what `defusedxml` exists to guard."""
        import PIL.Image as pil
        original = getattr(pil.Image, "getxmp", None)
        self.assertIsNotNone(original)
        with mock.patch.object(
                pil.Image, "getxmp", side_effect=AssertionError("parsed XMP")):
            found = media.read_provenance(
                with_xmp(jpeg(self.dir / "c.jpg"), IPTC_AI))
        self.assertEqual(found.kind, media.DECLARED_AI)

    def test_a_prompt_block_is_a_declaration(self):
        """Only the local-generation stack writes these, and it writes the
        model and the seed with them."""
        found = media.read_provenance(
            png(self.dir / "d.png",
                parameters="a cat on a roof, Steps: 20, Model: sd_xl, Seed: 42"))
        self.assertEqual(found.kind, media.DECLARED_AI)
        self.assertEqual(found.marker, "png:parameters")
        self.assertIn("Seed", found.detail)

    def test_a_tool_name_is_weaker_and_says_so_by_its_kind(self):
        """The field says which program touched the file, not where the
        pixels came from: an image edited in a generator's app carries the
        same string."""
        found = media.read_provenance(
            jpeg(self.dir / "e.jpg", software="Midjourney v6"))
        self.assertEqual(found.kind, media.GENERATOR_TOOL)
        self.assertEqual(found.tool, "midjourney")

    def test_an_ordinary_camera_string_is_not_a_generator(self):
        found = media.read_provenance(
            jpeg(self.dir / "f.jpg", software="Adobe Lightroom 13.2"))
        self.assertEqual(found.kind, media.NOTHING)

    def test_a_file_with_nothing_in_it_says_nothing(self):
        """And this is the sentence the whole module turns on: it is not a
        verdict that a person made the image."""
        found = media.read_provenance(png(self.dir / "g.png"))
        self.assertEqual(found.kind, media.NOTHING)
        self.assertFalse(found.says_something)

    def test_a_signed_manifest_is_reported_even_though_it_cannot_be_read(self):
        """Passing over one silently would show a file that documents itself
        as a file that does not."""
        path = with_png_chunk(png(self.dir / "h.png"), b"caBX", b"manifest")
        found = media.read_provenance(path)
        self.assertEqual(found.kind, media.SIGNED_UNVERIFIED)
        self.assertIn("not verified", found.detail)

    def test_a_broken_file_is_an_answer_not_a_crash(self):
        (self.dir / "i.png").write_bytes(b"not a png at all")
        found = media.read_provenance(self.dir / "i.png")
        self.assertEqual(found.kind, media.UNREADABLE)
        self.assertTrue(found.error)

    def test_a_missing_file_is_an_answer_too(self):
        self.assertEqual(media.read_provenance(self.dir / "nope.png").kind,
                         media.UNREADABLE)

    def test_a_kilobyte_of_json_does_not_become_a_kilobyte_of_report(self):
        found = media.read_provenance(
            png(self.dir / "j.png", parameters="x" * 5000))
        self.assertLessEqual(len(found.detail), 300)


class TheWalk(Temp):
    def test_it_reads_the_images_and_leaves_the_rest_alone(self):
        png(self.dir / "a.png", parameters="a cat, Seed: 1")
        (self.dir / "notes.txt").write_text("not an image")
        scan = media.scan_media(self.dir)
        self.assertEqual(scan.files_read, 1)
        self.assertEqual(len(scan.findings), 1)

    def test_it_skips_what_the_repository_scanner_skips(self):
        """Two walks with two opinions about `node_modules/` is one walk too
        many - and the second one reads a hundred megabytes."""
        vendored = self.dir / "node_modules" / "pkg"
        vendored.mkdir(parents=True)
        png(vendored / "logo.png", parameters="a cat, Seed: 1")
        scan = media.scan_media(self.dir)
        self.assertEqual(scan.files_read, 0)
        self.assertEqual(scan.skipped_ignored, 1)

    def test_a_quiet_image_is_read_and_not_reported(self):
        """Counted, because "nothing found" and "nothing looked at" are
        opposite answers and produce the same empty list."""
        png(self.dir / "plain.png")
        scan = media.scan_media(self.dir)
        self.assertEqual(scan.files_read, 1)
        self.assertEqual(scan.findings, [])

    def test_a_broken_image_is_counted_apart(self):
        (self.dir / "broken.png").write_bytes(b"nope")
        scan = media.scan_media(self.dir)
        self.assertEqual(scan.unreadable, 1)
        self.assertEqual(scan.findings, [])

    def test_a_path_that_is_not_a_folder_is_not_a_crash(self):
        self.assertEqual(media.scan_media(self.dir / "nowhere").files_read, 0)


class AsFindings(Temp):
    def test_each_kind_gets_its_own_rule_id(self):
        """Three different statements, and a reader has to be able to tell
        them apart in a report, a filter and a suppression file."""
        self.assertEqual(len(set(media.RULE_OF.values())), 3)

    def test_a_generated_image_is_minor_because_it_is_not_harm(self):
        """The audit's severities measure harm to a reader. A generated
        image does none; what to do about it is not this tool's call."""
        from audit.base import BEST_PRACTICES, MINOR

        issue = media.as_issue("a.png", media.Provenance(kind=media.DECLARED_AI))
        self.assertEqual(issue.severity, MINOR)
        self.assertEqual(issue.category, BEST_PRACTICES)

    def test_the_finding_names_the_field_it_came_from(self):
        """So a reader can go and look at the same field rather than take
        the finding on trust."""
        issue = media.as_issue("a.png", media.Provenance(
            kind=media.DECLARED_AI, marker="png:parameters", detail="a cat"))
        self.assertEqual(issue.details["marker"], "png:parameters")

    def test_it_is_attributed_to_the_media_pass_not_to_the_rules(self):
        issue = media.as_issue("a.png", media.Provenance(kind=media.DECLARED_AI))
        self.assertEqual(issue.engine, "media")

    def test_every_kind_reads_as_a_sentence_in_every_language(self):
        """`t` returns its key when it has no entry, and a user must never
        be shown `a11y_bp_ai_media_declared_title`."""
        for kind in media.RULE_OF:
            for lang in ("uk", "it", "en"):
                with self.subTest(kind=kind, lang=lang):
                    issue = media.as_issue("a.png", media.Provenance(
                        kind=kind, marker="png:parameters", tool="midjourney"))
                    explained = render(issue, lang)
                    for part in (explained.title, explained.found,
                                 explained.why, explained.fix):
                        self.assertNotIn("a11y_", part)

    def test_the_wording_never_says_this_is_ai(self):
        """It says what the file says. The distinction is the product."""
        issue = media.as_issue("a.png", media.Provenance(
            kind=media.DECLARED_AI, marker="png:parameters"))
        explained = render(issue, "en")
        self.assertIn("states", explained.title.lower())
        # And the limit is stated where the reader will meet it.
        self.assertIn("absence", explained.why.lower())


class InTheAudit(Temp):
    def test_a_repository_audit_reads_its_images(self):
        from models import FileResult

        import audit

        (self.dir / "a.html").write_text("<html><body><p>hi</p></body></html>")
        png(self.dir / "hero.png", parameters="a cat, Seed: 1")
        result = audit.analyze_files(
            [FileResult(path=str(self.dir / "a.html"),
                        raw_text=(self.dir / "a.html").read_text())],
            str(self.dir))
        sources = {Path(d.source).name for d in result.documents}
        self.assertIn("hero.png", sources)

    def test_a_caller_can_ask_for_the_markup_only(self):
        import audit

        png(self.dir / "hero.png", parameters="a cat, Seed: 1")
        result = audit.analyze_files([], str(self.dir), media=False)
        self.assertEqual(result.documents, [])

    def test_an_image_is_a_document_of_its_own(self):
        """Which is the unit the report, the grouping and the file column
        already work in."""
        import audit

        png(self.dir / "hero.png", parameters="a cat, Seed: 1")
        result = audit.analyze_files([], str(self.dir))
        self.assertEqual(len(result.documents), 1)
        self.assertEqual(len(result.documents[0].issues), 1)


class HowTheyGroup(Temp):
    """The window shows one row per distinct problem, with its places on it.

    Media findings go through the same grouping, and the question is whether
    that grouping means anything for them: all of them carry an empty
    selector, so a grouping keyed on that would collapse every image in the
    project into one row and quietly lose which file is which.
    """

    def png_with(self, name: str, prompt: str):
        return png(self.dir / name, parameters=prompt)

    def test_the_same_image_twice_is_one_row_naming_both_files(self):
        """Two files from one generation are one finding in two places -
        which is the same rule the copy findings already follow."""
        import audit
        import duplicates

        self.png_with("a.png", "a cat, Seed: 1")
        self.png_with("c.png", "a cat, Seed: 1")
        grouped = list(duplicates.group_issues(
            audit.analyze_files([], str(self.dir)).issues()))
        self.assertEqual(len(grouped), 1)
        first, others = grouped[0]
        self.assertEqual(len(duplicates.places_of(first, others)), 2)

    def test_two_different_generations_stay_two_rows(self):
        """They would collapse if the grouping keyed on the selector, which
        every media finding leaves empty."""
        import audit
        import duplicates

        self.png_with("a.png", "a cat, Seed: 1")
        self.png_with("b.png", "a dog, Seed: 2")
        grouped = list(duplicates.group_issues(
            audit.analyze_files([], str(self.dir)).issues()))
        self.assertEqual(len(grouped), 2)


if __name__ == "__main__":
    unittest.main()


class _Page:
    def __init__(self, url: str, html: str):
        self.url, self.raw_html, self.error = url, html, None


def png_bytes(prompt: str = "") -> bytes:
    import io

    buf = io.BytesIO()
    meta = PngImagePlugin.PngInfo()
    if prompt:
        meta.add_text("parameters", prompt)
    Image.new("RGB", (8, 8), "red").save(buf, "PNG", pnginfo=meta if prompt else None)
    return buf.getvalue()


class WhichImagesAPageRefersTo(unittest.TestCase):
    def urls(self, html: str) -> list:
        return media.image_urls(html, "https://x.test/a/b")

    def test_relative_addresses_are_resolved(self):
        self.assertEqual(self.urls('<img src="/hero.png">'),
                         ["https://x.test/hero.png"])

    def test_every_candidate_of_a_srcset_counts(self):
        """A generated image is often served only at one size."""
        self.assertEqual(len(self.urls('<img srcset="/a.png 1x, /b.png 2x">')), 2)

    def test_a_picture_source_counts_too(self):
        self.assertEqual(self.urls('<source srcset="/c.webp">'),
                         ["https://x.test/c.webp"])

    def test_a_lazy_attribute_counts(self):
        """Half the web puts the real address in `data-src`."""
        self.assertEqual(self.urls('<img data-src="/d.png">'),
                         ["https://x.test/d.png"])

    def test_a_data_uri_is_left_exactly_as_it_is(self):
        """Resolving it against the page would corrupt the bytes."""
        self.assertEqual(self.urls('<img src="data:image/png;base64,AAAA">'),
                         ["data:image/png;base64,AAAA"])

    def test_one_address_is_listed_once(self):
        self.assertEqual(len(self.urls('<img src="/a.png"><img src="/a.png">')), 1)

    def test_unparseable_markup_is_not_a_crash(self):
        self.assertEqual(media.image_urls("<<<", "https://x.test/"), [])


class TheWebPass(unittest.TestCase):
    def setUp(self):
        self.store = {"https://x.test/hero.png": png_bytes("a cat, Seed: 1"),
                      "https://x.test/logo.png": png_bytes()}
        self.asked = []

    def fetch(self, url, limit):
        self.asked.append(url)
        if url not in self.store:
            raise OSError("404")
        return self.store[url], True

    def pages(self, count: int = 1) -> list:
        return [_Page(f"https://x.test/p{i}",
                      '<img src="/hero.png"><img src="/logo.png">')
                for i in range(count)]

    def test_a_shared_image_is_fetched_once_not_once_per_page(self):
        """A logo in a header appears on every page of a site, and fetching
        it per page is how a thirty-page scan downloads one image thirty
        times."""
        scan = media.scan_page_media(self.pages(5), fetch=self.fetch)
        self.assertEqual(len(self.asked), 2)
        self.assertEqual(scan.checked, 2)

    def test_it_reports_what_it_found(self):
        scan = media.scan_page_media(self.pages(), fetch=self.fetch)
        self.assertEqual([source for source, _found in scan.findings],
                         ["https://x.test/hero.png"])

    def test_the_budget_stops_it_and_the_stop_is_counted(self):
        """An image nobody fetched has not come back clean - it has not come
        back. The count is how the run can say so."""
        scan = media.scan_page_media(self.pages(), fetch=self.fetch,
                                     max_images=1)
        self.assertEqual(scan.checked, 1)
        self.assertEqual(scan.skipped_budget, 1)
        self.assertEqual(scan.unchecked, 1)

    def test_a_data_uri_costs_nothing_and_is_read_anyway(self):
        """The bytes came with the page; a budget that exists to bound the
        network has no business refusing them."""
        import base64

        uri = "data:image/png;base64," + base64.b64encode(
            png_bytes("a dog, Seed: 9")).decode()
        scan = media.scan_page_media([_Page("https://x.test/", f'<img src="{uri}">')],
                                     fetch=self.fetch, max_images=0)
        self.assertEqual(scan.checked, 0)
        self.assertEqual(len(scan.findings), 1)

    def test_a_data_uri_is_named_by_where_it_is(self):
        """An eighty-character base64 prefix is not a place."""
        import base64

        uri = "data:image/png;base64," + base64.b64encode(
            png_bytes("a dog, Seed: 9")).decode()
        scan = media.scan_page_media([_Page("https://x.test/", f'<img src="{uri}">')],
                                     fetch=self.fetch)
        self.assertNotIn("base64", scan.findings[0][0])

    def test_an_image_that_will_not_load_is_counted_not_raised(self):
        scan = media.scan_page_media(
            [_Page("https://x.test/", '<img src="/gone.png">')], fetch=self.fetch)
        self.assertEqual(scan.unreachable, 1)
        self.assertEqual(scan.findings, [])

    def test_a_partial_download_is_not_reported_as_nothing_found(self):
        """It was not judged. Calling that "nothing found" is a claim the
        run did not earn - which is the whole point of this pass."""
        def truncating(url, limit):
            return self.store["https://x.test/hero.png"][:10], False

        scan = media.scan_page_media(
            [_Page("https://x.test/", '<img src="/big.png">')], fetch=truncating)
        self.assertEqual(scan.findings, [])
        self.assertEqual(scan.unreachable, 0)
        self.assertGreater(scan.unchecked, 0)

    def test_a_page_with_no_markup_is_skipped_quietly(self):
        page = _Page("https://x.test/", "")
        self.assertEqual(media.scan_page_media([page], fetch=self.fetch).found, 0)


class TheAuditSaysWhatItDidNotOpen(unittest.TestCase):
    """`diagnosis.diagnose_audit`, which is where the counts become words."""

    def scan(self, **kwargs):
        return media.MediaFetchScan(**kwargs)

    def result(self, scan):
        from audit.engine import AccessibilityResult

        return AccessibilityResult(root="https://x.test", media=scan)

    def test_a_run_that_opened_everything_says_nothing(self):
        import diagnosis as dx

        self.assertEqual(
            dx.diagnose_audit(self.result(self.scan(found=3, checked=3))), [])

    def test_a_run_that_skipped_images_says_so(self):
        import diagnosis as dx

        items = dx.diagnose_audit(
            self.result(self.scan(found=50, checked=40, skipped_budget=10)))
        self.assertEqual([item.kind for item in items], [dx.MEDIA_UNCHECKED])
        self.assertEqual(items[0].fields["unchecked"], 10)

    def test_an_audit_without_a_media_pass_says_nothing(self):
        import diagnosis as dx

        self.assertEqual(dx.diagnose_audit(self.result(None)), [])

    def test_it_reads_as_a_sentence_in_every_language(self):
        import diagnosis as dx
        from i18n.translations import t

        item = dx.diagnose_audit(
            self.result(self.scan(found=50, checked=40, skipped_budget=10)))[0]
        for lang in ("uk", "it", "en"):
            with self.subTest(lang=lang):
                for key in (item.title_key, item.body_key, item.evidence_key):
                    self.assertNotIn("diagnosis_", t(key, lang, **item.fields))
