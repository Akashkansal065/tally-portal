"""Bundle the sync agent into dist/SnehDistribuorsSync.exe: one file, no Python needed on the PC that runs it.
Run on Windows from anywhere; build_windows_exe.bat and the GitHub workflow both call this, so there is one
list of what goes into the .exe."""
import os
import sys

import PyInstaller.__main__

EXE_NAME = "SnehDistribuorsSync"
# Read at run time from beside the program, so they travel as files as well as imports
MODULES = ["security.py", "config.py", "agent.py", "tally_client.py", "cloud_client.py", "bridge_core.py", "webview_app.py"]


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
    for module in MODULES:
        args += ["--add-data", f"{module}{os.pathsep}."]
    PyInstaller.__main__.run(args + sys.argv[1:] + ["gui_app.py"])


if __name__ == "__main__":
    main()
