import tempfile
import unittest
from pathlib import Path

from plamp.context import RuntimeContext, resolve_context


class RuntimeContextTests(unittest.TestCase):
    def test_package_root_supplies_default_data_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            context = resolve_context(env={}, package_root=root)

            self.assertEqual(context, RuntimeContext(root=root.resolve(), data_dir=(root / "data").resolve()))
            self.assertEqual(context.config_file, (root / "data" / "config.json").resolve())

    def test_environment_selects_and_resolves_root_and_data(self):
        context = resolve_context(
            env={"PLAMP_ROOT": ".", "PLAMP_DATA_DIR": "instance-data"},
            package_root=Path("ignored"),
        )

        self.assertEqual(context.root, Path.cwd().resolve())
        self.assertEqual(context.data_dir, (Path.cwd() / "instance-data").resolve())

    def test_explicit_root_still_defaults_data_below_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "checkout"

            context = resolve_context(env={"PLAMP_ROOT": str(root)}, package_root=Path("ignored"))

            self.assertEqual(context.data_dir, (root / "data").resolve())


if __name__ == "__main__":
    unittest.main()
