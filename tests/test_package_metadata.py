import tomllib
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class PackageMetadataTests(unittest.TestCase):
    def test_uv_project_manages_dependencies_without_packaging_plamp(self):
        with (REPO_ROOT / "pyproject.toml").open("rb") as source:
            config = tomllib.load(source)

        self.assertNotIn("build-system", config)
        self.assertNotIn("scripts", config["project"])
        self.assertNotIn("setuptools", config.get("tool", {}))
        self.assertIs(config["tool"]["uv"]["package"], False)
        self.assertIn("version", config["project"]["dynamic"])
        self.assertEqual(
            config["project"]["dependencies"],
            ["fastapi", "pyserial", "pyudev", "uvicorn[standard]"],
        )

    def test_readme_exposes_rest_cli_without_uv_setup(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        operation = readme.split("## Operate Plamp", 1)[1].split("## Web and API", 1)[0]

        self.assertIn("source ./setup.sh\nplamp --help", operation)
        self.assertNotIn("uv sync", operation)


if __name__ == "__main__":
    unittest.main()
