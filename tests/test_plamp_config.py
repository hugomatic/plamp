import json
import tempfile
import unittest
from pathlib import Path

from plamp.config import ConfigError, load_config, save_config


class ConfigFileTests(unittest.TestCase):
    def valid_config(self):
        return {
            "controllers": {
                "grow": {
                    "type": "pico_scheduler",
                    "payload": {"pico_serial": "PICO-A"},
                }
            },
            "cameras": {},
        }

    def test_load_returns_validated_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps(self.valid_config()), encoding="utf-8")

            loaded = load_config(path)

            self.assertEqual(loaded["controllers"]["grow"]["payload"]["pico_serial"], "PICO-A")
            self.assertEqual(loaded["cameras"], {})

    def test_load_rejects_malformed_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text("{broken", encoding="utf-8")

            with self.assertRaisesRegex(ConfigError, "cannot read configuration"):
                load_config(path)

    def test_save_rejects_invalid_schema_without_changing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            original = json.dumps(self.valid_config()) + "\n"
            path.write_text(original, encoding="utf-8")

            with self.assertRaisesRegex(ConfigError, "controllers must be a mapping"):
                save_config(path, {"controllers": [], "cameras": {}})

            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_save_atomically_replaces_with_canonical_json_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "nested" / "config.json"

            saved = save_config(path, self.valid_config())

            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), saved)
            self.assertTrue(path.read_text(encoding="utf-8").endswith("\n"))
            self.assertEqual(list(path.parent.glob(".config.json.*")), [])


if __name__ == "__main__":
    unittest.main()
