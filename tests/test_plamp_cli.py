import unittest

from plamp_cli.main import build_parser, main


class PlampCliBootstrapTests(unittest.TestCase):
    def test_build_parser_accepts_config_get_shape(self):
        parser = build_parser()
        args = parser.parse_args(["config", "get"])

        self.assertEqual(args.area, "config")
        self.assertEqual(args.action, "get")

    def test_main_returns_zero_for_help(self):
        code = main(["--help"])
        self.assertEqual(code, 0)
