from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kb_app.core.transcripts import extract_conversation_context


class TranscriptExtractionTests(unittest.TestCase):
    def write_jsonl(self, *entries: dict | str) -> Path:
        tmp = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".jsonl", delete=False)
        with tmp:
            for entry in entries:
                if isinstance(entry, str):
                    tmp.write(entry)
                else:
                    tmp.write(json.dumps(entry))
                tmp.write("\n")
        return Path(tmp.name)

    def test_extracts_claude_code_transcript_messages(self) -> None:
        path = self.write_jsonl(
            {"message": {"role": "system", "content": "ignore me"}},
            {"message": {"role": "user", "content": "How do hooks work?"}},
            {
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "They read stdin and print JSON."}],
                }
            },
        )

        context, turns = extract_conversation_context(path)

        self.assertEqual(turns, 2)
        self.assertIn("**User:** How do hooks work?", context)
        self.assertIn("**Assistant:** They read stdin and print JSON.", context)
        self.assertNotIn("ignore me", context)

    def test_extracts_codex_response_item_messages(self) -> None:
        path = self.write_jsonl(
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "developer",
                    "content": [{"type": "input_text", "text": "ignore developer context"}],
                },
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Add Windows support."}],
                },
            },
            {"type": "response_item", "payload": {"type": "reasoning", "encrypted_content": "..."}},
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "I will update the hooks."}],
                },
            },
            {"type": "response_item", "payload": {"type": "function_call", "name": "shell"}},
        )

        context, turns = extract_conversation_context(path)

        self.assertEqual(turns, 2)
        self.assertIn("**User:** Add Windows support.", context)
        self.assertIn("**Assistant:** I will update the hooks.", context)
        self.assertNotIn("ignore developer context", context)

    def test_skips_invalid_json_and_empty_content(self) -> None:
        path = self.write_jsonl(
            "{not json",
            {"message": {"role": "user", "content": ""}},
            {"message": {"role": "assistant", "content": ["useful answer"]}},
        )

        context, turns = extract_conversation_context(path)

        self.assertEqual(turns, 1)
        self.assertEqual(context.strip(), "**Assistant:** useful answer")

    def test_applies_turn_and_character_limits_on_turn_boundaries(self) -> None:
        path = self.write_jsonl(
            {"message": {"role": "user", "content": "first"}},
            {"message": {"role": "assistant", "content": "second"}},
            {"message": {"role": "user", "content": "third"}},
        )

        context, turns = extract_conversation_context(path, max_turns=2, max_context_chars=40)

        self.assertEqual(turns, 2)
        self.assertNotIn("first", context)
        self.assertIn("second", context)
        self.assertIn("third", context)
        self.assertTrue(context.startswith("**Assistant:**") or context.startswith("**User:**"))


if __name__ == "__main__":
    unittest.main()
