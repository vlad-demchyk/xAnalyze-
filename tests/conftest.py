"""One temporary config directory for the whole test run.

A test that touches `Settings` used to write the developer's real
`~/.config/xanalyze/settings.json`, because `config.CONFIG_FILE` was a module
constant computed during import: by the time a test could set
`XDG_CONFIG_HOME`, the path was already decided. That is not a theoretical
hazard. `tests/test_devserver_gui.py` flipped the real auto-start toggle on
disk and passed, and `tests/test_ui_suppression.py` carried three copies of

    window.settings.save = lambda: None  # do not touch the real settings.json

which is what the absence of a mechanism looks like: every author has to
remember, and forgetting is silent. See `P-13`.

`config.config_file()` now resolves the path at the moment of the read or the
write, so pointing one environment variable at a temporary directory isolates
the entire process — including code that saves settings five call levels deep,
which is where the leaks actually came from.

Set here, at collection time, rather than in a fixture: `config` is imported at
module scope by most of the suite, and `_config_dir()` creates the directory as
a side effect of the first call.

`tests/test_renaming_migration.py` overrides this again per test, and must: its
subject *is* the directory logic, so it needs to control both the old and the
new location itself.
"""
from __future__ import annotations

import os
import tempfile

#: Kept alive for the process, not cleaned per test. The directory is the
#: shared "user config" the whole run sees, and removing it between tests
#: would make settings vanish mid-suite for no reason a test could explain.
_CONFIG_HOME = tempfile.TemporaryDirectory(prefix="xanalyze-tests-config-")
os.environ["XDG_CONFIG_HOME"] = _CONFIG_HOME.name
