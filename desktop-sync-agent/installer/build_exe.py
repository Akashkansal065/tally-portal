"""Bundle the sync agent into dist/SnehDistribuorsSync.exe: one file, no Python needed on the PC that runs it.
Run on Windows from anywhere; build_windows_exe.bat and the GitHub workflow both call this, so there is one
list of what goes into the .exe."""
import os
import sys

import PyInstaller.__main__

EXE_NAME = "SnehDistribuorsSync"
# The .py modules are compiled into the exe by PyInstaller's import analysis; nothing reads them as files when
# frozen (config.get_app_dir / autostart use sys.executable; get_asset_path only looks up assets/ and ui/), so
# they are not added as data: that would ship readable source inside the exe.


def main() -> None:
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    args = [
        "--noconfirm", "--onefile", "--windowed", "--name", EXE_NAME,
        "--icon", os.path.join("assets", "icon.ico"),
        "--collect-all", "customtkinter", "--copy-metadata", "customtkinter",
        "--collect-submodules", "keyring", "--copy-metadata", "keyring",
        "--add-data", f"assets{os.pathsep}assets",
        "--add-data", f"ui{os.pathsep}ui",          # the web window's page
        "--hidden-import", "webview",                # pywebview; without it the .exe opens the classic window
    ]
    PyInstaller.__main__.run(args + sys.argv[1:] + ["gui_app.py"])


if __name__ == "__main__":
    main()
