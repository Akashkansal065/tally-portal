"""Says whether the Python running this can build the agent's Windows .exe and, if not, why.

Used by build_windows_exe.bat on every Python it finds: exit code 0 means usable. The optional
argument is a file listing the Pythons already reported, so the same one found three ways (as
`python`, as `py` and in its folder) is explained once.
"""
import os
import sys


def why_unusable():
    """One sentence on what is wrong with this Python for building the agent, or None."""
    if sys.version_info < (3, 9):
        return "is too old; the agent needs Python 3.9 or newer"
    if "AMD64" not in sys.version:
        if "ARM64" in sys.version:
            return ("is the ARM64 build. An .exe built with it only runs on ARM PCs, and the "
                    "cryptography package cannot be installed on it without Visual Studio")
        return "is not the 64-bit Windows build (the python.org file ending in -amd64.exe)"
    try:
        import tkinter  # noqa: F401
    except ImportError:
        return ("was installed without tkinter (the 'tcl/tk and IDLE' box in the Python "
                "installer), which the agent's window is built on")
    return None


def main():
    seen_file = sys.argv[1] if len(sys.argv) > 1 else None
    this_python = os.path.normcase(sys.executable)
    seen = set()
    if seen_file and os.path.exists(seen_file):
        with open(seen_file, encoding="utf-8") as f:
            seen = {line.strip() for line in f}
    why = why_unusable()
    if why and this_python not in seen:
        print(f"   - Python {sys.version.split()[0]} at {sys.executable}")
        print(f"     {why}.")
    if seen_file and this_python not in seen:
        with open(seen_file, "a", encoding="utf-8") as f:
            f.write(this_python + "\n")
    return 1 if why else 0


if __name__ == "__main__":
    sys.exit(main())
