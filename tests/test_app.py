import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import main


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def test_status_endpoint_reports_expected_fields(self):
        response = self.client.get("/status")
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertIn("cam_dir", payload)
        self.assertIn("cam_dir_exists", payload)
        self.assertIn("video_count", payload)
        self.assertIn("gemini_configured", payload)
        self.assertIn("cache_ttl_seconds", payload)
        self.assertIn("cached_response_count", payload)
        self.assertTrue(payload["cam_dir_exists"])
        self.assertGreater(payload["video_count"], 0)

    def test_videos_endpoint_returns_expected_metadata(self):
        response = self.client.get("/videos")
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertGreater(len(payload), 0)

        first = payload[0]
        expected_keys = {
            "id",
            "study_name",
            "label",
            "has_importance_plot",
            "frame_count",
            "frames",
            "label_file",
            "video",
            "playback_video",
            "playback_video_type",
            "playback_url",
        }
        self.assertTrue(expected_keys.issubset(first.keys()))
        self.assertEqual(first["frame_count"], len(first["frames"]))

    def test_video_detail_endpoint_returns_study_data(self):
        first_id = self.client.get("/videos").json()[0]["id"]

        response = self.client.get(f"/videos/{first_id}")
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload["id"], first_id)
        self.assertTrue(payload["study_name"].startswith("Sample_"))
        self.assertEqual(payload["label_file"], "predicted_label.txt")
        self.assertIsNotNone(payload["video"])
        self.assertIsNotNone(payload["playback_video"])
        self.assertIsNotNone(payload["playback_url"])

    def test_invalid_video_returns_404(self):
        response = self.client.get("/videos/999999")
        self.assertEqual(response.status_code, 404)

    def test_empty_question_is_rejected(self):
        first_id = self.client.get("/videos").json()[0]["id"]

        response = self.client.post(f"/videos/{first_id}/ask", json={"question": "   "})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Question cannot be empty")

    def test_question_too_long_is_rejected(self):
        first_id = self.client.get("/videos").json()[0]["id"]

        response = self.client.post(
            f"/videos/{first_id}/ask",
            json={"question": "x" * 501},
        )
        self.assertEqual(response.status_code, 422)

    def test_frontend_root_serves_expected_ui_text(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

        html = response.text
        self.assertIn("Action Recognition XAI", html)
        self.assertIn("Evidence Workspace", html)
        self.assertIn("Ask a grounded question", html)

    @patch("main.time.sleep")
    @patch("main.get_gemini_client")
    def test_run_gemini_retries_transient_api_errors(self, get_client_mock, sleep_mock):
        class FakeResponse:
            text = "Recovered response"

        class FakeModels:
            def __init__(self):
                self.calls = 0

            def generate_content(self, model, contents):
                self.calls += 1
                if self.calls < 3:
                    raise main.errors.ServerError(
                        503,
                        {"error": {"code": 503, "message": "busy", "status": "UNAVAILABLE"}},
                    )
                return FakeResponse()

        class FakeClient:
            def __init__(self):
                self.models = FakeModels()

        get_client_mock.return_value = FakeClient()

        text, cached = main.run_gemini(["prompt"])

        self.assertEqual(text, "Recovered response")
        self.assertFalse(cached)
        self.assertEqual(get_client_mock.return_value.models.calls, 3)
        self.assertEqual(sleep_mock.call_count, 2)

    @patch("main.time.sleep")
    @patch("main.get_gemini_client")
    def test_run_gemini_returns_503_after_retry_exhaustion(self, get_client_mock, sleep_mock):
        class FakeModels:
            def __init__(self):
                self.calls = 0

            def generate_content(self, model, contents):
                self.calls += 1
                raise main.errors.ServerError(
                    503,
                    {"error": {"code": 503, "message": "busy", "status": "UNAVAILABLE"}},
                )

        class FakeClient:
            def __init__(self):
                self.models = FakeModels()

        get_client_mock.return_value = FakeClient()

        with self.assertRaises(main.HTTPException) as context:
            main.run_gemini(["prompt"])

        self.assertEqual(context.exception.status_code, 503)
        self.assertIn("Gemini analysis failed", context.exception.detail)
        self.assertEqual(get_client_mock.return_value.models.calls, main.GEMINI_MAX_RETRIES)
        self.assertEqual(sleep_mock.call_count, main.GEMINI_MAX_RETRIES - 1)


if __name__ == "__main__":
    unittest.main()
