import os
import unittest
from unittest.mock import patch

from plamp_cli.http import ApiError, build_base_url


class PlampCliHttpTests(unittest.TestCase):
    def test_build_base_url_defaults_to_local_service(self):
        self.assertEqual(build_base_url(None, None, None), "http://127.0.0.1:8000")

    def test_build_base_url_uses_explicit_base_url(self):
        self.assertEqual(build_base_url(None, None, "http://pi.local:9000"), "http://pi.local:9000")

    def test_build_base_url_uses_host_and_port(self):
        self.assertEqual(build_base_url("pi.local", 8123, None), "http://pi.local:8123")

    def test_build_base_url_reads_environment_when_flags_missing(self):
        with patch.dict(os.environ, {"PLAMP_HOST": "growbox.local", "PLAMP_PORT": "8100"}, clear=False):
            self.assertEqual(build_base_url(None, None, None), "http://growbox.local:8100")

    def test_api_error_carries_status_and_detail(self):
        error = ApiError(422, "bad payload")
        self.assertEqual(str(error), "API 422: bad payload")
