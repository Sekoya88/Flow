"""Verify worker.py references langsmith for training tracing."""


def test_worker_references_langsmith():
    """task_run_skill_training should import/use langsmith for tracing."""
    import inspect

    from flow.infrastructure.queue import worker

    src = inspect.getsource(worker)
    assert "langsmith" in src, "worker.py should import/use langsmith for training run tracing"
    assert "langsmith.Client" in src or "from langsmith import Client" in src, "worker.py should use langsmith.Client for training run tracing"
    assert "_start_ls_run" in src, "worker.py should define _start_ls_run helper for LangSmith tracing"
    assert "_end_ls_run" in src, "worker.py should define _end_ls_run helper for LangSmith tracing"
