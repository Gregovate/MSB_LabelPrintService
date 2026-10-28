"""Durable Label Print heartbeat, recovery evidence, and incident producer.

This module deliberately does not send email.  PRINT-SERVER records durable
business events in PostgreSQL; the Server Management mail worker owns SMTP.
"""

from __future__ import annotations

import json
import logging
import os
import re
import socket
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any


ConnectDatabase = Callable[[], Any]


class LabelPrintObservability:
    """Small fail-closed adapter for the database notification contract."""

    _BATCH_PATH = re.compile(
        r"(?P<workload>display|container|controller)_batch_"
        r"(?P<batch_id>[0-9]+)_",
        re.IGNORECASE,
    )

    def __init__(
        self,
        *,
        enabled: bool,
        connect_database: ConnectDatabase,
        service_version: str,
        process_id: int | None = None,
        host_name: str | None = None,
        printer_name: str = "Brother PT-P950NW",
    ) -> None:
        self.enabled = enabled
        self.connect_database = connect_database
        self.service_version = service_version
        self.process_id = process_id if process_id is not None else os.getpid()
        self.host_name = host_name or socket.gethostname()
        self.printer_name = printer_name
        self._event_lock = threading.Lock()
        self._seen_events: set[tuple[str, int, str]] = set()

    @staticmethod
    def _json(value: dict[str, Any] | None) -> str:
        return json.dumps(value or {}, sort_keys=True, default=str)

    def verify_contract(self) -> None:
        """Fail startup if enabled but the approved DB contract is absent."""
        if not self.enabled:
            return
        required = (
            "ops.label_print_bind_batch_requests(text,bigint)",
            "ops.label_print_heartbeat(text,integer,text,jsonb)",
            "ops.label_print_queue_success_events(text,bigint)",
            "ops.label_print_recovery_checkpoint(text,bigint,text,jsonb)",
            "ops.label_print_release_batch_requests(text,bigint)",
            (
                "ops.label_print_incident_upsert(text,text,text,text,text,"
                "bigint,integer,text,integer,text,text,jsonb)"
            ),
            "ops.label_print_incident_resolve(text,text,jsonb)",
        )
        with self.connect_database() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT name, to_regprocedure(name) IS NOT NULL "
                    "FROM unnest(%s::text[]) AS name;",
                    (list(required),),
                )
                missing = [name for name, present in cur.fetchall() if not present]
            conn.rollback()
        if missing:
            raise RuntimeError(
                "Label Print observability is enabled but its database "
                f"contract is incomplete: {', '.join(missing)}"
            )

    def heartbeat(self, state: str, details: dict[str, Any] | None = None) -> None:
        if not self.enabled:
            return
        with self.connect_database() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT ops.label_print_heartbeat(%s, %s, %s, %s::jsonb);",
                    (
                        self.service_version,
                        self.process_id,
                        state,
                        self._json(details),
                    ),
                )
            conn.commit()

    def bind_batch_requests(
        self,
        conn: Any,
        workload_type: str,
        batch_id: int,
    ) -> int:
        if not self.enabled:
            return 0
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ops.label_print_bind_batch_requests(%s, %s);",
                (workload_type.upper(), batch_id),
            )
            bound = int(cur.fetchone()[0])
        if bound <= 0:
            raise RuntimeError("No durable Label Print requests were bound")
        return bound

    def checkpoint_in_transaction(
        self,
        conn: Any,
        workload_type: str,
        batch_id: int,
        event_name: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        if not self.enabled:
            return
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ops.label_print_recovery_checkpoint(%s, %s, %s, %s::jsonb);",
                (
                    workload_type.upper(),
                    batch_id,
                    event_name,
                    self._json(details),
                ),
            )

    def checkpoint(
        self,
        workload_type: str,
        batch_id: int,
        event_name: str,
        details: dict[str, Any] | None = None,
        *,
        once: bool = False,
    ) -> None:
        if not self.enabled:
            return
        key = (workload_type.upper(), batch_id, event_name)
        with self._event_lock:
            if once and key in self._seen_events:
                return
            if once:
                self._seen_events.add(key)
        try:
            with self.connect_database() as conn:
                self.checkpoint_in_transaction(
                    conn, workload_type, batch_id, event_name, details
                )
                conn.commit()
        except Exception:
            if once:
                with self._event_lock:
                    self._seen_events.discard(key)
            raise

    def release_batch_requests(
        self,
        conn: Any,
        workload_type: str,
        batch_id: int,
    ) -> int:
        if not self.enabled:
            return 0
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ops.label_print_release_batch_requests(%s, %s);",
                (workload_type.upper(), batch_id),
            )
            return int(cur.fetchone()[0])

    def queue_success_events(
        self,
        conn: Any,
        workload_type: str,
        batch_id: int,
    ) -> int:
        if not self.enabled:
            return 0
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ops.label_print_queue_success_events(%s, %s);",
                (workload_type.upper(), batch_id),
            )
            return int(cur.fetchone()[0])

    def recovery_candidates(self, conn: Any) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT workload_type, batch_id, last_event,
                       submission_started, spooler_observed,
                       brother_active_observed, spooler_cleared,
                       ready_idle_observed, recovery_state, details,
                       last_seen_at
                FROM ops.label_print_recovery_candidates();
                """
            )
            columns = [item.name for item in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def incident_upsert(
        self,
        conn: Any,
        *,
        incident_key: str,
        incident_kind: str,
        workload_type: str,
        printer_name: str,
        batch_id: int | None,
        pending_count: int,
        severity: str,
        alert_delay_seconds: int,
        operator_action: str,
        recovery_state: str,
        details: dict[str, Any],
    ) -> None:
        if not self.enabled:
            return
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM ops.label_print_incident_upsert(
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s::jsonb
                );
                """,
                (
                    incident_key,
                    incident_kind,
                    workload_type.upper(),
                    printer_name,
                    self.host_name,
                    batch_id,
                    pending_count,
                    severity,
                    alert_delay_seconds,
                    operator_action,
                    recovery_state,
                    self._json(details),
                ),
            )

    def incident_resolve(
        self,
        conn: Any,
        incident_key: str,
        recovery_state: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        if not self.enabled:
            return
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM ops.label_print_incident_resolve(%s, %s, %s::jsonb);",
                (incident_key, recovery_state, self._json(details)),
            )

    def observe_batch_log(self, batch_log_path: Path, message: str) -> None:
        """Convert established runtime log evidence into durable checkpoints.

        An evidence-write failure is logged but cannot interrupt an already
        submitted physical print.  The pre-submission BATCH_CREATED checkpoint
        remains fail-closed and is written synchronously by the main thread.
        """
        if not self.enabled:
            return
        match = self._BATCH_PATH.search(batch_log_path.name)
        if not match:
            return
        workload = match.group("workload").upper()
        batch_id = int(match.group("batch_id"))
        event: str | None = None
        once = True

        if message.startswith("StartPrint called"):
            event = "SUBMISSION_STARTED"
        elif "Spooler job(s) observed:" in message:
            event = "SPOOLER_OBSERVED"
        elif "BROTHER_STATUS_SAMPLE" in message and "phase=0x01" in message:
            event = "BROTHER_ACTIVE"
        elif "Observed spooler job(s) cleared successfully" in message:
            event = "SPOOLER_CLEARED"
        elif "BROTHER_STATUS_PHYSICAL_TERMINAL outcome=READY_IDLE" in message:
            event = "READY_IDLE"
        elif message.startswith("ACTIVE_PRINT_MEDIA_WAIT"):
            event = "RECOVERABLE_MEDIA"
            once = False
        elif "BROTHER_STATUS_PHYSICAL_TERMINAL outcome=ERROR" in message:
            event = "AMBIGUOUS_ERROR"

        if event is None:
            return
        try:
            self.checkpoint(
                workload,
                batch_id,
                event,
                {"evidence": message[:2000]},
                once=once,
            )
            if event == "RECOVERABLE_MEDIA":
                reason_match = re.search(r" reason='(?P<reason>.*)'$", message)
                requester_action = (
                    reason_match.group("reason")
                    if reason_match
                    else (
                        "Install the tape required for this label job and "
                        "close the cover."
                    )
                )
                with self.connect_database() as conn:
                    self.incident_upsert(
                        conn,
                        incident_key=(
                            f"active-media:{workload.lower()}:{batch_id}"
                        ),
                        incident_kind="ACTIVE_MEDIA",
                        workload_type=workload,
                        printer_name=self.printer_name,
                        batch_id=batch_id,
                        pending_count=0,
                        severity="ERROR",
                        alert_delay_seconds=0,
                        operator_action=requester_action,
                        recovery_state="WAITING_MEDIA",
                        details={"evidence": message[:2000]},
                    )
                    conn.commit()
            elif event == "READY_IDLE":
                with self.connect_database() as conn:
                    self.incident_resolve(
                        conn,
                        f"active-media:{workload.lower()}:{batch_id}",
                        "AUTOMATIC_MEDIA_RECOVERY",
                        {"evidence": message[:2000]},
                    )
                    conn.commit()
        except Exception:
            logging.exception(
                "LABEL_PRINT_EVIDENCE_WRITE_FAILED workload=%s batch_id=%s "
                "event=%s",
                workload,
                batch_id,
                event,
            )

    def record_explicit_batch_event(
        self,
        batch_log_path: Path,
        event_name: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Record evidence that must precede the physical action itself."""
        if not self.enabled:
            return
        match = self._BATCH_PATH.search(batch_log_path.name)
        if not match:
            raise RuntimeError(
                f"Could not resolve batch identity from {batch_log_path.name}"
            )
        self.checkpoint(
            match.group("workload").upper(),
            int(match.group("batch_id")),
            event_name,
            details,
            once=True,
        )
