"""Pure routing rules for unresolved failed label batches.

An unresolved failed batch must continue to freeze its own workload so the
same source requests cannot be submitted again. It must not, however, turn an
unrelated Display, Container, or Controller failure into a global service
shutdown once the shared-printer active-job guards have already passed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FailedBatchRoutingDecision:
    """Pending counts remaining eligible after workload-specific blocking."""

    display_pending: int
    container_pending: int
    controller_pending: int
    blocked_workloads: tuple[str, ...]
    eligible_workloads: tuple[str, ...]

    @property
    def all_pending_work_blocked(self) -> bool:
        """Return true when no workload remains eligible in this poll."""

        return (
            self.display_pending == 0
            and self.container_pending == 0
            and self.controller_pending == 0
        )


def isolate_failed_batch_workloads(
    *,
    display_pending: int,
    container_pending: int,
    controller_pending: int,
    failed_display_batch_id: int | None,
    failed_container_batch_id: int | None,
    failed_controller_batch_id: int | None,
) -> FailedBatchRoutingDecision:
    """Freeze only workload types that own an unresolved failed batch.

    The caller remains responsible for the global active-PRINTING-batch and
    printer-queue guards. This function only decides which *pending workload
    types* may advance to preflight and snapshot creation.
    """

    pending = {
        "DISPLAY": int(display_pending),
        "CONTAINER": int(container_pending),
        "CONTROLLER": int(controller_pending),
    }
    if any(count < 0 for count in pending.values()):
        raise ValueError("Pending label counts cannot be negative")

    failed = {
        "DISPLAY": failed_display_batch_id,
        "CONTAINER": failed_container_batch_id,
        "CONTROLLER": failed_controller_batch_id,
    }
    blocked = tuple(
        workload
        for workload in ("DISPLAY", "CONTAINER", "CONTROLLER")
        if pending[workload] > 0 and failed[workload] is not None
    )
    eligible = tuple(
        workload
        for workload in ("DISPLAY", "CONTAINER", "CONTROLLER")
        if pending[workload] > 0 and failed[workload] is None
    )

    return FailedBatchRoutingDecision(
        display_pending=(
            0 if failed_display_batch_id is not None else pending["DISPLAY"]
        ),
        container_pending=(
            0 if failed_container_batch_id is not None else pending["CONTAINER"]
        ),
        controller_pending=(
            0
            if failed_controller_batch_id is not None
            else pending["CONTROLLER"]
        ),
        blocked_workloads=blocked,
        eligible_workloads=eligible,
    )
