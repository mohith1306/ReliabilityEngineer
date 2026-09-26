"""Builds the seeded fixture repositories with git history, for tests and the
evaluation harness alike.

A nested `.git` cannot be committed to this repository, so history is always
constructed at runtime. Each fixture ships a regression *story*: commit 1 has
the healthy config, commit 2 restores the failing state that the fixture files
on disk contain -- the same "a commit lowered a value and broke CI" shape a real
investigation would trace.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"

_GIT_ID = ["-c", "user.email=bre-test@example.com", "-c", "user.name=BRE Test"]


@dataclass(frozen=True)
class RegressionStory:
    """How the fixture's git history reads: healthy first, regression second."""

    file: str            # config file under the fixture
    failing: str         # the state on disk (the regression)
    healthy: str         # what the first commit should contain
    import_message: str
    regression_message: str


REGRESSION_STORIES: dict[str, RegressionStory] = {
    "seeded_failure": RegressionStory(
        file="config/app.yaml",
        failing="pool_size: 2",
        healthy="pool_size: 20",
        import_message="import dataforge connection pool",
        regression_message="lower database pool_size to 2 under memory pressure",
    ),
    "auth_timeout": RegressionStory(
        file="config/auth.yaml",
        failing="request_timeout_seconds: 0.001",
        healthy="request_timeout_seconds: 5",
        import_message="import auth service",
        regression_message="cut auth request timeout to 0.001s under load",
    ),
}


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *_GIT_ID, *args],
        cwd=repo, capture_output=True, text=True, check=True,
    )


def build_fixture_repo(name: str, dest: Path) -> Path:
    """Copy fixture `name` to `dest` and give it its two-commit git history."""
    src = FIXTURES_DIR / name
    if not src.is_dir():
        raise FileNotFoundError(f"unknown fixture repository: {name} ({src})")
    if dest.exists():
        raise FileExistsError(f"destination already exists: {dest}")

    shutil.copytree(src, dest)

    story = REGRESSION_STORIES.get(name)
    _git(dest, "init", "-q")
    if story is None:
        _git(dest, "add", "-A")
        _git(dest, "commit", "-q", "-m", f"import {name}")
        return dest

    target = dest / story.file
    original = target.read_text()
    if story.failing not in original:
        raise ValueError(
            f"fixture {name}: {story.file} does not contain {story.failing!r}"
        )
    target.write_text(original.replace(story.failing, story.healthy))
    _git(dest, "add", "-A")
    _git(dest, "commit", "-q", "-m", story.import_message)

    target.write_text(original)
    _git(dest, "add", "-A")
    _git(dest, "commit", "-q", "-m", story.regression_message)
    return dest
