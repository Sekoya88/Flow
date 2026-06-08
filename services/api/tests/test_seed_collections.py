from flow.infrastructure.persistence.seed_collections import _category_for


def test_category_mapping():
    assert _category_for("ecc") == "Code"
    assert _category_for("scientific-agent-skills") == "Research"
    assert _category_for("academic-research-skills") == "Research"
    assert _category_for("mattpocock-skills") == "Code"
    assert _category_for("unknown") == "General"
