from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.zotero import zotero_ai_governance as governance


class LlmFirstGovernanceTests(unittest.TestCase):
    def test_model_api_commands_are_not_exposed(self) -> None:
        parser = governance.build_parser()
        for command in (
            "build-batch-file",
            "submit-batch",
            "aggregate-directions",
            "build-collection-plan",
            "build-tag-plan",
        ):
            with self.subTest(command=command), self.assertRaises(SystemExit):
                parser.parse_args([command])

    def test_agent_packet_contains_evidence_and_schema_without_api_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            corpus = root / "corpus.jsonl"
            packet = root / "packet.jsonl"
            instructions = root / "instructions.md"
            corpus.write_text(
                json.dumps({"item_key": "ITEM0001", "title": "Example"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            args = governance.build_parser().parse_args(
                [
                    "build-agent-packet",
                    "--corpus-jsonl",
                    str(corpus),
                    "--output-jsonl",
                    str(packet),
                    "--instructions-md",
                    str(instructions),
                ]
            )
            self.assertEqual(args.func(args), 0)
            record = json.loads(packet.read_text(encoding="utf-8").strip())
            self.assertEqual(record["item_key"], "ITEM0001")
            self.assertIn("evidence", record)
            self.assertNotIn("expected_result", record)
            self.assertNotIn("url", record)
            self.assertNotIn("model", record)
            instruction_text = instructions.read_text(encoding="utf-8")
            self.assertIn("must not call a language-model API", instruction_text)
            self.assertIn('"required"', instruction_text)

    def test_plain_agent_result_is_validated_and_legacy_api_envelope_is_rejected(self) -> None:
        result = {field: [] for field in governance.classification_schema()["required"]}
        result.update(
            {
                "item_key": "ITEM0001",
                "type_tag": "",
                "needs_manual_review": True,
                "evidence": "title only",
            }
        )
        item_key, parsed, error = governance.parse_agent_result_line(json.dumps(result))
        self.assertEqual(item_key, "ITEM0001")
        self.assertEqual(parsed, result)
        self.assertEqual(error, "")

        item_key, parsed, error = governance.parse_agent_result_line(
            json.dumps({"custom_id": "ITEM0001", "response": {"status_code": 200}})
        )
        self.assertEqual(item_key, "ITEM0001")
        self.assertIsNone(parsed)
        self.assertIn("legacy model API", error)


if __name__ == "__main__":
    unittest.main()
