import os
import unittest
from unittest.mock import patch

from app import response_for_path


class ResponseForPathTests(unittest.TestCase):
    def test_root_returns_app_metadata(self):
        with patch.dict(os.environ, {"APP_ENV": "test", "APP_VERSION": "abc123"}):
            status, body = response_for_path("/")

        self.assertEqual(status, 200)
        self.assertEqual(
            body,
            {
                "app": "gitops-sample-app",
                "environment": "test",
                "version": "abc123",
            },
        )

    def test_health_endpoints_are_healthy(self):
        for path in ("/healthz", "/readyz"):
            with self.subTest(path=path):
                self.assertEqual(response_for_path(path), (200, {"status": "ok"}))

    def test_unknown_path_is_not_found(self):
        self.assertEqual(response_for_path("/missing"), (404, {"error": "not found"}))


if __name__ == "__main__":
    unittest.main()
