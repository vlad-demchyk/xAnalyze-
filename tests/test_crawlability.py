from __future__ import annotations

import unittest
from unittest.mock import patch

import audit
from audit.base import Issue, SEO, SERIOUS
from audit import crawlability
from models import PageDiagnostics, PageResult


def page(url, markup="", status=200, headers=None, error=None):
    return PageResult(url=url, depth=0, raw_html=markup, error=error,
                      diagnostics=PageDiagnostics(status_code=status,
                                                  final_url=url,
                                                  headers=headers or {}))


class Response:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


class CrawlabilityFacts(unittest.TestCase):
    def test_x_robots_noindex_is_an_exact_seo_finding(self):
        found = crawlability.issues_for([
            page("https://example.test/", "<html></html>",
                 headers={"x-robots-tag": "noindex, nofollow"})])
        self.assertEqual([issue.rule_id for issue in found], ["seo-x-robots-noindex"])

    def test_a_link_to_a_reached_404_is_reported_on_its_source_page(self):
        found = crawlability.issues_for([
            page("https://example.test/", '<a href="/gone">Gone</a>'),
            page("https://example.test/gone", status=404, error="404"),
        ])
        self.assertEqual({issue.rule_id for issue in found}, {
            "seo-crawl-http-error", "seo-internal-link-failed"})

    def test_an_unvisited_link_is_not_assumed_broken(self):
        found = crawlability.issues_for([
            page("https://example.test/", '<a href="/not-in-this-depth">Later</a>'),
        ])
        self.assertEqual(found, [])

    def test_external_links_are_not_claimed_to_be_internal_failures(self):
        found = crawlability.issues_for([
            page("https://example.test/", '<a href="https://other.test/gone">Offsite</a>'),
            page("https://other.test/gone", status=404, error="404"),
        ])
        self.assertEqual([issue.rule_id for issue in found], ["seo-crawl-http-error"])


class LinksAreReadOnce(unittest.TestCase):
    """The audit reuses the crawl's anchors instead of re-parsing the page.

    The same HTML was being parsed four times per page: text blocks, links
    for the walk, the rules, and then this pass. The fourth was a duplicate
    of the second down to the selector.
    """

    def test_the_crawl_records_its_anchors_on_the_page(self):
        from crawler import page_from_html
        result = page_from_html(
            '<html><body><a href="/a">A</a><a href="#top">Top</a></body></html>',
            "https://example.test/")
        self.assertEqual([link.url for link in result.links],
                         ["https://example.test/a"])
        self.assertIn("<a", result.links[0].snippet)

    def test_a_recorded_empty_list_is_not_a_reason_to_re_parse(self):
        # `[]` means "read, no anchors"; `None` means "nobody looked". A
        # reader that conflates them parses pages that were already read.
        source = page("https://example.test/", '<a href="/gone">Gone</a>')
        source.links = []
        found = crawlability.issues_for([
            source, page("https://example.test/gone", status=404, error="404")])
        self.assertEqual([issue.rule_id for issue in found], ["seo-crawl-http-error"])

    def test_recorded_anchors_are_used_and_the_markup_is_not_touched(self):
        from models import LinkRef
        source = page("https://example.test/")
        source.raw_html = None
        source.links = [LinkRef(href="/gone", url="https://example.test/gone",
                                snippet='<a href="/gone">Gone</a>')]
        found = crawlability.issues_for([
            source, page("https://example.test/gone", status=404, error="404")])
        self.assertIn("seo-internal-link-failed",
                      {issue.rule_id for issue in found})


class SiteControlFacts(unittest.TestCase):
    ROOT = "https://example.test/path/page"
    ROBOTS = "https://example.test/robots.txt"

    def issues(self, responses):
        def fetch(url, timeout):
            return responses[url]
        return crawlability.site_control_issues(self.ROOT, fetch=fetch)

    def test_global_robots_block_is_reported(self):
        found = self.issues({self.ROBOTS: Response(200, "User-agent: *\nDisallow: /\n")})
        self.assertEqual([issue.rule_id for issue in found],
                         ["seo-robots-root-disallowed"])

    def test_a_rule_for_only_googlebot_is_not_misreported_as_global(self):
        found = self.issues({self.ROBOTS: Response(
            200, "User-agent: *\nAllow: /\n\nUser-agent: Googlebot\nDisallow: /\n")})
        self.assertEqual(found, [])

    def test_disallow_all_with_an_allow_list_is_not_a_site_wide_block(self):
        """The shape this rule used to call "the site forbids indexing".

        `Disallow: / + Allow: /public` is a site publishing a list, not a
        site hiding. Every real crawler resolves the pair by longest match,
        so reporting SERIOUS here was a false alarm on a common pattern.
        """
        found = self.issues({self.ROBOTS: Response(
            200, "User-agent: *\nDisallow: /\nAllow: /public\nAllow: /blog\n")})
        self.assertEqual(found, [])

    def test_a_bare_allow_does_not_hide_a_real_global_block(self):
        # An empty `Allow:` value grants nothing, so it must not silence the
        # finding - otherwise the fix above becomes a way to go unreported.
        found = self.issues({self.ROBOTS: Response(
            200, "User-agent: *\nAllow:\nDisallow: /\n")})
        self.assertEqual([issue.rule_id for issue in found],
                         ["seo-robots-root-disallowed"])

    def test_a_global_block_after_a_bot_group_is_still_read(self):
        found = self.issues({self.ROBOTS: Response(
            200, "User-agent: Googlebot\nAllow: /\n\nUser-agent: *\nDisallow: /\n")})
        self.assertEqual([issue.rule_id for issue in found],
                         ["seo-robots-root-disallowed"])

    def test_site_control_fetches_do_not_follow_redirects(self):
        """The origin check is worth nothing if the address moves after it.

        A same-origin sitemap answering 302 to any host would turn an
        untrusted `robots.txt` into a request proxy - which is exactly what
        `_same_origin` exists to prevent.
        """
        seen = []

        def fetch(url, timeout, allow_redirects=True):
            seen.append((url, allow_redirects))
            return Response(200, "Sitemap: /sitemap.xml\n" if url == self.ROBOTS
                            else "<urlset/>")

        crawlability.site_control_issues(self.ROOT, fetch=fetch)
        self.assertEqual([url for url, _ in seen],
                         [self.ROBOTS, "https://example.test/sitemap.xml"])
        self.assertTrue(all(allow is False for _, allow in seen))

    def test_a_sitemap_declaring_entities_is_refused_not_parsed(self):
        # "Billion laughs": `xml.etree` resolves no external entities but does
        # expand internal ones. Refusing the shape is narrower than adding a
        # parser dependency, and reads to the report as what it is - a
        # declared sitemap this tool could not read.
        sitemap = "https://example.test/sitemap.xml"
        bomb = ('<?xml version="1.0"?><!DOCTYPE urlset ['
                '<!ENTITY a "aaaaaaaaaa">]><urlset><loc>&a;</loc></urlset>')
        found = self.issues({
            self.ROBOTS: Response(200, "Sitemap: /sitemap.xml\n"),
            sitemap: Response(200, bomb),
        })
        self.assertEqual([issue.rule_id for issue in found], ["seo-sitemap-invalid"])

    def test_a_sitemap_past_the_byte_cap_is_not_read_into_the_parser(self):
        sitemap = "https://example.test/sitemap.xml"
        huge = "<urlset>" + ("<url><loc>https://example.test/x</loc></url>"
                             * (crawlability.SITEMAP_BYTE_CAP // 40 + 100)) + "</urlset>"
        self.assertGreater(len(huge), crawlability.SITEMAP_BYTE_CAP)
        found = self.issues({
            self.ROBOTS: Response(200, "Sitemap: /sitemap.xml\n"),
            sitemap: Response(200, huge),
        })
        self.assertEqual([issue.rule_id for issue in found], ["seo-sitemap-invalid"])

    def test_a_declared_sitemap_http_error_is_reported(self):
        sitemap = "https://example.test/sitemap.xml"
        found = self.issues({
            self.ROBOTS: Response(200, "Sitemap: /sitemap.xml\n"),
            sitemap: Response(404),
        })
        self.assertEqual([issue.rule_id for issue in found],
                         ["seo-sitemap-http-error"])

    def test_a_declared_non_xml_sitemap_is_reported(self):
        sitemap = "https://example.test/sitemap.xml"
        found = self.issues({
            self.ROBOTS: Response(200, "Sitemap: /sitemap.xml\n"),
            sitemap: Response(200, "not <xml"),
        })
        self.assertEqual([issue.rule_id for issue in found], ["seo-sitemap-invalid"])

    def test_cross_origin_sitemap_is_not_fetched(self):
        found = self.issues({
            self.ROBOTS: Response(200, "Sitemap: https://other.test/sitemap.xml\n"),
        })
        self.assertEqual(found, [])

    def test_opt_in_site_controls_reach_the_web_audit(self):
        control_issue = Issue(rule_id="seo-robots-root-disallowed",
                              severity=SERIOUS, category=SEO,
                              source=self.ROBOTS)
        with patch("audit.crawlability.site_control_issues",
                   return_value=[control_issue]) as controls:
            result = audit.analyze_pages(
                [page("https://example.test/", "<html><body>Text</body></html>")],
                "https://example.test/", media=False, site_controls=True)
        controls.assert_called_once_with("https://example.test/")
        self.assertIn(control_issue, result.issues())
