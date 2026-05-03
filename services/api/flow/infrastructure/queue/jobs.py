"""ARQ job names used by the worker and enqueue callers — keep in sync."""

# Must match arq.func(..., name=...) in worker.WorkerSettings.
DEER_EXECUTION_JOB = "run_deer_execution"
