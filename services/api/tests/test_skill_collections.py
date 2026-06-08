from flow.infrastructure.persistence.skill_collections import (
    CURATED_COLLECTIONS,
    get_collection,
    is_skill_file,
    raw_url,
)


def test_collections_have_required_fields():
    assert len(CURATED_COLLECTIONS) == 4
    ids = {c["id"] for c in CURATED_COLLECTIONS}
    assert ids == {"mattpocock-skills", "scientific-agent-skills", "academic-research-skills", "ecc"}
    for c in CURATED_COLLECTIONS:
        assert c["name"] and c["repo"] and c["category"]
        assert c["skills"], f"{c['id']} has no pinned skills"
        for s in c["skills"]:
            assert s["path"].endswith("SKILL.md")
            assert s["name"]


def test_get_collection_found_and_missing():
    assert get_collection("ecc")["repo"] == "affaan-m/ECC"
    assert get_collection("nope") is None


def test_raw_url_builds_github_raw_path():
    assert raw_url("owner/repo", ".agents/skills/x/SKILL.md") == ("https://raw.githubusercontent.com/owner/repo/HEAD/.agents/skills/x/SKILL.md")


def test_is_skill_file_accepts_skill_md_by_name():
    assert is_skill_file("skills/tdd/SKILL.md", "no frontmatter here")


def test_is_skill_file_accepts_frontmatter_with_name_and_description():
    md = "---\nname: x\ndescription: when to use\n---\n\nbody"
    assert is_skill_file("foo/x.md", md)


def test_is_skill_file_rejects_readme_and_references():
    assert not is_skill_file("README.md", "# Readme")
    assert not is_skill_file("skills/tdd/references/mocking.md", "---\nname: m\n---\nx")
    assert not is_skill_file("docs/ARCHITECTURE.md", "# Arch\nno frontmatter")
