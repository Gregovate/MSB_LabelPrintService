"""Behavior tests for workload-specific failed-batch isolation."""

from __future__ import annotations

import unittest

from failed_batch_routing_runtime import isolate_failed_batch_workloads


class FailedBatchRoutingTests(unittest.TestCase):
    def test_no_failed_batch_preserves_all_pending_work(self) -> None:
        decision = isolate_failed_batch_workloads(
            display_pending=12,
            container_pending=2,
            controller_pending=5,
            failed_display_batch_id=None,
            failed_container_batch_id=None,
            failed_controller_batch_id=None,
        )

        self.assertEqual(decision.display_pending, 12)
        self.assertEqual(decision.container_pending, 2)
        self.assertEqual(decision.controller_pending, 5)
        self.assertEqual(decision.blocked_workloads, ())
        self.assertEqual(
            decision.eligible_workloads,
            ("DISPLAY", "CONTAINER", "CONTROLLER"),
        )
        self.assertFalse(decision.all_pending_work_blocked)

    def test_failed_display_freezes_display_but_releases_controller(self) -> None:
        decision = isolate_failed_batch_workloads(
            display_pending=12,
            container_pending=0,
            controller_pending=5,
            failed_display_batch_id=391,
            failed_container_batch_id=None,
            failed_controller_batch_id=None,
        )

        self.assertEqual(decision.display_pending, 0)
        self.assertEqual(decision.controller_pending, 5)
        self.assertEqual(decision.blocked_workloads, ("DISPLAY",))
        self.assertEqual(decision.eligible_workloads, ("CONTROLLER",))
        self.assertFalse(decision.all_pending_work_blocked)

    def test_each_failed_type_blocks_only_its_own_workload(self) -> None:
        decision = isolate_failed_batch_workloads(
            display_pending=3,
            container_pending=2,
            controller_pending=1,
            failed_display_batch_id=None,
            failed_container_batch_id=352,
            failed_controller_batch_id=95,
        )

        self.assertEqual(decision.display_pending, 3)
        self.assertEqual(decision.container_pending, 0)
        self.assertEqual(decision.controller_pending, 0)
        self.assertEqual(
            decision.blocked_workloads,
            ("CONTAINER", "CONTROLLER"),
        )
        self.assertEqual(decision.eligible_workloads, ("DISPLAY",))

    def test_all_pending_work_can_remain_safely_frozen(self) -> None:
        decision = isolate_failed_batch_workloads(
            display_pending=4,
            container_pending=0,
            controller_pending=0,
            failed_display_batch_id=391,
            failed_container_batch_id=None,
            failed_controller_batch_id=None,
        )

        self.assertTrue(decision.all_pending_work_blocked)
        self.assertEqual(decision.blocked_workloads, ("DISPLAY",))
        self.assertEqual(decision.eligible_workloads, ())

    def test_failure_without_pending_rows_does_not_block_other_work(self) -> None:
        decision = isolate_failed_batch_workloads(
            display_pending=0,
            container_pending=0,
            controller_pending=2,
            failed_display_batch_id=391,
            failed_container_batch_id=None,
            failed_controller_batch_id=None,
        )

        self.assertEqual(decision.blocked_workloads, ())
        self.assertEqual(decision.eligible_workloads, ("CONTROLLER",))
        self.assertEqual(decision.controller_pending, 2)

    def test_negative_pending_count_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            isolate_failed_batch_workloads(
                display_pending=-1,
                container_pending=0,
                controller_pending=0,
                failed_display_batch_id=None,
                failed_container_batch_id=None,
                failed_controller_batch_id=None,
            )


if __name__ == "__main__":
    unittest.main()
