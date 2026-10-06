#!/usr/bin/env python3
"""
Run ESLint on the frontend, but fail only on errors in lines changed since a base ref.

The codebase still has older lint errors being cleaned up gradually. Linting whole files
would make anyone who touches one of those files fix every old error in it, so this gate
only holds new and edited lines to the rules. Warnings are ignored.

Run from frontend-nextjs/:
    python3 ../.github/scripts/lint_changed_lines.py              # against origin/master
    python3 ../.github/scripts/lint_changed_lines.py upstream/master

Compares the working tree (committed and uncommitted changes) with the merge base of the ref.
"""
import json
import os
import re
import subprocess
import sys

PATTERNS = ["*.ts", "*.tsx", "*.js", "*.jsx", "*.mjs"]
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def changed_lines(base):
    """Map each changed file (relative to the current directory) to the set of its added or edited line numbers."""
    merge_base = git("merge-base", base, "HEAD").strip()
    diff = git("diff", "-U0", "--relative", "--diff-filter=ACMR", "--no-color", merge_base, "--", *PATTERNS)
    lines, path, prev = {}, None, ""
    for row in diff.splitlines():
        if row.startswith("+++ ") and prev.startswith("--- "):
            path = row[6:] if row.startswith("+++ b/") else None
            if path:
                lines.setdefault(path, set())
        elif path and (m := HUNK.match(row)):
            start, count = int(m.group(1)), int(m.group(2) or 1)
            lines[path].update(range(start, start + count))
        prev = row
    return {p: ls for p, ls in lines.items() if ls}


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/master"
    changed = changed_lines(base)
    if not changed:
        print("No frontend source lines changed.")
        return 0

    result = subprocess.run(
        ["npx", "eslint", "--format", "json", "--no-warn-ignored", *changed],
        capture_output=True, text=True,
    )
    try:
        reports = json.loads(result.stdout)
    except json.JSONDecodeError:
        # ESLint itself failed (bad config, crash): surface its output and fail
        sys.stderr.write(result.stdout + result.stderr)
        return 1

    cwd, prefix = os.getcwd(), os.path.relpath(os.getcwd(), git("rev-parse", "--show-toplevel").strip())
    in_ci = os.environ.get("GITHUB_ACTIONS") == "true"
    problems = 0
    for report in reports:
        path = os.path.relpath(report["filePath"], cwd)
        for msg in report["messages"]:
            line = msg.get("line")
            # Fatal parse errors have no rule and always count; otherwise only errors on changed lines
            if msg["severity"] != 2 or (msg.get("ruleId") and line not in changed.get(path, ())):
                continue
            problems += 1
            rule = msg.get("ruleId") or "parse-error"
            print(f"{path}:{line}:{msg.get('column', 0)}  {msg['message']}  ({rule})")
            if in_ci:
                print(f"::error file={prefix}/{path},line={line},col={msg.get('column', 0)},title={rule}::{msg['message']}")

    files = len(changed)
    if problems:
        print(f"\n{problems} lint error(s) in changed lines across {files} file(s).")
        return 1
    print(f"No lint errors in changed lines ({files} file(s) checked).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
