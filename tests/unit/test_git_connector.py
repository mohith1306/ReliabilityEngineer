"""Git connector tests -- identity resolution and topic mapping.

Identity resolution is the part with real consequences: splitting one person across
several agent ids spreads their claims across rows and lowers measured ownership
concentration. Session 0004 found 17 (name, email) pairs for 4 people in one real
repository, including a contributor whose git config produced a different email on
each of six machines.
"""

import pytest

from connectors.git import default_topic_fn, resolve_identities


# ── identity resolution ───────────────────────────────────────────────────────

def test_same_email_different_names_is_one_person():
    """Observed: `csdeepak` and `C S DEEPAK` share a GitHub noreply address."""
    r = resolve_identities([("csdeepak", "a@x.com"), ("C S DEEPAK", "a@x.com")])
    assert len(set(r.values())) == 1


def test_same_name_different_emails_is_one_person():
    """Observed: git defaulting to user@hostname across six machines."""
    pairs = [("Dhrithi Kiran", f"d@Dhrithis-MacBook-Pro-{n}.local") for n in range(6)]
    pairs.append(("Dhrithi Kiran", "dhrithi@gmail.com"))
    assert len(set(resolve_identities(pairs).values())) == 1


def test_resolution_is_transitive():
    """A -> B by email, B -> C by name, so all three are one person."""
    r = resolve_identities(
        [("alice", "a@x.com"), ("Alice A", "a@x.com"), ("Alice A", "alice@home.local")]
    )
    assert len(set(r.values())) == 1


def test_genuinely_different_people_stay_separate():
    r = resolve_identities([("alice", "a@x.com"), ("bob", "b@x.com")])
    assert len(set(r.values())) == 2


def test_smart_quotes_in_an_email_do_not_split_a_person():
    """Observed: a git config carrying a curly quote inside the address itself."""
    r = resolve_identities([("Chandra", "c@x.com"), ("\u201cChandra-sand\u201d", "\u201cc@x.com")])
    assert len(set(r.values())) == 1


def test_case_and_spacing_are_folded():
    r = resolve_identities([("Bhavith Kumar", "b@x.com"), ("bhavithkumar", "other@x.com")])
    assert len(set(r.values())) == 1


def test_id_is_an_email_not_a_display_name():
    """Emails are more stable than display names, so they win as the id."""
    ids = set(resolve_identities([("alice", "a@x.com"), ("Alice A", "a@x.com")]).values())
    assert ids == {"a@x.com"}


def test_empty_input_is_not_an_error():
    assert resolve_identities([]) == {}


# ── topic mapping ─────────────────────────────────────────────────────────────

@pytest.fixture
def topics(tmp_path):
    return default_topic_fn(tmp_path)


def test_source_root_is_stepped_past(topics):
    """src/<pkg>/<topic>/file -- the topic is the subsystem, qualified by package.

    Qualified rather than bare so that src/foo/utils and src/bar/utils are two
    subsystems, not one. Topic *naming* does not affect any concentration metric;
    only the partition does, and this partition is the finer one.
    """
    assert topics("src/asmos/ownership/trust.py") == ["asmos/ownership"]


def test_same_subsystem_name_in_two_packages_does_not_collide(topics):
    assert topics("src/foo/utils/a.py") != topics("src/bar/utils/a.py")


def test_shallow_source_path_falls_back_to_the_package(topics):
    assert topics("src/asmos/__init__.py") == ["asmos"]


def test_plain_directory_is_the_topic(topics):
    assert topics("reliability/risk/classifier.py") == ["reliability"]


def test_root_level_file_has_no_topic(topics):
    """A catch-all bucket dilutes every concentration metric computed over it."""
    assert topics("README.md") == []
    assert topics("pyproject.toml") == []


def test_dotfiles_and_vendor_dirs_are_excluded(topics):
    assert topics(".github/workflows/ci.yml") == []
    assert topics("node_modules/left-pad/index.js") == []
    assert topics("venv/Lib/site-packages/x.py") == []


def test_empty_path_is_safe(topics):
    assert topics("") == []
