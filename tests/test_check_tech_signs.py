"""Проверки для scripts/check_tech_signs.py. Запуск: python3 -m unittest discover tests"""

import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import check_tech_signs as cts  # noqa: E402

SCRIPT = os.path.join(ROOT, "scripts", "check_tech_signs.py")

DIRTY = (
    "Компания основана в 2015 году. :contentReference[oaicite:1]{index=1}\n"
    "Источник: https://example.org/news?utm_source=chatgpt.com\n"
    "Ещё одна ссылка https://example.org/a?referrer=grok.com и citeturn0search3\n"
    "|access-date=2025-xx-xx\n"
    "Ссылка на трек: PASTE_SPOTIFY_TRACK_URL_HERE ↩\n"
    "Это <mark>известный музыкант</mark>.\n"
)

CLEAN = (
    "Завод открыли в 1987 году. В 2015-м его купила местная компания,\n"
    "сейчас там работает около трёхсот человек (данные сайта завода).\n"
    "Подробнее: https://example.org/history?utm_source=newsletter\n"
    "Архив: https://web.archive.org/web/2020/https://example.org/history\n"
    "Редирект: https://example.org/go?url=https://example.com/page&lang=ru\n"
)

GLUED = (
    "История правок: https://ru.wikipedia.org/w/index.php?title=%D0%92%D0%B0"
    "https://ru.wikipedia.org/w/index.php?title=X&action=historyaction=history\n"
)

MD_DOC = (
    "# Скрипт\n"
    "\n"
    "Ищет `utm_source=chatgpt.com` и ``contentReference[oaicite:0]``.\n"
    "\n"
    "```\n"
    "referrer=grok.com\n"
    "|access-date=2025-xx-xx\n"
    "```\n"
    "\n"
    "~~~text\n"
    "PASTE_URL_HERE\n"
    "~~~\n"
    "\n"
    "А это настоящий след: https://example.org/?utm_source=openai\n"
)


class ScanTest(unittest.TestCase):
    def labels(self, text, markers=cts.MARKERS, skip_code=False):
        return {h[2] for h in cts.scan(text, markers, skip_code)}

    def test_dirty_text(self):
        found = self.labels(DIRTY)
        for label in ("oaicite", "utm-chatbot", "referrer-grok", "turnNsearch",
                      "placeholder-date", "placeholder", "footnote-arrow", "mark-tag"):
            self.assertIn(label, found)

    def test_clean_text(self):
        self.assertEqual(cts.scan(CLEAN, cts.MARKERS), [])

    def test_line_and_column(self):
        hits = cts.scan("abc\nxx utm_source=openai", cts.MARKERS)
        self.assertEqual(hits[0][:3], (2, 4, "utm-chatbot"))

    def test_markdown_only_on_request(self):
        text = "## Заголовок\n**жирный** и [ссылка](https://example.org)\n"
        self.assertEqual(self.labels(text), set())
        self.assertEqual(self.labels(text, cts.MARKERS + cts.MARKDOWN),
                         {"md-heading", "md-bold", "md-link"})


class GluedUrlTest(unittest.TestCase):
    def test_glued_url_and_duplicate_param(self):
        hits = cts.scan(GLUED, cts.MARKERS)
        labels = [h[2] for h in hits]
        self.assertIn("url-glued", labels)
        self.assertIn("url-dup-param", labels)
        dup = [h for h in hits if h[2] == "url-dup-param"][0]
        self.assertEqual(dup[4], "action=historyaction=history")
        glued = [h for h in hits if h[2] == "url-glued"][0]
        self.assertTrue(glued[4].endswith("https://"))
        self.assertEqual(GLUED[glued[1] - 1:glued[1] + 7], "https://")

    def test_repeated_pair_with_ampersand(self):
        hits = cts.scan("https://example.org/?a=1&b=2&a=1\n", cts.MARKERS)
        self.assertEqual([(h[2], h[4]) for h in hits], [("url-dup-param", "a=1")])

    def test_archive_and_redirect_are_not_glued(self):
        text = ("https://web.archive.org/web/20200101000000id_/https://example.org\n"
                "https://example.org/go?to=https://example.com\n"
                "https://example.org/?page=2&sort=asc\n")
        self.assertEqual(cts.scan(text, cts.MARKERS), [])


class SkipCodeTest(unittest.TestCase):
    def test_code_is_scanned_by_default_in_scan(self):
        found = {h[2] for h in cts.scan(MD_DOC, cts.MARKERS)}
        self.assertTrue({"utm-chatbot", "oaicite", "referrer-grok",
                         "placeholder-date", "placeholder"} <= found)

    def test_skip_code_ignores_inline_and_fenced(self):
        hits = cts.scan(MD_DOC, cts.MARKERS, skip_code=True)
        self.assertEqual([(h[0], h[2], h[4]) for h in hits],
                         [(14, "utm-chatbot", "utm_source=openai")])

    def test_skip_code_keeps_positions_and_fences(self):
        masked = cts.mask_code(MD_DOC)
        self.assertEqual(masked.count("\n"), MD_DOC.count("\n"))
        self.assertEqual(len(masked), len(MD_DOC))
        fences = [h for h in cts.scan(MD_DOC, cts.MARKERS + cts.MARKDOWN, skip_code=True)
                  if h[2] == "md-fence"]
        self.assertEqual([h[0] for h in fences], [5, 8])

    def test_unclosed_backtick_is_not_code(self):
        text = "Одна ` кавычка и utm_source=openai\n"
        self.assertEqual(len(cts.scan(text, cts.MARKERS, skip_code=True)), 1)

    def test_default_depends_on_extension(self):
        self.assertTrue(cts.should_skip_code("README.md", "auto"))
        self.assertTrue(cts.should_skip_code("notes.MARKDOWN", "auto"))
        self.assertFalse(cts.should_skip_code("article.txt", "auto"))
        self.assertFalse(cts.should_skip_code("-", "auto"))
        self.assertTrue(cts.should_skip_code("article.txt", "skip"))
        self.assertFalse(cts.should_skip_code("README.md", "keep"))


class CliTest(unittest.TestCase):
    def run_cli(self, *args, stdin=None):
        return subprocess.run([sys.executable, SCRIPT] + list(args), input=stdin,
                              capture_output=True, text=True)

    def test_cli_exit_codes(self):
        dirty = self.run_cli("-", stdin=DIRTY)
        self.assertEqual(dirty.returncode, 1)
        self.assertIn("oaicite", dirty.stdout)
        clean = self.run_cli("-", stdin=CLEAN)
        self.assertEqual(clean.returncode, 0)
        missing = self.run_cli("/nonexistent/file.txt")
        self.assertEqual(missing.returncode, 2)

    def test_cli_code_flags(self):
        with tempfile.TemporaryDirectory() as d:
            md = os.path.join(d, "doc.md")
            txt = os.path.join(d, "doc.txt")
            for p in (md, txt):
                with open(p, "w", encoding="utf-8") as f:
                    f.write(MD_DOC)
            self.assertEqual(self.run_cli(md).stdout.count("\n"), 1)
            self.assertGreater(self.run_cli("--keep-code", md).stdout.count("\n"), 1)
            self.assertGreater(self.run_cli(txt).stdout.count("\n"), 1)
            self.assertEqual(self.run_cli("--skip-code", txt).stdout.count("\n"), 1)
            self.assertEqual(self.run_cli("--skip-code", "-", stdin=MD_DOC).stdout.count("\n"), 1)


if __name__ == "__main__":
    unittest.main()
