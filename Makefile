.PHONY: rebuild check version package rebuild-cli rebuild-app rebuild-all check-cli check-app update

SHELL := /bin/bash
VENV := venv
PY := $(VENV)/bin/python
PYINST := $(VENV)/bin/pyinstaller

# Read version from the single source of truth.
SOURCE_VERSION := $(shell $(PY) -c "import config; print(config.APP_VERSION)")

# One bundle. The window, the command line and the terminal interface are one
# executable that picks its role by the name it was started under (see
# app_entry.py); `xanalyze` is a symlink into the app. A second, separate CLI
# bundle used to be built here, released beside the app and updated on its
# own - two copies of one program that could be two versions at once.
APP_DIR  := dist/XAnalyze.app
APP_SPEC := packaging/XAnalyze.spec

# --- version ---

version:
	@echo "$(SOURCE_VERSION)"

# --- check: is the built app up to date? ---

check:
	@PLIST_VER=$$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$(APP_DIR)/Contents/Info.plist" 2>/dev/null); \
	if [ "$$PLIST_VER" != "$(SOURCE_VERSION)" ]; then \
		echo "App is stale: built $$PLIST_VER, source $(SOURCE_VERSION)"; exit 1; \
	fi
	@echo "XAnalyze $(SOURCE_VERSION) is up to date (window, CLI and TUI)"

# --- rebuild ---

rebuild:
	@echo "Building XAnalyze $(SOURCE_VERSION) ..."
	rm -rf "$(APP_DIR)" dist/xanalyze-cli
	$(PYINST) $(APP_SPEC) --noconfirm --distpath dist
	@echo "XAnalyze $(SOURCE_VERSION) built. Verify: $(APP_DIR)/Contents/MacOS/XAnalyze --version"
	@echo "Command line from it: $(APP_DIR)/Contents/MacOS/XAnalyze --install-cli"

# The old names, so scripts and habits keep working: there is one bundle now.
rebuild-cli rebuild-app rebuild-all: rebuild
check-cli check-app: check

# --- release artefact ---
#
# One archive and its manifest: `XAnalyze.app.zip` is the name `updater.py`
# looks for. Packed with `ditto`, which keeps the bundle's symlinks (Qt's
# frameworks are built of them) and its executable bits; the updater unpacks
# both back. Refuses to run over a stale bundle: publishing the previous
# version's archive under this version's tag is the one packaging mistake
# that cannot be spotted by looking at the release page.

APP_ARCHIVE := dist/XAnalyze.app.zip

package: check
	@echo "Packaging $(SOURCE_VERSION) ..."
	rm -f "$(APP_ARCHIVE)" dist/xanalyze-cli-macos-*.tar.gz
	cd dist && ditto -c -k --sequesterRsrc --keepParent "$(notdir $(APP_DIR))" "$(notdir $(APP_ARCHIVE))"
	$(PY) scripts/update_manifest.py \
		--release "v$(SOURCE_VERSION)" \
		--output dist/xanalyze-update-manifest.json \
		"$(APP_ARCHIVE)"
	@echo "Wrote:"
	@ls -lh "$(APP_ARCHIVE)" | awk '{print "  " $$9 "  " $$5}'
	@echo "The update manifest is unsigned unless UPDATE_SIGNING_KEY is set."
	@echo "Unsigned: a first launch of the app needs Control-click > Open until it is notarised."


# --- convenience ---

update: check
	@echo "Nothing to rebuild"
