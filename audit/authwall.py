"""Whether what was audited is the site, or the door in front of it.

Half of what is worth checking stands behind a login: an admin area, an
account page, an intranet, a staging site under basic auth. Before this the
tool did not know that and, worse, did not say so: it fetched the login
page, found three things wrong with it, and reported them with exactly the
confidence it reports a real page with. "40 pages, 3 findings" over a site
that answered with one login form forty times is not a quiet result, it is
the wrong question answered forty times.

So this pass produces **diagnostics about the run**, never findings about
the site. A login wall is not a defect of the page - it is the reason the
page in the report is not the page anyone wanted audited.

What counts as evidence, and why each one:

* **401** always carries `WWW-Authenticate`: the server is saying *how* to
  authenticate, which makes it the only status that identifies itself. The
  scheme is named in the diagnostic, because "Basic" and "Negotiate" are
  different conversations.
* **403** carries no such header. It means "not for you", which may be a
  login wall and may be a permission - so it is recorded as the weaker
  signal it is.
* **A redirect to something that looks like a sign-in address.** The status
  is 200 and the body is real, so nothing else in the pipeline notices; the
  only trace is that the final URL is not the one that was asked for.
* **A password field.** `<input type="password">`, or a form posting to
  something with login in its name. This is the signal that catches a
  single-page app, where the address never changes at all.

**One wall, not N pages.** When the same signal answers on many addresses,
the report says that: a crawl that walked into a wall found one wall, and
listing it forty times buries the fact that forty addresses were never read.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

#: The signals, weakest last. Also the translation-key stems.
HTTP_401 = "http-401"
HTTP_403 = "http-403"
LOGIN_REDIRECT = "login-redirect"
PASSWORD_FORM = "password-form"

#: Addresses that mean "sign in here". Matched on the path, so a marketing
#: page at `/why-login-matters` is not one of them, and on `returnUrl`,
#: which is how a redirect says where it will send you back to.
_LOGIN_PATH = re.compile(
    r"(^|/)(login|log-in|signin|sign-in|auth|sso|session[s]?|"
    r"account/login|users/sign_in|wp-login\.php)(/|$|\.)", re.I)
_RETURN_PARAM = re.compile(
    r"[?&](returnurl|return_to|redirect_uri|redirect_to|next|continue)=", re.I)

_PASSWORD_INPUT = re.compile(
    r"<input[^>]+type\s*=\s*[\"']?password", re.I)
_CURRENT_PASSWORD = re.compile(
    r"autocomplete\s*=\s*[\"']?current-password", re.I)
_LOGIN_FORM_ACTION = re.compile(
    r"<form[^>]+action\s*=\s*[\"'][^\"']*(login|signin|sign-in|session)", re.I)


@dataclass(frozen=True)
class Wall:
    """One address that answered with a door rather than with a page."""
    url: str
    signal: str
    #: What said so, already a string and not translated: an auth scheme, a
    #: redirect target, the form's action. It is the line a reader checks
    #: the diagnosis against.
    detail: str = ""

    @property
    def certain(self) -> bool:
        """Is this a login wall, as opposed to something that may be one?

        401 and a password field are the page saying it itself. A 403 is the
        server declining without saying why, and a redirect to `/auth` may be
        an SSO hop that lands somewhere real - both are worth reporting and
        neither is proof.
        """
        return self.signal in (HTTP_401, PASSWORD_FORM)


def _looks_like_login_url(url: str) -> bool:
    parsed = urlparse(url or "")
    return bool(_LOGIN_PATH.search(parsed.path or "")
                or _RETURN_PARAM.search(f"?{parsed.query}" if parsed.query else ""))


def inspect(page) -> Wall | None:
    """The wall this page ran into, or `None` if it is a page.

    Ordered by how much the evidence settles: a 401 names its own scheme, a
    password field is the page saying what it is, a redirect is an address
    changing under the request, and a 403 is a refusal with no reason given.
    """
    diagnostics = getattr(page, "diagnostics", None)
    url = getattr(page, "url", "") or ""
    status = getattr(diagnostics, "status_code", None)
    headers = getattr(diagnostics, "headers", None) or {}
    markup = getattr(page, "raw_html", "") or ""

    if status == 401:
        scheme = (headers.get("www-authenticate") or "").split(" ")[0]
        return Wall(url, HTTP_401, scheme or "unnamed scheme")

    if markup:
        if _PASSWORD_INPUT.search(markup) or _CURRENT_PASSWORD.search(markup):
            match = _LOGIN_FORM_ACTION.search(markup)
            return Wall(url, PASSWORD_FORM,
                        match.group(0)[:80] if match else "<input type=password>")

    final = getattr(diagnostics, "final_url", "") or ""
    if final and final != url and _looks_like_login_url(final):
        return Wall(url, LOGIN_REDIRECT, final)
    # An address that *is* a login page, reached directly rather than by
    # redirect - a crawl that followed a "Sign in" link. Only when the body
    # gave nothing away, so a real page at `/account/login/help` that has no
    # password field is not called a wall on its name alone.
    if not markup and _looks_like_login_url(url):
        return Wall(url, LOGIN_REDIRECT, url)

    if status == 403:
        return Wall(url, HTTP_403, "403 with no WWW-Authenticate")

    return None


@dataclass
class WallReport:
    """What a crawl found in front of the site, rolled up.

    `by_signal` is what makes this readable: one wall answering on forty
    addresses is one row, and the addresses are carried so nobody has to
    take the count on trust.
    """
    walls: list = field(default_factory=list)
    pages_read: int = 0

    @property
    def blocked(self) -> int:
        return len(self.walls)

    @property
    def certain(self) -> bool:
        return any(wall.certain for wall in self.walls)

    def by_signal(self) -> dict:
        grouped: dict = {}
        for wall in self.walls:
            grouped.setdefault(wall.signal, []).append(wall)
        return grouped

    @property
    def whole_site(self) -> bool:
        """Was *everything* the crawl reached a door?

        The case that matters most, and the one a count alone hides: a run
        that read nothing but login pages has audited nothing, and its clean
        summary is the most misleading output this tool can produce.
        """
        return bool(self.walls) and self.blocked >= self.pages_read


def scan(pages) -> WallReport:
    """Every wall in a crawl's results, with what was read alongside."""
    report = WallReport()
    for page in pages or ():
        report.pages_read += 1
        wall = inspect(page)
        if wall is not None:
            report.walls.append(wall)
    return report
