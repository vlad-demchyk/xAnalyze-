.PHONY: rebuild-cli rebuild-app version check-cli check-app package

SHELL := /bin/bash
VENV := venv
PY := $(VENV)/bin/python
PYINST := $(VENV)/bin/pyinstaller

# Read version from the single source of truth.
SOURCE_VERSION := $(shell $(PY) -c "import config; print(config.APP_VERSION)")

CLI_DIR  := dist/xanalyze-cli
APP_DIR  := dist/XAnalyze.app
CLI_SPEC := packaging/XAnalyze-cli.spec
APP_SPEC := packaging/XAnalyze.spec

# --- version ---

version:
	@echo "$(SOURCE_VERSION)"

# --- checks: is the built binary up to date? ---

check-cli:
	@if [ ! -f "$(CLI_DIR)/.build_version" ]; then \
		echo "CLI not built yet"; exit 1; \
	fi
	@BUILD_VER=$$(cat "$(CLI_DIR)/.build_version"); \
	if [ "$$BUILD_VER" != "$(SOURCE_VERSION)" ]; then \
		echo "CLI is stale: built $$BUILD_VER, source $(SOURCE_VERSION)"; exit 1; \
	fi
	@echo "CLI $(SOURCE_VERSION) is up to date"

check-app:
	@PLIST_VER=$$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$(APP_DIR)/Contents/Info.plist" 2>/dev/null); \
	if [ "$$PLIST_VER" != "$(SOURCE_VERSION)" ]; then \
		echo "App is stale: built $$PLIST_VER, source $(SOURCE_VERSION)"; exit 1; \
	fi
	@echo "App $(SOURCE_VERSION) is up to date"

# --- rebuilds ---

rebuild-cli:
	@echo "Building CLI $(SOURCE_VERSION) ..."
	rm -rf "$(CLI_DIR)"
	$(PYINST) $(CLI_SPEC) --noconfirm --distpath dist
	@echo "$(SOURCE_VERSION)" > "$(CLI_DIR)/.build_version"
	@echo "CLI $(SOURCE_VERSION) built. Verify: $(CLI_DIR)/xanalyze --version"

rebuild-app:
	@echo "Building App $(SOURCE_VERSION) ..."
	rm -rf "$(APP_DIR)"
	$(PYINST) $(APP_SPEC) --noconfirm --distpath dist
	@echo "App $(SOURCE_VERSION) built. Verify: $(APP_DIR)/Contents/MacOS/XAnalyze --version"

rebuild-all: rebuild-cli rebuild-app

# --- release artefacts ---
#
# The names are not decorative: `updater.py` looks for exactly these, in this
# order, when `xanalyze update` asks GitHub for the latest release. A release
# whose assets are named anything else is a release nobody can update to.
#
# Both are rebuilt from what is in `dist/` right now and refuse to run over a
# stale bundle: publishing an archive of the previous version under this
# version's tag is the one packaging mistake that cannot be spotted by
# looking at the release page.

ARCH := $(shell uname -m | sed 's/x86_64/x64/')
CLI_ARCHIVE := dist/xanalyze-cli-macos-$(ARCH).tar.gz
APP_ARCHIVE := dist/XAnalyze.app.zip

package: check-cli check-app
	@echo "Packaging $(SOURCE_VERSION) for $(ARCH) ..."
	rm -f "$(CLI_ARCHIVE)" "$(APP_ARCHIVE)"
	cd dist && tar czf "$(notdir $(CLI_ARCHIVE))" "$(notdir $(CLI_DIR))"
	cd dist && ditto -c -k --sequesterRsrc --keepParent "$(notdir $(APP_DIR))" "$(notdir $(APP_ARCHIVE))"
	@echo "Wrote:"
	@ls -lh "$(CLI_ARCHIVE)" "$(APP_ARCHIVE)" | awk '{print "  " $$9 "  " $$5}'
	@echo "These are the two asset names that 'xanalyze update' looks for."
	@echo "Unsigned: a first launch of the app needs Control-click > Open until it is notarised."


# --- convenience: rebuild only if version drifted ---

update: check-cli
	@echo "CLI is up to date, nothing to do"
