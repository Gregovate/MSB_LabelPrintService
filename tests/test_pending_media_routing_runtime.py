"""Behavior tests for media-aware pending-work routing."""

from __future__ import annotations

import unittest

from pending_media_routing_runtime import (
    PendingMediaWorkload,
    select_pending_media_workload,
)


class PendingMediaRoutingTests(unittest.TestCase):
    def test_24mm_controller_bypasses_waiting_36mm_display(self) -> None:
        decision = select_pending_media_workload(
            [
                PendingMediaWorkload(
                    "DISPLAY", 36, label_template_id=1,
                    label_family_code="QR_36MM_HORIZONTAL",
                ),
                PendingMediaWorkload("CONTROLLER", 24),
            ],
            detected_width_mm=24,
        )

        self.assertEqual(decision.selected.workload_type, "CONTROLLER")
        self.assertTrue(decision.used_media_match)

    def test_36mm_display_remains_first_when_36mm_is_loaded(self) -> None:
        decision = select_pending_media_workload(
            [
                PendingMediaWorkload(
                    "DISPLAY", 36, label_template_id=1,
                    label_family_code="QR_36MM_HORIZONTAL",
                ),
                PendingMediaWorkload("CONTROLLER", 24),
            ],
            detected_width_mm=36,
        )

        self.assertEqual(decision.selected.workload_type, "DISPLAY")
        self.assertTrue(decision.used_media_match)

    def test_matching_display_family_is_selected_from_mixed_families(self) -> None:
        decision = select_pending_media_workload(
            [
                PendingMediaWorkload(
                    "DISPLAY", 36, label_template_id=1,
                    label_family_code="QR_36MM_HORIZONTAL",
                ),
                PendingMediaWorkload(
                    "DISPLAY", 24, label_template_id=2,
                    label_family_code="QR_24MM_HORIZONTAL",
                ),
            ],
            detected_width_mm=24,
        )

        self.assertEqual(decision.selected.label_template_id, 2)

    def test_unreadable_status_preserves_deterministic_preflight_fallback(self) -> None:
        first = PendingMediaWorkload(
            "DISPLAY", 36, label_template_id=1,
            label_family_code="QR_36MM_HORIZONTAL",
        )
        decision = select_pending_media_workload(
            [first, PendingMediaWorkload("CONTROLLER", 24)],
            detected_width_mm=None,
        )

        self.assertEqual(decision.selected, first)
        self.assertFalse(decision.used_media_match)
        self.assertEqual(decision.compatible_workloads, ())

    def test_no_matching_width_preserves_preflight_fallback(self) -> None:
        first = PendingMediaWorkload(
            "DISPLAY", 36, label_template_id=1,
            label_family_code="QR_36MM_HORIZONTAL",
        )
        decision = select_pending_media_workload(
            [first, PendingMediaWorkload("CONTROLLER", 24)],
            detected_width_mm=12,
        )

        self.assertEqual(decision.selected, first)
        self.assertFalse(decision.used_media_match)

    def test_invalid_candidate_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Display routing requires"):
            PendingMediaWorkload("DISPLAY", 24)


if __name__ == "__main__":
    unittest.main()
