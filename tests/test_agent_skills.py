import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RETIRED_SHELL_NAMES = tuple(
    stem + "." + suffix for stem in ("generate", "template") for suffix in ("bash",)
)


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
        for retired_name in RETIRED_SHELL_NAMES:
            self.assertNotIn(retired_name, smoke)

    def test_stand_smoke_accepts_fingerprinted_artifacts_from_generated_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            smoke_dir = root / "things" / "plamp_stand"
            smoke_dir.mkdir(parents=True)
            smoke = smoke_dir / "check_generates_stl_files_from_scad.bash"
            smoke.write_text(
                self.read("things/plamp_stand/check_generates_stl_files_from_scad.bash"),
                encoding="utf-8",
            )
            smoke.chmod(0o755)
            fake_bin = root / "fake-bin"
            fake_bin.mkdir()
            fake_git = fake_bin / "git"
            fake_git.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ \"$*\" == *rev-parse* ]]; then\n"
                "  printf '%s\\n' \"$FAKE_REPO_ROOT\"\n"
                "elif [[ \"$*\" == *log* ]]; then\n"
                "  printf '%s\\n' abc1234\n"
                "else\n"
                "  exit 2\n"
                "fi\n",
                encoding="utf-8",
            )
            fake_git.chmod(0o755)
            fake_openscad = fake_bin / "openscad"
            fake_openscad.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            fake_openscad.chmod(0o755)
            plamp = root / "bin" / "plamp"
            plamp.parent.mkdir()
            plamp.write_text(
                """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

output = Path(sys.argv[sys.argv.index("--output") + 1])
revision = sys.argv[sys.argv.index("--revision") + 1]
output.mkdir(parents=True)
(output / "artifacts").mkdir()
jobs = []
views = (
    ("assembly", "0123456789ab"),
    ("tripod", "abcdef012345"),
    ("plate", "fedcba987654"),
    ("camera_clip", "567890abcdef"),
)
for view, fingerprint in views:
    if view == os.environ.get("FAKE_DROP_VIEW"):
        continue
    artifact_id = f"plamp_stand_{view}--{fingerprint}"
    artifact = f"artifacts/{artifact_id}--{revision}.stl"
    (output / artifact).write_text("solid fixture\\n")
    jobs.append({"artifact_id": artifact_id, "view": view, "status": "complete", "artifact": artifact})
(output / "readme.md").write_text("# fake run\\n")
manifest = {"status": "complete", "jobs": jobs}
(output / "manifest.json").write_text(json.dumps(manifest))
print(json.dumps(manifest))
""",
                encoding="utf-8",
            )
            plamp.chmod(0o755)
            env = dict(os.environ)
            env["FAKE_REPO_ROOT"] = str(root)
            env["PATH"] = f"{fake_bin}:{env['PATH']}"

            result = subprocess.run(
                ["bash", str(smoke)],
                cwd=root,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PASS:", result.stdout)

            env["FAKE_DROP_VIEW"] = "plate"
            incomplete = subprocess.run(
                ["bash", str(smoke)],
                cwd=root,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertNotEqual(incomplete.returncode, 0, incomplete.stdout + incomplete.stderr)
            self.assertIn("plate", incomplete.stdout + incomplete.stderr)

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
                for retired_name in RETIRED_SHELL_NAMES:
                    self.assertNotIn(retired_name, self.read(relative_path))

    def test_all_tracked_text_has_no_retired_shell_filename_references(self):
        for retired_name in RETIRED_SHELL_NAMES:
            with self.subTest(retired_name=retired_name):
                references = subprocess.run(
                    ["git", "grep", "-n", "-I", "-F", "-e", retired_name, "--"],
                    cwd=REPO_ROOT,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                self.assertEqual(
                    references.returncode,
                    1,
                    references.stdout + references.stderr,
                )

    def test_cad_docs_describe_current_archive_and_direct_interface(self):
        reference = self.read("agent/skills/openscad-cad/references/plamp-things.md")
        readme = self.read("README.md")
        skill = self.read("agent/skills/openscad-cad/SKILL.md")

        self.assertIn("artifacts/<ARTIFACT_ID>--<REVISION>.stl", reference)
        self.assertNotIn("legacy script options", readme)
        self.assertNotIn("wrappers", skill.lower())


if __name__ == "__main__":
    unittest.main()
