#!/usr/bin/env python3
"""
Regenerates the static GitHub Pages site (docs/site_data/) from the local
database and pushes it to GitHub -- the GitHub Pages counterpart of the old
sync_to_pythonanywhere.py. GitHub Pages republishes automatically on any push
to main, so there's no separate "reload" step the way PythonAnywhere needed.

Requires that `git push` can already run non-interactively on this machine
(i.e. Git Credential Manager has a cached credential from a prior interactive
login) -- same requirement the GitHub webhook/auto-deploy setup already relies
on elsewhere in this project.

Usage:
    python publish_static_site.py
"""
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_static_site


def _run(args):
    return subprocess.run(args, cwd=str(PROJECT_ROOT), capture_output=True, text=True)


def publish() -> bool:
    export_static_site.main()

    add = _run(["git", "add", "docs/site_data", "docs/index.html"])
    if add.returncode != 0:
        print(f"  [!] git add failed: {add.stderr}")
        return False

    # Nothing staged (data unchanged since the last publish) -- not an error.
    if _run(["git", "diff", "--cached", "--quiet"]).returncode == 0:
        print("  No data changes to publish.")
        return True

    commit = _run(["git", "commit", "-m", "Update site data (automated)"])
    if commit.returncode != 0:
        print(f"  [!] git commit failed: {commit.stderr}")
        return False

    push = _run(["git", "push", "origin", "main"])
    if push.returncode != 0:
        print(f"  [!] git push failed: {push.stderr}")
        return False

    print("  Published -- GitHub Pages will pick this up automatically.")
    return True


if __name__ == "__main__":
    ok = publish()
    sys.exit(0 if ok else 1)
