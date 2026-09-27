"""The team pack is shared as a zip, away from the repository, so every link in it must still work there."""

from __future__ import annotations

import hashlib
import importlib.util
import re
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("make_team_pack", ROOT / "scripts" / "make_team_pack.py")
make_team_pack = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(make_team_pack)


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    out = tmp_path_factory.mktemp("pack")
    zip_path = make_team_pack.build(out)
    return out / make_team_pack.NAME, zip_path


def test_the_guides_and_the_video_script_are_at_the_top(pack):
    folder, _ = pack
    guides = sorted(p.name for p in (ROOT / "docs" / "team-pack").glob("*.md"))
    assert guides and all((folder / g).is_file() for g in guides)
    assert (folder / "VIDEO_SCRIPT.md").is_file() and (folder / "MANIFEST.txt").is_file()


def test_every_relative_link_resolves_inside_the_pack(pack):
    folder, _ = pack
    broken = []
    for md in folder.rglob("*.md"):
        for target in re.findall(r"\[[^\]]*\]\(([^)\s]+)\)", md.read_text(encoding="utf-8")):
            if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I) or target.startswith("#"):
                continue
            if not (md.parent / target.partition("#")[0]).exists():
                broken.append(f"{md.relative_to(folder)} -> {target}")
    assert not broken, broken


def test_a_link_to_code_goes_to_github_not_to_a_dead_relative_path():
    mapping = {"docs/team-pack/x.md": "x.md", "docs/RESULTS.md": "reference/docs/RESULTS.md"}
    out = make_team_pack.rewrite_links(
        "[r](../RESULTS.md#tables) [e](../../reliability/remediation/engine.py) [w](https://x.org/a.md) [a](#top)",
        "docs/team-pack/x.md", mapping)
    assert "[r](reference/docs/RESULTS.md#tables)" in out
    assert f"[e]({make_team_pack.GITHUB}/blob/main/reliability/remediation/engine.py)" in out
    assert "[w](https://x.org/a.md)" in out and "[a](#top)" in out


def test_the_manifest_hashes_match_the_zip(pack):
    folder, zip_path = pack
    manifest = (folder / "MANIFEST.txt").read_text(encoding="utf-8")
    rows = re.findall(r"^([0-9a-f]{64})\s+\d+\s+(.+)$", manifest, re.M)
    with zipfile.ZipFile(zip_path) as z:
        names = set(z.namelist())
        assert rows and len(rows) == len(names) - 1  # every file but the manifest itself
        for digest, rel in rows:
            assert hashlib.sha256(z.read(f"{make_team_pack.NAME}/{rel}")).hexdigest() == digest


def test_the_builder_never_deletes_a_folder_it_did_not_make(tmp_path):
    precious = tmp_path / make_team_pack.NAME
    precious.mkdir()
    (precious / "keep.txt").write_text("mine", encoding="utf-8")
    with pytest.raises(SystemExit):
        make_team_pack.build(tmp_path)
    assert (precious / "keep.txt").is_file()
