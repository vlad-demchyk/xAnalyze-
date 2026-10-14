# GUI account and provider readiness

The header shows the xFormat account. AI availability follows the provider
selected in the toolbar/settings: a personal Anthropic key or Claude Code
session works without an xFormat login. A signed-in header alone cannot enable
a different provider with missing credentials. GUI probes honour the explicit
desktop provider instead of applying the CLI's automatic routing.

Status checks run on Python background threads with snapshots of settings.
Workers return account/provider results through a queue; a parented GUI-thread
QTimer applies them. The two checks are independent, so a slow xFormat response
cannot delay personal-provider readiness and a slow CLI cannot delay the header.
No widget is accessed from a worker. A generation identifies each request;
responses from an older configuration and responses after window close are ignored.

While a previously selected AI method awaits a new provider check, the run
button/shortcut waits and the choice is restored when that provider is ready.
Choosing Local explicitly during the check cancels that restoration. Local-only
runs need no provider result. InlineValue's user `activated` signal includes
reselecting the same item; programmatic changes do not emit it.

Passive xFormat probes use `auth_status(read_only=True)`: GET status does not
refresh, save or delete credentials. If an access token needs refresh and a local
refresh token exists, the stored session is retained; the user's later AI request
performs the normal refresh. Credential readiness is not proof of endpoint access,
quota or a successful billed request. Explicit sign-in selects xFormat and the
combined local/AI method; signing out of the header account does not disable an
independent personal provider.

Checking labels and run-button feedback exist in Ukrainian, Italian and English.
Tests use isolated settings, provider doubles and real Qt event loops; no paid
inference is needed. See the primary [Qt timer documentation](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QTimer.html)
and [Qt thread rules](https://doc.qt.io/qtforpython-6/overviews/qtdoc-threads-qobject.html).
