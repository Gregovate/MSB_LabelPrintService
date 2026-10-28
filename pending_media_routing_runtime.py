"""Pure media-aware routing for simultaneously pending label workloads.

The PT-P950NW is shared by Display, Container, and Controller labels.  A
pending workload whose required tape does not match the installed cassette
must not prevent another pending workload that *does* match from advancing.
The caller still owns printer-state validation and all no-double-print guards.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PendingMediaWorkload:
    """One eligible workload and the tape width it requires."""

    workload_type: str
    required_width_mm: int
    label_template_id: int | None = None
    label_family_code: str | None = None

    def __post_init__(self) -> None:
        if self.workload_type not in {"DISPLAY", "CONTAINER", "CONTROLLER"}:
            raise ValueError(f"Unsupported workload type: {self.workload_type}")
        if self.required_width_mm <= 0:
            raise ValueError("Required tape width must be positive")
        if self.workload_type == "DISPLAY" and self.label_template_id is None:
            raise ValueError("Display routing requires label_template_id")


@dataclass(frozen=True)
class PendingMediaRoutingDecision:
    """Selected workload plus evidence explaining the routing choice."""

    selected: PendingMediaWorkload
    detected_width_mm: int | None
    compatible_workloads: tuple[PendingMediaWorkload, ...]
    used_media_match: bool


def select_pending_media_workload(
    candidates: list[PendingMediaWorkload],
    *,
    detected_width_mm: int | None,
) -> PendingMediaRoutingDecision:
    """Prefer pending work compatible with the installed tape.

    Candidate order remains the deterministic fallback when status is absent,
    invalid, or no pending workload matches.  That fallback lets the existing
    full preflight produce the precise operator/requester notice instead of
    silently doing nothing.
    """

    if not candidates:
        raise ValueError("At least one pending workload candidate is required")
    if detected_width_mm is not None and detected_width_mm < 0:
        raise ValueError("Detected tape width cannot be negative")

    compatible = tuple(
        candidate
        for candidate in candidates
        if detected_width_mm not in (None, 0)
        and candidate.required_width_mm == detected_width_mm
    )
    if compatible:
        selected = compatible[0]
        used_media_match = True
    else:
        selected = candidates[0]
        used_media_match = False

    return PendingMediaRoutingDecision(
        selected=selected,
        detected_width_mm=detected_width_mm,
        compatible_workloads=compatible,
        used_media_match=used_media_match,
    )
