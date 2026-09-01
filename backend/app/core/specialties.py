"""Canonical specialty vocabulary — single source of truth.

Why this module exists
======================
Historically `Doctor.specialty` is a free string and four live spellings of
the dental family coexisted across creation channels:

- ``dentistry`` — written by user provisioning (``user_mgmt/_core.py``),
  the EMR canonical value, panels and frontend routing;
- ``dental``    — written by the admin DoctorModal, whose dropdown is fed
  by the departments API (department key ``dental``);
- ``stomatology`` — the queue machinery profile key (legacy rows);
- ``dentist``   — legacy role spelling leaked into some rows.

NEEDS DECISION D-1 (2026-08-31): ``dentistry`` is THE canonical stored
value for the whole dental family. New writes are normalized at the CRUD
boundary; migration ``0049`` rewrites existing rows; read-side matching
uses :func:`specialty_variants` so any spelling finds every family row.

Rules
=====
- This module must stay import-light (no app imports) — it is imported by
  CRUD, services, provisioning and Alembic migrations alike.
- ``general`` remains the INCOMPLETE-profile sentinel (decisions #5/#13):
  it is not a bookable specialty and every eligibility filter excludes it.
- Non-dental specialties (``cardiology``, ``dermatology``, ``lab``, ...)
  are passed through untouched — they are already consistent.
"""
from __future__ import annotations

# Incomplete-profile sentinel (decision #5): SSOT moved here so CRUD,
# provisioning and migrations share one constant. ``user_mgmt._base``
# re-exports it for backwards compatibility.
INCOMPLETE_DOCTOR_SPECIALTY = "general"

# D-1: canonical value stored in Doctor.specialty for the dental family.
DENTAL_CANONICAL_SPECIALTY = "dentistry"

# Every known dental-family spelling, case-insensitively compared.
DENTAL_FAMILY_SPELLINGS = frozenset(
    {"dentistry", "dental", "stomatology", "dentist"}
)

# Doctor-onboarding vocabulary (owner decision 2026-09-01): the specialty
# domain ids an Admin may SELECT when creating a new system doctor via the
# normal ``POST /users`` flow (User.role=Doctor + doctor_profile).
# Semantics — "selectable at new-doctor onboarding", NOT "the only
# specialties that exist": this is a pilot bootstrap registry; new
# specialties are added here (plus frontend i18n labels) without new User
# roles. It must NEVER contain the incomplete sentinel or legacy dental
# spellings; values are compared exactly (canonical ids only). It is not
# tied to Department.key or queue_tags.
DOCTOR_ONBOARDING_SPECIALTIES: tuple[str, ...] = (
    "cardiology",
    "dermatology",
    "dentistry",
)


def canonical_specialty(value: str | None) -> str | None:
    """Normalize a specialty value for STORAGE (write boundary).

    - ``None`` / empty → returned unchanged (blank stays blank; the
      incomplete-profile predicates already treat blank as incomplete).
    - Any dental-family spelling (case-insensitive) → ``dentistry``.
    - Everything else → trimmed as-is (no case rewriting: legacy rows
      like ``Cardiologist`` keep their stored form; comparisons that
      need case handling use :func:`specialty_variants`).
    """
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return trimmed
    if trimmed.lower() in DENTAL_FAMILY_SPELLINGS:
        return DENTAL_CANONICAL_SPECIALTY
    return trimmed


def specialty_variants(value: str | None) -> list[str]:
    """Expand a specialty into every stored spelling to match (read side).

    Used by filters that historically compared ``Doctor.specialty``
    exactly: passing any dental spelling returns all four family
    spellings so a ``dentistry`` doctor is found when filtering by
    ``dental`` and vice versa. Unknown specialties return only their
    trimmed form (case preserved for the original input, lowercase
    family spellings for known families) — SQL ``IN`` stays
    case-sensitive, so the original input is always included verbatim.
    """
    if value is None:
        return []
    trimmed = value.strip()
    if not trimmed:
        return [trimmed]
    if trimmed.lower() in DENTAL_FAMILY_SPELLINGS:
        return sorted(DENTAL_FAMILY_SPELLINGS)
    return [trimmed]


def expand_queue_tags(tags: list[str] | None) -> list[str]:
    """Expand QueueProfile queue_tags with dental-family spellings.

    Queue profiles match ``Doctor.specialty`` against their ``queue_tags``
    (e.g. the stomatology profile carries ``["dental", "stomatology",
    "dentist"]``). Without expansion a ``dentistry`` doctor is invisible
    to the profile join (Codex round-1 / NEEDS DECISION D-1). Original
    tags are kept first, order preserved, duplicates removed.
    """
    if not tags:
        return []
    expanded: list[str] = []
    for tag in tags:
        trimmed = (tag or "").strip()
        if not trimmed:
            continue
        variants = specialty_variants(trimmed)
        for variant in variants:
            if variant and variant not in expanded:
                expanded.append(variant)
    for tag in tags:
        trimmed = (tag or "").strip()
        if trimmed and trimmed not in expanded:
            expanded.append(trimmed)
    return expanded
