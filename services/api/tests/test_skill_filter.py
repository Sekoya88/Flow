from flow.infrastructure.persistence.skill_collections import is_skill_file


def test_import_keeps_only_skill_files():
    # Simulates the per-file decision import_skills_from_repo now makes.
    files = {
        "skills/tdd/SKILL.md": "---\nname: tdd\ndescription: when to test\n---\nbody",
        "README.md": "# Repo readme",
        "skills/tdd/references/mocking.md": "---\nname: mocking\n---\nref",
        "docs/ARCHITECTURE.md": "# arch",
        "academic-paper/SKILL.md": "---\nname: academic-paper\ndescription: write papers\n---\nx",
    }
    kept = [p for p, c in files.items() if is_skill_file(p, c)]
    assert kept == ["skills/tdd/SKILL.md", "academic-paper/SKILL.md"]


def test_preview_path_only_filter_keeps_skill_md():
    # preview has no content; path-only filter keeps SKILL.md, drops the rest.
    paths = ["skills/x/SKILL.md", "README.md", "skills/x/references/a.md", "b/SKILL.md"]
    kept = [p for p in paths if p.lower().endswith("/skill.md") or p.lower() == "skill.md"]
    assert kept == ["skills/x/SKILL.md", "b/SKILL.md"]
