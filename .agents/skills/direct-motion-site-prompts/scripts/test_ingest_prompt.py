from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("ingest_prompt.py")


class IngestPromptTests(unittest.TestCase):
    def run_ingest(self, source: Path, corpus: Path, slug: str = "sample") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--source", str(source), "--slug", slug,
             "--source-kind", "operator-file", "--source-id", "test-source",
             "--corpus-dir", str(corpus)],
            text=True, capture_output=True, check=False,
        )

    def test_writes_exact_bytes_manifest_and_deduplicated_urls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / "prompt.txt"; corpus = root / "resources" / "corpus"
            data = b"Use https://example.com/a. Then https://example.com/a.\n"
            source.write_bytes(data)
            result = self.run_ingest(source, corpus)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((corpus / "sample.txt").read_bytes(), data)
            manifest = json.loads((corpus.parent / "corpus-manifest.json").read_text())
            self.assertEqual(manifest["entries"][0]["urls"], ["https://example.com/a"])
            self.assertEqual(manifest["entries"][0]["lines"], 1)

    def test_refuses_conflicting_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / "prompt.txt"; corpus = root / "resources" / "corpus"
            source.write_text("first")
            self.assertEqual(self.run_ingest(source, corpus).returncode, 0)
            source.write_text("second")
            result = self.run_ingest(source, corpus)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing to replace", result.stderr)

    def test_rejects_bad_slug(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / "prompt.txt"; source.write_text("prompt")
            result = self.run_ingest(source, root / "corpus", "Bad Slug")
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
