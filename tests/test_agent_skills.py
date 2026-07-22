import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RETIRED_GENERATOR = "generate" + ".bash"


class AgentSkillsTests(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (REPO_ROOT / relative_path).read_text(encoding="utf-8")

    def assert_skill_frontmatter(self, relative_path: str, expected_name: str) -> str:
        source = self.read(relative_path)
        match = re.match(r"\A---\n(?P<header>.*?)\n---\n", source, re.DOTALL)
        self.assertIsNotNone(match, relative_path)
        fields = {}
        for line in match.group("header").splitlines():
            key, separator, value = line.partition(":")
            self.assertTrue(separator, f"invalid frontmatter line in {relative_path}: {line}")
            fields[key.strip()] = value.strip()
        self.assertEqual(fields.get("name"), expected_name)
        self.assertTrue(fields.get("description"))
        self.assertEqual(set(fields), {"name", "description"})
        return source

    def test_repository_publishes_canonical_skills_with_valid_frontmatter(self):
        workflow = self.assert_skill_frontmatter(
            "agent/skills/plamp-workflow/SKILL.md", "plamp-workflow"
        )
        cad = self.assert_skill_frontmatter(
            "agent/skills/openscad-cad/SKILL.md", "openscad-cad"
        )

        self.assertIn("plampctl", workflow)
        self.assertIn("plamp CLI", workflow)
        self.assertIn("plamp cad", workflow)
        self.assertIn("plamp cad new", cad)
        self.assertIn("plamp cad generate", cad)

    def test_agent_readme_is_one_url_entrypoint_for_both_skills(self):
        readme = self.read("agent/README.md")

        self.assertIn("skills/plamp-workflow/SKILL.md", readme)
        self.assertIn("skills/openscad-cad/SKILL.md", readme)
        self.assertRegex(readme, r"(?i)start.*plamp-workflow")

    def test_live_docs_use_direct_new_and_generate_commands(self):
        documentation = "\n".join(
            self.read(path)
            for path in (
                "agent/skills/openscad-cad/SKILL.md",
                "agent/skills/openscad-cad/references/plamp-things.md",
                "things/README.md",
                "things/plamp_stand/README.md",
            )
        )

        self.assertIn("plamp cad new PART", documentation)
        self.assertIn("plamp cad generate plamp_stand", documentation)

    def test_stand_smoke_uses_checkout_cad_command(self):
        smoke = self.read("things/plamp_stand/check_generates_stl_files_from_scad.bash")

        self.assertIn(
            '"$REPO_ROOT/bin/plamp" cad generate plamp_stand '
            '--preset all-views-default --revision "$commit" --output "$outdir/out"',
            smoke,
        )
        self.assertNotIn(RETIRED_GENERATOR, smoke)

    def test_live_agent_and_cad_files_have_no_retired_generator_references(self):
        live_paths = (
            "CHECKLIST.md",
            "docs/host-tools.md",
            "things/README.md",
            "things/plamp_stand/README.md",
            "things/plamp_stand/check_generates_stl_files_from_scad.bash",
            "agent/README.md",
            "agent/skills/plamp-workflow/SKILL.md",
            "agent/skills/openscad-cad/SKILL.md",
            "agent/skills/openscad-cad/references/plamp-things.md",
        )

        for relative_path in live_paths:
            with self.subTest(path=relative_path):
                self.assertNotIn(RETIRED_GENERATOR, self.read(relative_path))


if __name__ == "__main__":
    unittest.main()
