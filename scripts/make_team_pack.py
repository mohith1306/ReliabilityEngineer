"""Build the team pack: dist/BRE-team-pack/ and dist/BRE-team-pack.zip.

    python scripts/make_team_pack.py            # build into dist/
    python scripts/make_team_pack.py --out X    # build into X/

The pack is what a teammate opens without cloning the repository:

    00_START_HERE.md ... 05_TEAM_DOSSIER.md   the guides (docs/team-pack/)
    VIDEO_SCRIPT.md                           the annotated video script (docs/submission/)
    reference/<repo path>                     snapshot copies of the key project documents
    MANIFEST.txt                              the commit it was built from, and a sha256 per file

Relative Markdown links are rewritten so they work inside the zip: a link to a document that is in the pack
points at the copy, and a link to anything else (code, tests, artifacts) points at that file on GitHub `main`.
The repository stays the source of truth; the pack is a dated snapshot and says so.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import posixpath
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "BRE-team-pack"
GITHUB = "https://github.com/mohith1306/ReliabilityEngineer"
MARKER = ".bre-team-pack"  # the builder only ever deletes an output directory it marked itself

# repo path (posix) or glob -> where it goes in the pack. Guides and the video script sit at the top level;
# everything else is mirrored under reference/ at its repo path, which keeps link rewriting mechanical.
TOP_LEVEL = {"docs/submission/VIDEO_SCRIPT.md": "VIDEO_SCRIPT.md"}
REFERENCE_GLOBS = [
    "README.md", "CLAUDE.md",
    "docs/STATUS.md", "docs/RESULTS.md", "docs/DEMO.md",
    "docs/stages/STAGES.md",
    "docs/architecture/*.md", "docs/decisions/*.md",
    "docs/memory/INDEX.md", "docs/memory/PROTOCOL.md", "docs/memory/sessions/*.md",
    "docs/submission/*.md", "docs/submission/*.html", "docs/submission/*.png",
    "docs/submission/screenshots/**/*",
]

LINK = re.compile(r"(\[[^\]]*\]\()([^)\s]+)(\))")


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def pack_map() -> dict[str, str]:
    """repo path -> pack path, for every file that goes in the pack."""
    mapping: dict[str, str] = {}
    for p in sorted((ROOT / "docs" / "team-pack").glob("*.md")):
        mapping[p.relative_to(ROOT).as_posix()] = p.name
    for pattern in REFERENCE_GLOBS:
        for p in sorted(ROOT.glob(pattern)):
            if p.is_file():
                rel = p.relative_to(ROOT).as_posix()
                mapping.setdefault(rel, "reference/" + rel)
    mapping.update({k: v for k, v in TOP_LEVEL.items() if (ROOT / k).is_file()})
    return mapping


def rewrite_links(text: str, repo_path: str, mapping: dict[str, str]) -> str:
    """Point every relative link at the copy in the pack, or at GitHub when the pack has no copy."""
    here_repo = posixpath.dirname(repo_path)
    here_pack = posixpath.dirname(mapping[repo_path])

    def fix(m: re.Match) -> str:
        target = m.group(2)
        if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I) or target.startswith(("#", "/")):
            return m.group(0)  # absolute URL, mailto:, in-page anchor
        path, _, anchor = target.partition("#")
        resolved = posixpath.normpath(posixpath.join(here_repo, path))
        if resolved.startswith(".."):
            return m.group(0)  # points outside the repository; leave it alone
        if resolved in mapping:
            new = posixpath.relpath(mapping[resolved], here_pack or ".")
        else:
            kind = "tree" if (ROOT / resolved).is_dir() else "blob"
            new = f"{GITHUB}/{kind}/main/{resolved}"
        return m.group(1) + new + ("#" + anchor if anchor else "") + m.group(3)

    return LINK.sub(fix, text)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(out_root: Path) -> Path:
    """Build the pack folder and zip under out_root; returns the zip path."""
    out_root = out_root.resolve()
    folder = out_root / NAME
    if folder.exists():
        if not (folder / MARKER).is_file():
            raise SystemExit(f"refusing to delete {folder}: it was not created by this script")
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    (folder / MARKER).write_text("created by scripts/make_team_pack.py; safe to delete\n", encoding="utf-8")

    mapping = pack_map()
    for repo_path, pack_path in mapping.items():
        src, dst = ROOT / repo_path, folder / pack_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix == ".md":
            text = src.read_bytes().decode("utf-8")
            dst.write_bytes(rewrite_links(text, repo_path, mapping).encode("utf-8"))
        else:
            shutil.copyfile(src, dst)

    sha, branch = _git("rev-parse", "HEAD"), _git("rev-parse", "--abbrev-ref", "HEAD")
    dirty = _git("status", "--porcelain") not in ("", "unknown")
    files = sorted(p for p in folder.rglob("*") if p.is_file() and p.name != MARKER)
    lines = [
        "BRE team pack -- a dated SNAPSHOT. The repository is the source of truth:",
        f"  {GITHUB}",
        f"built    {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"commit   {sha}{'  (plus uncommitted changes)' if dirty else ''}",
        f"branch   {branch}",
        f"rebuild  python scripts/make_team_pack.py",
        "",
        f"{len(files)} files (sha256, bytes, path):",
    ]
    lines += [f"{_sha256(p)}  {p.stat().st_size:>9}  {p.relative_to(folder).as_posix()}" for p in files]
    (folder / "MANIFEST.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    zip_path = out_root / f"{NAME}.zip"
    zip_path.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(folder.rglob("*")):
            if p.is_file() and p.name != MARKER:
                z.write(p, f"{NAME}/{p.relative_to(folder).as_posix()}")
    return zip_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / "dist"), help="output directory (default: dist/)")
    args = ap.parse_args(argv)
    zip_path = build(Path(args.out))
    with zipfile.ZipFile(zip_path) as z:
        n = len(z.namelist())
    print(f"{zip_path}  ({n} files, {zip_path.stat().st_size / 1024:.0f} KiB)")
    print(f"folder: {zip_path.with_suffix('')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
