from flow.infrastructure.persistence.golden_seed import CURATED_GOLDEN_SETS


def test_curated_sets_cover_four_domains():
    names = {s["name"] for s in CURATED_GOLDEN_SETS}
    assert len(CURATED_GOLDEN_SETS) == 4
    assert len(names) == 4, "golden set names must be unique"
    for s in CURATED_GOLDEN_SETS:
        assert s["items"], f"{s['name']} has no items"
        for it in s["items"]:
            assert it["input_text"] and it["expected_output"] and it["scoring_criteria"]
