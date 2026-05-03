"""Guardrail: ARQ worker registration and enqueue must use the same job name."""

import inspect

from flow.infrastructure.queue import worker as queue_worker
from flow.infrastructure.queue.client import enqueue_execution
from flow.infrastructure.queue.jobs import DEER_EXECUTION_JOB
from flow.interfaces.http.routes.executions import approve_execution


def test_deer_execution_job_name_matches_worker_and_client() -> None:
    registered = queue_worker.WorkerSettings.functions[0].name
    assert registered == DEER_EXECUTION_JOB
    # Source uses the shared constant (not a divergent string literal).
    assert "DEER_EXECUTION_JOB" in inspect.getsource(enqueue_execution)
    assert "DEER_EXECUTION_JOB" in inspect.getsource(approve_execution)
