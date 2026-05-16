import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run(cmd, cwd, **kwargs):
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **kwargs,
    )


def init_git_repo(path: Path):
    run(["git", "init"], path, check=True)
    run(["git", "config", "user.email", "test@example.invalid"], path, check=True)
    run(["git", "config", "user.name", "Test User"], path, check=True)


def make_fake_openscad(path: Path):
    path.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
out=""
view=""
input="${@: -1}"
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    -o) shift; out="$1" ;;
    view=*) view="${1#view=}" ;;
  esac
  shift || true
done
printf 'view=%s input=%s\\n' "$view" "$input" >> "$OPENSCAD_LOG"
printf 'solid %s\\nendsolid %s\\n' "$view" "$view" > "$out"
""",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class ThingsCadScriptsTest(unittest.TestCase):
    def test_template_bash_can_select_scad_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            things = tmp_path / "things"
            shutil.copytree(REPO_ROOT / "things" / "3d_template", things / "3d_template")
            shutil.copy2(REPO_ROOT / "things" / "template.bash", things / "template.bash")
            templates = things / "3d_template" / "scad"
            templates.mkdir(exist_ok=True)
            (templates / "cover.scad").write_text('view = "plate"; // [plate]\n// cover template\n')

            result = run(["bash", "template.bash", "new_cover", "--template", "cover"], things)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((things / "new_cover" / "generate.bash").exists())
            self.assertEqual(
                (things / "new_cover" / "new_cover.scad").read_text(),
                'view = "plate"; // [plate]\n// cover template\n',
            )
            self.assertIn('cad="new_cover"', (things / "new_cover" / "generate.bash").read_text())

    def test_template_bash_lists_available_templates_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            things = tmp_path / "things"
            shutil.copytree(REPO_ROOT / "things" / "3d_template", things / "3d_template")
            shutil.copy2(REPO_ROOT / "things" / "template.bash", things / "template.bash")
            templates = things / "3d_template" / "scad"
            templates.mkdir(exist_ok=True)
            (templates / "basic.scad").write_text("// basic\n")

            result = run(["bash", "template.bash", "new_part", "--template", "missing"], things)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Available templates:", result.stderr)
            self.assertIn("basic", result.stderr)

    def test_generate_bash_defaults_to_head_and_uses_ordered_scad_views(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = tmp_path / "repo"
            part = repo / "things" / "multi_part"
            part.mkdir(parents=True)
            init_git_repo(repo)
            generate = (REPO_ROOT / "things" / "3d_template" / "generate.bash").read_text()
            (part / "generate.bash").write_text(generate.replace("__cad__name__", "multi_part"))
            (part / "generate.bash").chmod(0o755)
            (part / "lib.scad").write_text("module helper() { cube([1, 1, 1]); }\n")
            (part / "multi_part.scad").write_text(
                'include <lib.scad>\nview = "assembly"; // [assembly, camera_clip, plate]\n'
                'revision_string = "dev";\nhelper();\n'
            )
            run(["git", "add", "."], repo, check=True)
            run(["git", "commit", "-m", "add cad part"], repo, check=True)
            fake_openscad = tmp_path / "openscad"
            make_fake_openscad(fake_openscad)
            log = tmp_path / "openscad.log"
            target = tmp_path / "rendered"

            env = {**os.environ, "OPENSCAD_BIN": str(fake_openscad), "OPENSCAD_LOG": str(log)}
            result = run(["./generate.bash", str(target), "HEAD"], part, env=env)

            self.assertEqual(result.returncode, 0, result.stderr)
            short_head = run(["git", "rev-parse", "--short", "HEAD"], repo, check=True).stdout.strip()
            self.assertEqual(
                [p.name for p in sorted(target.glob("*.stl"))],
                [
                    f"multi_part_assembly_{short_head}.stl",
                    f"multi_part_camera_clip_{short_head}.stl",
                    f"multi_part_plate_{short_head}.stl",
                ],
            )
            rendered_views = [
                line.split()[0].removeprefix("view=").strip('"')
                for line in log.read_text().splitlines()
            ]
            self.assertEqual(rendered_views, ["assembly", "camera_clip", "plate"])

    def test_generate_bash_preview_uses_render_fn_without_ball_quality(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = tmp_path / "repo"
            part = repo / "things" / "preview_part"
            part.mkdir(parents=True)
            init_git_repo(repo)
            generate = (REPO_ROOT / "things" / "3d_template" / "generate.bash").read_text()
            (part / "generate.bash").write_text(generate.replace("__cad__name__", "preview_part"))
            (part / "generate.bash").chmod(0o755)
            (part / "preview_part.scad").write_text('view = "plate"; // [plate]\ncube([1,1,1]);\n')
            run(["git", "add", "."], repo, check=True)
            run(["git", "commit", "-m", "add cad part"], repo, check=True)
            fake_openscad = tmp_path / "openscad"
            make_fake_openscad(fake_openscad)
            log = tmp_path / "openscad.log"
            target = tmp_path / "rendered"

            env = {**os.environ, "OPENSCAD_BIN": str(fake_openscad), "OPENSCAD_LOG": str(log)}
            result = run(["./generate.bash", "--preview", str(target), "HEAD"], part, env=env)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("render_fn=24", result.stdout)
            self.assertNotIn("ball_quality=", result.stdout)

    def test_generate_bash_refuses_dirty_part_without_revision_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = tmp_path / "repo"
            part = repo / "things" / "dirty_part"
            other = repo / "app"
            part.mkdir(parents=True)
            other.mkdir()
            init_git_repo(repo)
            generate = (REPO_ROOT / "things" / "3d_template" / "generate.bash").read_text()
            (part / "generate.bash").write_text(generate.replace("__cad__name__", "dirty_part"))
            (part / "generate.bash").chmod(0o755)
            (part / "dirty_part.scad").write_text('view = "plate"; // [plate]\ncube([1,1,1]);\n')
            (other / "unrelated.py").write_text("print('clean enough')\n")
            run(["git", "add", "."], repo, check=True)
            run(["git", "commit", "-m", "add files"], repo, check=True)
            (other / "unrelated.py").write_text("print('ignored dirty')\n")
            result_with_unrelated_dirty = run(["./generate.bash", str(tmp_path / "ok"), "HEAD"], part)
            (part / "dirty_part.scad").write_text('view = "plate"; // [plate]\nsphere(1);\n')

            result = run(["./generate.bash", str(tmp_path / "blocked"), "HEAD"], part)

            self.assertNotIn("part directory has uncommitted changes", result_with_unrelated_dirty.stderr)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("part directory has uncommitted changes", result.stderr)
            self.assertIn("git status --porcelain -- things/dirty_part", result.stderr)


if __name__ == "__main__":
    unittest.main()
