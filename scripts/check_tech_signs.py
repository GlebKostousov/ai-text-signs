#!/usr/bin/env python3
"""Поиск технических следов чат-ботов в тексте (раздел 6 SKILL.md).

Ищет остатки разметки ChatGPT и других сервисов, UTM-метки чат-ботов,
шаблонные заглушки, даты вида 2025-xx-xx и склеенные ссылки. Находка говорит
о том, что текст или ссылки прошли через чат-бот (или были испорчены при
копировании), но не доказывает, что текст написал ИИ.

Использование:
    python3 scripts/check_tech_signs.py статья.txt [ещё_файл.md ...]
    cat статья.txt | python3 scripts/check_tech_signs.py -
    python3 scripts/check_tech_signs.py --markdown вики.txt
    python3 scripts/check_tech_signs.py --skip-code заметка.txt
    python3 scripts/check_tech_signs.py --keep-code README.md

Код в Markdown: в файлах .md, .markdown и .mdx встроенный код `…` и блоки
в тройных обратных кавычках (или ~~~) по умолчанию пропускаются, потому что
там обычно стоят примеры маркеров, а не сами следы. --skip-code включает
пропуск для любых файлов и stdin, --keep-code выключает его везде.

Коды выхода: 0 — ничего не найдено, 1 — есть находки, 2 — ошибка чтения.
Нужен только Python 3.8+, сторонних библиотек нет.
"""

import argparse
import os
import re
import sys

MD_EXTENSIONS = (".md", ".markdown", ".mdx")

URL_RX = re.compile(r"https?://[^\s<>\"'`\]\)]+", re.I)
# Второй адрес внутри первого, приклеенный без разделителя: …%D0%B0https://…
# Адреса после '/', '=', '?' и т. п. (веб-архив, редиректы) не трогаем.
GLUED_SCHEME_RX = re.compile(r"(?<=[A-Za-z0-9%_.~-])https?://", re.I)
# Параметр, повторённый вплотную: action=historyaction=history
GLUED_PARAM_RX = re.compile(r"(?<![\w%.-])([A-Za-z_][\w.-]*=[\w.%-]+?)\1(?![\w%])")


def find_glued_urls(text):
    """Склеенные и испорченные адреса: (позиция, фрагмент)."""
    for url in URL_RX.finditer(text):
        u = url.group(0)
        m = GLUED_SCHEME_RX.search(u, 1)
        if m:
            i = m.start()
            yield url.start() + i, u[max(0, i - 12):i + 8]


def find_duplicate_params(text):
    """Повторы параметров запроса в одном адресе: (позиция, фрагмент)."""
    for url in URL_RX.finditer(text):
        u = url.group(0)
        q = u.find("?")
        if q < 0:
            continue
        query = u[q + 1:].split("#", 1)[0]
        hit = GLUED_PARAM_RX.search(query)
        if hit:
            yield url.start() + q + 1 + hit.start(), hit.group(0)
            continue
        seen, offset = set(), q + 1
        for pair in query.split("&"):
            if "=" in pair and pair in seen:
                yield url.start() + offset, pair
                break
            seen.add(pair)
            offset += len(pair) + 1


# (метка, пояснение, регулярное выражение или функция поиска)
MARKERS = [
    ("oaicite", "внутренняя разметка цитат ChatGPT",
     re.compile(r":?contentReference\[oaicite:\d+\](?:\{index=\d+\})?|oaicite", re.I)),
    ("oai_citation", "внутренняя разметка цитат ChatGPT",
     re.compile(r"oai_citation[\w:]*", re.I)),
    ("turnNsearch", "служебная ссылка на результат поиска ChatGPT",
     re.compile(r"\bcite(?:turn\d+\w*)+|\bturn\d+(?:search|news|view|fetch|image|file|product)\d+\b", re.I)),
    ("private-use", "невидимые служебные символы (U+E200–U+E2FF), встречаются в копиях из ChatGPT",
     re.compile(r"[\ue200-\ue2ff]")),
    ("utm-chatbot", "ссылку нашёл чат-бот (UTM-метка)",
     re.compile(r"utm_source=(?:chatgpt\.com|openai|copilot\.com|perplexity(?:\.ai)?)\b", re.I)),
    ("referrer-grok", "ссылку нашёл Grok",
     re.compile(r"referrer=grok\.com", re.I)),
    ("placeholder-date", "дата-заглушка",
     re.compile(r"\b(?:19|20)\d\d-xx-xx\b", re.I)),
    ("placeholder", "незаполненный шаблон",
     re.compile(r"\b(?:PASTE|INSERT)_[A-Z0-9_]+\b"
                r"|\[(?:Insert|Your|Name of|Describe|Вставьте|Укажите|Опишите|Имя|Название)\b[^\]\n]{0,80}\]")),
    ("footnote-arrow", "символ ↩ у сносок, скопированных из интерфейса чат-бота",
     re.compile("\u21a9")),
    ("mark-tag", "тег <mark>, остаток перепроверки Gemini",
     re.compile(r"</?mark>", re.I)),
    ("ai-disclaimer", "реплика чат-бота о себе",
     re.compile(r"as an AI language model|as of my (?:last )?knowledge (?:update|cutoff)"
                r"|как (?:языковая )?модель ИИ|по состоянию на (?:моё|мое) последнее обновление", re.I)),
    ("url-glued", "в адрес вклеен второй адрес (битая ссылка, чаще от копирования, чем от ИИ)",
     find_glued_urls),
    ("url-dup-param", "параметр в адресе повторён (битая или склеенная ссылка)",
     find_duplicate_params),
]

# Markdown — признак только там, где ждали другую разметку (вики, CMS, письмо).
MARKDOWN = [
    ("md-bold", "Markdown-жирный **…**", re.compile(r"\*\*[^*\n]+\*\*")),
    ("md-heading", "Markdown-заголовок #", re.compile(r"^#{1,6} \S", re.M)),
    ("md-link", "Markdown-ссылка [текст](url)", re.compile(r"\[[^\]\n]+\]\(https?://[^)\s]+\)")),
    ("md-fence", "блок кода ```", re.compile(r"^```", re.M)),
]

FENCE_RX = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")
INLINE_CODE_RX = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.S)


def _blank(s):
    """Заменить всё, кроме переводов строк, пробелами: номера строк и столбцов не сдвигаются."""
    return re.sub(r"[^\n]", " ", s)


def mask_code(text):
    """Скрыть код Markdown: содержимое блоков ``` / ~~~ и встроенный код `…`.

    Сами строки-ограждения (``` и ~~~) остаются, чтобы --markdown по-прежнему
    их видел; информационная строка после них и содержимое заменяются пробелами.
    """
    out, fence = [], None
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        tail = line[len(body):]
        m = FENCE_RX.match(body)
        if fence is None:
            if m and not (m.group(2)[0] == "`" and "`" in m.group(3)):
                fence = m.group(2)
                keep = len(m.group(1)) + len(fence)
                out.append(body[:keep] + _blank(body[keep:]) + tail)
            else:
                out.append(line)
        else:
            if m and m.group(2)[0] == fence[0] and len(m.group(2)) >= len(fence) and not m.group(3).strip():
                out.append(line)
                fence = None
            else:
                out.append(_blank(body) + tail)
    text = "".join(out)

    def inline(m):
        if re.search(r"\n[ \t]*\n", m.group(0)):  # код не переходит через пустую строку
            return m.group(0)
        return _blank(m.group(0))

    return INLINE_CODE_RX.sub(inline, text)


def _matches(finder, text):
    if hasattr(finder, "finditer"):
        for m in finder.finditer(text):
            yield m.start(), m.group(0)
    else:
        yield from finder(text)


def scan(text, markers, skip_code=False):
    """Вернуть список (строка, столбец, метка, пояснение, фрагмент)."""
    if skip_code:
        text = mask_code(text)
    hits = []
    line_starts = [0] + [m.end() for m in re.finditer(r"\n", text)]
    for label, note, finder in markers:
        for pos, frag in _matches(finder, text):
            lo, hi = 0, len(line_starts) - 1
            while lo < hi:  # бинарный поиск номера строки
                mid = (lo + hi + 1) // 2
                if line_starts[mid] <= pos:
                    lo = mid
                else:
                    hi = mid - 1
            if label == "private-use":
                frag = "U+%04X" % ord(frag)
            hits.append((lo + 1, pos - line_starts[lo] + 1, label, note, frag))
    hits.sort()
    return hits


def should_skip_code(path, mode):
    if mode == "skip":
        return True
    if mode == "keep":
        return False
    return path != "-" and path.lower().endswith(MD_EXTENSIONS)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Ищет технические следы чат-ботов (oaicite, utm_source=chatgpt.com, turn0search, "
                    "2025-xx-xx, склеенные ссылки и т. п.).")
    ap.add_argument("files", nargs="+", help="файлы для проверки, '-' для stdin")
    ap.add_argument("--markdown", action="store_true",
                    help="также отмечать Markdown (полезно для вики-текстов и писем)")
    code = ap.add_mutually_exclusive_group()
    code.add_argument("--skip-code", dest="code", action="store_const", const="skip",
                      help="пропускать встроенный код и блоки кода в любых файлах "
                           "(по умолчанию только в .md, .markdown, .mdx)")
    code.add_argument("--keep-code", dest="code", action="store_const", const="keep",
                      help="проверять и код, в том числе в .md")
    ap.set_defaults(code="auto")
    args = ap.parse_args(argv)

    markers = MARKERS + (MARKDOWN if args.markdown else [])
    total, failed = 0, False
    for path in args.files:
        try:
            if path == "-":
                text = sys.stdin.read()
            else:
                with open(path, encoding="utf-8", errors="replace") as f:
                    text = f.read()
        except OSError as e:
            print(f"{path}: не удалось прочитать: {e}", file=sys.stderr)
            failed = True
            continue
        name = "<stdin>" if path == "-" else path
        for line, col, label, note, frag in scan(text, markers, should_skip_code(path, args.code)):
            print(f"{name}:{line}:{col}: [{label}] {frag!r} — {note}")
            total += 1

    print(f"Найдено: {total}", file=sys.stderr)
    if failed:
        return 2
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
