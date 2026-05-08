import unittest
from unittest.mock import Mock, patch

import requests

import Backend


class TranslateRouteTests(unittest.TestCase):
    def setUp(self):
        Backend.app.config["TESTING"] = True
        self.client = Backend.app.test_client()

    def test_rejects_empty_input(self):
        response = self.client.post("/translate", json={"text": "   "})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Please type something first.")

    def test_build_prompt_keeps_large_vocab_compact(self):
        huge_context = {
            "tone_notes": [
                "Keep it playful.",
                "Use light Spanglish.",
            ],
            "glossary": {
                "friend": "pana",
            },
            "examples": [
                f"Example line number {index} with a lot of filler text for testing."
                for index in range(500)
            ],
        }

        prompt = Backend.build_prompt("Hello friend", huge_context)

        self.assertLess(len(prompt), 1800)
        self.assertIn("friend -> pana", prompt)
        self.assertNotIn("Example line number 499", prompt)

    def test_build_prompt_uses_vocab_as_style_and_relevant_hints(self):
        slang_context = {
            "tone_notes": [
                "Keep it playful.",
                "Keep the original meaning intact.",
            ],
            "glossary": {
                "friend": "pana",
                "money": "chavos",
            },
            "examples": [
                "Mano, el corillo esta brutal.",
                "Acho, ese jangueo estuvo duro.",
            ],
        }

        prompt = Backend.build_prompt("My friend is here", slang_context)

        self.assertIn("Common boricua flavor words", prompt)
        self.assertIn("friend -> pana", prompt)
        self.assertIn("Do not dump or summarize the whole file.", prompt)

    def test_parse_slang_context_accepts_json_shape(self):
        slang_context = {
            "tone_notes": ["Keep it playful."],
            "glossary": {
                "friend": "pana",
                "money": "chavos",
            },
            "examples": ["Mano, ese vibe esta duro."],
        }

        parsed = Backend.parse_slang_context(slang_context)

        self.assertEqual(parsed["tone_notes"], ["Keep it playful."])
        self.assertIn(("friend", "pana"), parsed["glossary"])
        self.assertEqual(parsed["examples"], ["Mano, ese vibe esta duro."])

    def test_parse_slang_context_preserves_normalized_glossary_entries(self):
        normalized_context = {
            "tone_notes": ["Keep it playful."],
            "glossary": [("friend", "pana"), ("money", "chavos")],
            "examples": ["Mano, ese vibe esta duro."],
        }

        parsed = Backend.parse_slang_context(normalized_context)

        self.assertIn(("friend", "pana"), parsed["glossary"])
        self.assertIn(("money", "chavos"), parsed["glossary"])

    @patch("Backend.load_slang_context", return_value={"glossary": {"friend": "pana"}})
    @patch("Backend.requests.post")
    def test_successful_api_translation_strips_reasoning(self, mock_post: Mock, _mock_context: Mock):
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "status": "ok",
            "prompt": "<reasoning>internal</reasoning>Hola, pana.",
        }
        mock_post.return_value = mock_response

        response = self.client.post("/translate", json={"text": "Hello, friend."})
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["translation"], "Hola, pana.")
        self.assertEqual(payload["source"], "api")

    @patch("Backend.load_slang_context", return_value={"glossary": {"friend": "pana"}})
    @patch("Backend.requests.post")
    def test_guardrail_rejection_uses_fallback(self, mock_post: Mock, _mock_context: Mock):
        mock_response = Mock()
        mock_response.ok = False
        mock_response.json.return_value = {
            "status": "invalid",
            "message": "prompt is outside allowed hackathon topics",
        }
        mock_post.return_value = mock_response

        response = self.client.post("/translate", json={"text": "Hello friend"})
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["translation"], "Wepa pana")
        self.assertEqual(payload["source"], "fallback")

    @patch("Backend.load_slang_context", return_value={})
    @patch("Backend.requests.post", side_effect=requests.RequestException("boom"))
    def test_network_failure_uses_fallback(self, _mock_post: Mock, _mock_context: Mock):
        response = self.client.post("/translate", json={"text": "Testing the translator"})
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["translation"], "Testing the translator, mano.")
        self.assertEqual(payload["source"], "fallback")


if __name__ == "__main__":
    unittest.main()
