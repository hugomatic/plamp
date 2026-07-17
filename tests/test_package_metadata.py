import tomllib
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class PackageMetadataTests(unittest.TestCase):
    def test_project_declares_build_backend_for_cli_entry_point(self):
        with (REPO_ROOT / "pyproject.toml").open("rb") as source:
            config = tomllib.load(source)

        self.assertEqual(
            config["build-system"]["build-backend"],
            "setuptools.build_meta",
        )
        self.assertIn("setuptools>=80", config["build-system"]["requires"])
        self.assertIn(
            "setuptools-scm[simple]>=8",
            config["build-system"]["requires"],
        )
        self.assertNotIn("version", config["project"])
        self.assertIn("version", config["project"]["dynamic"])
        self.assertEqual(
            config["project"]["scripts"]["plamp"],
            "plamp_cli.main:run",
        )


if __name__ == "__main__":
    unittest.main()
