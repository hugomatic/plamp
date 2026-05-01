import os
import io
import json
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request
from unittest.mock import patch

from plamp_cli.http import ApiError, NetworkError, build_base_url, request_json


class PlampCliHttpTests(unittest.TestCase):
    def test_build_base_url_defaults_to_local_service(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(build_base_url(None, None, None), "http://127.0.0.1:8000")

    def test_build_base_url_uses_explicit_base_url(self):
        with patch.dict(
            os.environ,
            {"PLAMP_BASE_URL": "http://env.example:9000", "PLAMP_HOST": "env-host", "PLAMP_PORT": "9999"},
            clear=True,
        ):
            self.assertEqual(build_base_url(None, None, "http://pi.local:9000"), "http://pi.local:9000")

    def test_build_base_url_uses_environment_base_url_when_flags_missing(self):
        with patch.dict(
            os.environ,
            {
                "PLAMP_BASE_URL": "http://env.example:9000",
                "PLAMP_HOST": "env-host",
                "PLAMP_PORT": "9999",
            },
            clear=True,
        ):
            self.assertEqual(build_base_url(None, None, None), "http://env.example:9000")

    def test_build_base_url_uses_host_and_port(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(build_base_url("pi.local", 8123, None), "http://pi.local:8123")

    def test_build_base_url_reads_environment_when_flags_missing(self):
        with patch.dict(os.environ, {"PLAMP_HOST": "growbox.local", "PLAMP_PORT": "8100"}, clear=True):
            self.assertEqual(build_base_url(None, None, None), "http://growbox.local:8100")

    def test_api_error_carries_status_and_detail(self):
        error = ApiError(422, "bad payload")
        self.assertEqual(str(error), "API 422: bad payload")

    @patch("plamp_cli.http.urlopen")
    def test_request_json_returns_json_response_and_uses_timeout(self, urlopen):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({"ok": True}).encode("utf-8")
        urlopen.return_value = response

        result = request_json("GET", "http://127.0.0.1:8000", "/api/config")

        self.assertEqual(result, {"ok": True})
        urlopen.assert_called_once()
        _, kwargs = urlopen.call_args
        self.assertEqual(kwargs["timeout"], 10)

        request = urlopen.call_args.args[0]
        self.assertIsInstance(request, Request)
        self.assertEqual(request.full_url, "http://127.0.0.1:8000/api/config")

    @patch("plamp_cli.http.urlopen")
    def test_request_json_raises_api_error_with_clean_detail(self, urlopen):
        urlopen.side_effect = HTTPError(
            "http://127.0.0.1:8000/api/config",
            422,
            "Unprocessable Entity",
            hdrs=None,
            fp=io.BytesIO(json.dumps({"detail": "bad payload"}).encode("utf-8")),
        )

        with self.assertRaises(ApiError) as ctx:
            request_json("GET", "http://127.0.0.1:8000", "/api/config")

        self.assertEqual(ctx.exception.status, 422)
        self.assertEqual(ctx.exception.detail, "bad payload")
        self.assertEqual(str(ctx.exception), "API 422: bad payload")

    @patch("plamp_cli.http.urlopen")
    def test_request_json_raises_api_error_with_validation_error_list_detail(self, urlopen):
        urlopen.side_effect = HTTPError(
            "http://127.0.0.1:8000/api/config",
            422,
            "Unprocessable Entity",
            hdrs=None,
            fp=io.BytesIO(json.dumps({"detail": [{"msg": "Field required"}]}).encode("utf-8")),
        )

        with self.assertRaises(ApiError) as ctx:
            request_json("GET", "http://127.0.0.1:8000", "/api/config")

        self.assertEqual(ctx.exception.status, 422)
        self.assertEqual(ctx.exception.detail, "Field required")
        self.assertEqual(str(ctx.exception), "API 422: Field required")

    @patch("plamp_cli.http.urlopen")
    def test_request_json_wraps_network_error(self, urlopen):
        urlopen.side_effect = URLError(TimeoutError("timed out"))

        with self.assertRaises(NetworkError) as ctx:
            request_json("GET", "http://127.0.0.1:8000", "/api/config")

        self.assertIn("timed out", str(ctx.exception))
