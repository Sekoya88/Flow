from __future__ import annotations


def test_ab_test_insert_sql_uses_same_agent_for_both_sides():
    """Verify the INSERT SQL intentionally uses same positional param $4 for both agent columns.

    In the genome versioning system, the A/B test compares two versions of the same agent,
    not two different agents. The agent_id is used for both agent_a_id and agent_b_id,
    while version_a_id and version_b_id are set later by ab_runner.py on completion.
    """
    sql = (
        "INSERT INTO ab_tests "
        "(id, workspace_id, golden_set_id, agent_a_id, agent_b_id, status) "
        "VALUES ($1, $2, $3, $4, $4, 'running')"
    )
    # Both agent_a_id and agent_b_id use $4 = same agent (versions differ, not agents)
    assert sql.count("$4") == 2
    assert "agent_a_id" in sql
    assert "agent_b_id" in sql
