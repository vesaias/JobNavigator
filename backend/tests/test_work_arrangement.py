"""Tests for analyzer/work_arrangement.py — the remote/hybrid/onsite cascade.

The negative cases matter more than the positive ones. A naive substring test
over the description marks roughly four jobs wrongly for each correct one, and
every phrase in `test_description_noise_is_not_remote` was taken from a real
posting in the feed.
"""
import pytest

from backend.analyzer.work_arrangement import (
    HYBRID,
    ONSITE,
    REMOTE,
    apply_arrangement_to_job,
    extract_arrangement,
    from_structured,
    from_token,
)


class FakeJob:
    """Only the attributes the extractor touches."""

    def __init__(self, location=None, title=None, description=None,
                 arr_remote=None, arr_hybrid=None, arr_onsite=None):
        self.id = "job-1"
        self.location = location
        self.title = title
        self.description = description
        self.arr_remote = arr_remote
        self.arr_hybrid = arr_hybrid
        self.arr_onsite = arr_onsite
        self.remote = None

    @property
    def flags(self):
        return (self.arr_remote, self.arr_hybrid, self.arr_onsite)


# ── tier 1: the source's own field ───────────────────────────────────────────

@pytest.mark.parametrize("value,expected", [
    ("Remote", REMOTE),
    ("REMOTE", REMOTE),
    ("Hybrid", HYBRID),
    ("On-site", ONSITE),
    ("Onsite", ONSITE),
    ("In Office", ONSITE),
    ("Unspecified", None),
    ("", None),
    (None, None),
    ("something we never saw", None),
])
def test_structured_values(value, expected):
    assert from_structured(value) == expected


def test_structured_boolean_true_means_remote():
    """Ashby's `isRemote` is a boolean."""
    assert from_structured(True) == REMOTE


def test_structured_boolean_false_is_not_onsite():
    """`False` means "not flagged remote", which is not the same as onsite."""
    assert from_structured(False) is None


# ── tier 2/3: a token in location or title ───────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("Remote", REMOTE),
    ("Remote - US", REMOTE),
    ("San Francisco, CA · Remote", REMOTE),
    ("Seattle, WA · Hybrid", HYBRID),
    ("Technical Leader (Remote)", REMOTE),
    ("Staff Engineer [Hybrid]", HYBRID),
    ("Vancouver, British Columbia, Canada", None),
])
def test_token_extraction(text, expected):
    assert from_token(text) == expected


def test_token_ignores_a_word_inside_another_word():
    assert from_token("Remotesensing Engineer") is None


# ── tier 4: explicit phrases in the description ──────────────────────────────

@pytest.mark.parametrize("description,expected", [
    ("This role is 100% remote in Canada.", REMOTE),
    ("We are hiring for a remote position on the platform team.", REMOTE),
    ("All roles with the company are global and remote-based.", REMOTE),
    ("This role is available in the following locations: Remote", REMOTE),
    ("The majority of our employees can live and work anywhere in the U.S.", REMOTE),
    ("This role operates in a hybrid capacity.", HYBRID),
    ("You will be in the office for 3 days per week.", HYBRID),
    ("Work Arrangement Hybrid: blending in-person and remote work.", HYBRID),
    ("This position is fully on-site at our Vancouver location.", ONSITE),
])
def test_description_phrases(description, expected):
    assert extract_arrangement(description=description)["arrangement"] == expected


@pytest.mark.parametrize("description", [
    # Every one of these appeared in a real posting and a substring test
    # would mark all of them remote.
    "Establish module standards, remote state, and GitOps-based plan/apply pipelines.",
    "Terraform proficiency: module authoring, state management, remote backends.",
    "Secure network access for CI/CD and remote dev environments (Tailscale).",
    "Secure Remote Access and Mobility via SSL and IPsec VPN.",
    "Experience with device telemetry and remote lifecycle management.",
    "Comfort collaborating asynchronously across remote-first, global engineering teams.",
])
def test_description_noise_is_not_remote(description):
    assert extract_arrangement(description=description)["arrangement"] is None


@pytest.mark.parametrize("description", [
    # "hybrid" is also an infrastructure word. None of these is a work arrangement.
    "Experience designing hybrid-cloud deployments across AWS and on-prem.",
    "You will own our hybrid cloud infrastructure and the service mesh.",
    "Familiarity with hybrid network architecture and multi-cloud routing.",
    "Build a hybrid search environment over Elasticsearch and pgvector.",
])
def test_hybrid_noise_is_not_hybrid(description):
    assert extract_arrangement(description=description)["arrangement"] is None


def test_label_form_of_hybrid_is_detected():
    text = "Work Arrangement Hybrid: you will split your week between home and the office."
    assert extract_arrangement(description=text)["arrangement"] == HYBRID


def test_negated_remote_is_not_remote():
    text = "This is not a remote role. You must be in our Toronto office."
    assert extract_arrangement(description=text)["arrangement"] != REMOTE


def test_conditional_remote_is_not_remote():
    text = ("The role is based out of a local office. However, we may be willing to "
            "consider exceptionally qualified remote candidates within the US and Canada.")
    assert extract_arrangement(description=text)["arrangement"] is None


@pytest.mark.parametrize("text", [
    "You will be in the office Tuesday, Wednesday and Thursday. "
    "As a perk, we also have up to four weeks per year of fully remote work!",
    # The wording of a real posting: the count is a word, and "per week" sits
    # between "office" and the weekday list.
    "We have designated days in the office per week, Monday, Wednesday and "
    "Thursday. As a perk, we also have up to four weeks per year of fully remote work!",
])
def test_hybrid_outranks_a_remote_perk(text):
    """A hybrid posting that also advertises remote weeks stays hybrid."""
    assert extract_arrangement(description=text)["arrangement"] == HYBRID


def test_html_description_is_stripped():
    text = "<div><p>This role is <b>100% remote</b> in Canada.</p></div>"
    assert extract_arrangement(description=text)["arrangement"] == REMOTE


def test_unknown_description_stays_none():
    text = "We are looking for a senior engineer to join the platform team."
    result = extract_arrangement(description=text)
    assert result["arrangement"] is None
    assert result["arrangement_source"] is None


# ── cascade order ────────────────────────────────────────────────────────────

def test_structured_field_beats_the_description():
    result = extract_arrangement(
        description="This role is 100% remote.", structured="Hybrid")
    assert result["arrangement"] == HYBRID
    assert result["arrangement_source"] == "structured"


def test_location_beats_the_description():
    result = extract_arrangement(
        location="Toronto, Ontario, Canada · Hybrid",
        description="This role is 100% remote.")
    assert result["arrangement"] == HYBRID
    assert result["arrangement_source"] == "location"


def test_title_beats_the_description():
    result = extract_arrangement(
        title="Staff Engineer (Remote)",
        description="You will be in the office 3 days per week.")
    assert result["arrangement"] == REMOTE
    assert result["arrangement_source"] == "title"


# ── apply_arrangement_to_job ─────────────────────────────────────────────────

def test_apply_sets_the_remote_flag():
    job = FakeJob(description="This role is 100% remote in Canada.")
    apply_arrangement_to_job(job)
    assert job.flags == (True, False, False)
    assert job.remote is True


def test_apply_sets_the_hybrid_flag():
    job = FakeJob(description="This role operates in a hybrid capacity.")
    apply_arrangement_to_job(job)
    assert job.flags == (False, True, False)
    assert job.remote is False


def test_unknown_is_its_own_state_not_a_false():
    """All three NULL is the fourth state. It must never read as "not remote"."""
    job = FakeJob(description="We are looking for a senior engineer.")
    apply_arrangement_to_job(job)
    assert job.flags == (None, None, None)
    assert job.remote is None


def test_a_posting_can_carry_two_arrangements():
    """"Remote or Hybrid" answers either filter."""
    job = FakeJob(location="Remote or Hybrid")
    apply_arrangement_to_job(job)
    assert job.flags == (True, True, False)


def test_a_structured_collection_sets_both_flags():
    """A board exposing independent flags hands the handler a collection."""
    job = FakeJob()
    apply_arrangement_to_job(job, structured=["Remote", "Hybrid"])
    assert job.flags == (True, True, False)


def test_apply_does_not_overwrite_existing_flags():
    """A value the scraper already set wins over anything the cascade finds."""
    job = FakeJob(description="This role is 100% remote.",
                  arr_remote=False, arr_hybrid=True, arr_onsite=False)
    apply_arrangement_to_job(job)
    assert job.flags == (False, True, False)


def test_apply_uses_the_structured_argument():
    job = FakeJob(location="Vancouver, British Columbia, Canada")
    apply_arrangement_to_job(job, structured="Remote")
    assert job.flags == (True, False, False)


def test_apply_tolerates_empty_fields():
    job = FakeJob()
    apply_arrangement_to_job(job)
    assert job.flags == (None, None, None)
