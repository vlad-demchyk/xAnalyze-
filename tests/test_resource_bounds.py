"""What one page may cost the scanner, and where a page may send it.

P-11: a page larger than `max_page_bytes` is not read, and one page cannot
queue an unbounded number of links.
P-12: a `data:` image is decoded no further than `max_image`, and all of
them together no further than `max_total`.
P-13: a page cannot make the media pass request a private address, directly
or through a redirect; the hosts the crawl itself read stay allowed.
"""
from __future__ import annotations

import base64
import functools
import http.server
import threading
import unittest
from unittest import mock

from audit import media
from crawler import EMPTY_TOO_LARGE, CrawlConfig, crawl


def _png() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (4, 4)).save(buf, "PNG")
    return buf.getvalue()


class _Handler(http.server.BaseHTTPRequestHandler):
    routes: dict = {}

    def log_message(self, *_args):
        pass

    def do_GET(self):  # noqa: N802 - the stdlib's name
        route = self.routes.get(self.path)
        if route is None:
            self.send_response(404)
            self.end_headers()
            return
        status, headers, body = route
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        if body is not None and "Content-Length" not in headers:
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)


class _Server(unittest.TestCase):
    def setUp(self):
        handler = type("H", (_Handler,), {"routes": {}})
        self.routes = handler.routes
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def html(self, path, body: str, extra_headers=None):
        headers = {"Content-Type": "text/html; charset=utf-8"}
        headers.update(extra_headers or {})
        self.routes[path] = (200, headers, body.encode("utf-8"))


class PageBytes(_Server):
    def test_a_page_past_the_ceiling_is_not_read(self):
        self.html("/", "<html><body><h1>Home</h1>"
                  + "<p>Some copy that is long enough to count.</p>" * 2000
                  + "</body></html>")
        pages = crawl(self.base + "/", CrawlConfig(max_depth=0, max_pages=1,
                                                   max_page_bytes=10_000))
        self.assertEqual(len(pages), 1)
        self.assertIn(EMPTY_TOO_LARGE, pages[0].diagnostics.reasons)
        self.assertEqual(pages[0].blocks, [])

    def test_a_server_that_lies_about_its_length_is_still_stopped(self):
        # No Content-Length at all: chunked, the length is only known by
        # reading - which is what the counter is for.
        body = ("<html><body>" + "x" * 50_000 + "</body></html>").encode()

        class Chunked(_Handler):
            routes = {}

            def do_GET(self):  # noqa: N802
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                for start in range(0, len(body), 4096):
                    part = body[start:start + 4096]
                    self.wfile.write(f"{len(part):x}\r\n".encode() + part + b"\r\n")
                self.wfile.write(b"0\r\n\r\n")

        Chunked.protocol_version = "HTTP/1.1"
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Chunked)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        pages = crawl(f"http://127.0.0.1:{server.server_port}/",
                      CrawlConfig(max_depth=0, max_pages=1, max_page_bytes=10_000))
        self.assertIn(EMPTY_TOO_LARGE, pages[0].diagnostics.reasons)

    def test_a_page_under_the_ceiling_reads_as_before(self):
        self.html("/", "<html lang='uk'><body><h1>Головна сторінка</h1>"
                  "<p>Текст сторінки, достатньо довгий, щоб його прочитати.</p>"
                  "</body></html>")
        pages = crawl(self.base + "/", CrawlConfig(max_depth=0, max_pages=1))
        self.assertNotIn(EMPTY_TOO_LARGE, pages[0].diagnostics.reasons)
        self.assertTrue(any("достатньо довгий" in b.text for b in pages[0].blocks))


class LinksPerPage(_Server):
    def test_one_page_does_not_queue_every_link_it_has(self):
        links = "".join(f'<a href="/p{i}">page {i}</a>' for i in range(50))
        self.html("/", f"<html><body><h1>Index of everything</h1>{links}</body></html>")
        for i in range(50):
            self.html(f"/p{i}", f"<html><body><h1>Page number {i}</h1></body></html>")
        pages = crawl(self.base + "/", CrawlConfig(max_depth=1, max_pages=0,
                                                   max_links_per_page=5))
        self.assertEqual(len(pages), 1 + 5)
        # Every link is still known to the audit; only the walk is narrower.
        self.assertEqual(len(pages[0].links), 50)


class InlineImages(unittest.TestCase):
    class _Page:
        def __init__(self, html):
            self.url = "https://x.test/"
            self.raw_html = html

    def test_a_huge_data_image_is_decoded_only_to_the_ceiling(self):
        payload = base64.b64encode(b"\x89PNG" + b"\0" * 3_000_000).decode()
        uri = "data:image/png;base64," + payload
        with mock.patch.object(base64, "b64decode",
                               wraps=base64.b64decode) as decode:
            scan = media.scan_page_media(
                [self._Page(f'<img src="{uri}">')], fetch=lambda u, n: (b"", True),
                max_image=4096)
        decoded_text = decode.call_args.args[0]
        self.assertLessEqual(len(decoded_text), 4096 * 4 // 3 + 4)
        self.assertEqual(scan.head_only, 1)

    def test_the_decoded_total_is_bounded_as_well(self):
        one = "data:image/png;base64," + base64.b64encode(b"\x89PNG" + b"a" * 2000).decode()
        imgs = "".join(f'<img src="{one}#{i}">' for i in range(10))
        scan = media.scan_page_media([self._Page(imgs)],
                                     fetch=lambda u, n: (b"", True),
                                     max_image=1000, max_total=3000)
        self.assertEqual(scan.skipped_budget, 10 - 3)

    def test_a_small_data_image_is_read_whole(self):
        data, complete = media._decode_data_uri(
            "data:image/png;base64," + base64.b64encode(b"tiny").decode(), 4096)
        self.assertEqual((data, complete), (b"tiny", True))

    def test_percent_encoded_payload_is_bounded_too(self):
        data, complete = media._decode_data_uri(
            "data:image/svg+xml," + "%41" * 10_000, 100)
        self.assertEqual((len(data), complete), (100, False))


class PrivateAddresses(_Server):
    def test_a_private_address_on_a_public_page_is_refused(self):
        for url in ("http://127.0.0.1/x.png", "http://169.254.169.254/latest",
                    "http://10.0.0.1/a.png", "http://[::1]/a.png",
                    "file:///etc/passwd"):
            with self.subTest(url=url):
                with self.assertRaises(media.BlockedAddress):
                    media._check_media_address(url, allowed_hosts={"x.test"})

    def test_the_host_the_crawl_read_stays_allowed(self):
        media._check_media_address("http://localhost:3000/logo.png",
                                   allowed_hosts={"localhost"})

    def test_a_redirect_into_a_private_address_is_not_followed(self):
        self.routes["/img.png"] = (302, {"Location": "http://10.0.0.1/secret"}, b"")
        # The test server itself is local, so it is the crawl's own host.
        with self.assertRaises(media.BlockedAddress):
            media._default_fetch(self.base + "/img.png", 1024,
                                 allowed_hosts={"127.0.0.1"})

    def test_a_page_on_its_own_dev_server_still_gets_its_images(self):
        png = _png()
        self.routes["/logo.png"] = (200, {"Content-Type": "image/png"}, png)

        class _Page:
            url = self.base + "/"
            raw_html = '<img src="/logo.png">'

        scan = media.scan_page_media([_Page()])
        self.assertEqual((scan.checked, scan.unreachable), (1, 0))

    def test_a_page_cannot_point_the_scanner_at_the_local_machine(self):
        png = _png()
        self.routes["/logo.png"] = (200, {"Content-Type": "image/png"}, png)

        class _Page:
            url = "https://public.example/"
            raw_html = f'<img src="{self.base}/logo.png">'

        import requests

        with mock.patch.object(requests, "get",
                               side_effect=AssertionError("fetched")) as get:
            scan = media.scan_page_media([_Page()])
        get.assert_not_called()
        self.assertEqual((scan.checked, scan.unreachable), (0, 1))


if __name__ == "__main__":
    unittest.main()
