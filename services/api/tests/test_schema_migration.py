"""Verify migration module contains new digest_runs schema statements."""


def test_migration_contains_digest_runs():
    import inspect

    from flow.infrastructure.db import migrations

    src = inspect.getsource(migrations)
    assert "digest_runs" in src, "digest_runs table missing from migrations"


def test_migration_contains_digest_run_id():
    import inspect

    from flow.infrastructure.db import migrations

    src = inspect.getsource(migrations)
    assert "digest_run_id" in src, "digest_run_id column missing from migrations"


def test_migration_contains_obsidian_vault_path():
    import inspect

    from flow.infrastructure.db import migrations

    src = inspect.getsource(migrations)
    assert "obsidian_vault_path" in src, "obsidian_vault_path column missing from migrations"
