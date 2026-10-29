# AI writing patterns (ai-text-signs)

[Русская версия](README.md)

An agent skill (Claude Code, Cursor, Codex and other tools that read `SKILL.md`) and a plain editing checklist for analyzing patterns typical of AI-generated writing. It shows which patterns a text uses, where and how densely, explains why they read badly, and helps rewrite the text in plain language. The skill itself is written in Russian and is tuned for Russian text; the English Wikipedia material is translated and summarized.

It is not an AI detector and does not tell you who wrote a text. People use the same patterns, and an AI draft that has been edited (for example with this skill) may show very few of them.

It is based on two Wikipedia pages: Russian [«Википедия:Признаки сгенерированности текста»](https://ru.wikipedia.org/wiki/Википедия:Признаки_сгенерированности_текста) and English [Wikipedia:Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing). The patterns are grouped into 19 categories, followed by a list of things that are *not* patterns, 16 rewriting rules and a section on technical traces.

## Modes

- Audit (Аудит, pattern analysis) quotes each pattern, says where it occurs and rates density on a four-step scale: none, isolated, noticeable, dense. Technical traces such as `oaicite` are reported on a separate line.
- Cleanup (Чистка) rewrites the text, keeps the author's facts, names, numbers and links, never invents new ones (missing facts are marked `[нужен факт]`), and lists the edits.

[examples/](examples/) has one audit and two cleanups, all on invented texts.

## Install

The folder name must match the `name` field: `ai-text-signs`.

```bash
# Claude Code
git clone https://github.com/GlebKostousov/ai-text-signs ~/.claude/skills/ai-text-signs
# Cursor
git clone https://github.com/GlebKostousov/ai-text-signs ~/.cursor/skills/ai-text-signs
# Codex and other agents that read ~/.agents/skills
git clone https://github.com/GlebKostousov/ai-text-signs ~/.agents/skills/ai-text-signs
```

Project-level installs go to `.claude/skills/`, `.cursor/skills/` or `.agents/skills/` inside the project. Without an agent, paste `SKILL.md` into a system prompt or use section 3 as a checklist.

## Technical traces script

```bash
python3 scripts/check_tech_signs.py article.txt            # exit 0: nothing found, 1: hits, 2: read error
python3 scripts/check_tech_signs.py --markdown wiki.txt    # also flag Markdown
python3 scripts/check_tech_signs.py --skip-code notes.txt  # ignore inline code and code blocks
python3 scripts/check_tech_signs.py --keep-code README.md  # scan code too
python3 -m unittest discover tests
```

It looks for `contentReference[oaicite:…]`, `utm_source=chatgpt.com`, `utm_source=openai`, `referrer=grok.com`, `turn0search0`, `2025-xx-xx` placeholder dates, `PASTE_…_HERE` templates, `↩` footnote arrows and `<mark>` tags. It also flags glued URLs (a second `https://` stuck inside an address, or a parameter repeated back to back like `action=historyaction=history`); these usually come from careless copying rather than AI, but the link is broken either way. In `.md`, `.markdown` and `.mdx` files inline code and fenced blocks are skipped by default, since documentation tends to quote the markers there. Standard library only, Python 3.8+.

## Limitations

The skill catches techniques, not origin. Pattern density says nothing reliable about authorship: an AI text cleaned with this skill will show few patterns, and a person writing to a press-release template will show many. Only technical traces such as `oaicite` or chatbot UTM tags are strong evidence that a chatbot touched the text, and even they do not show that it wrote all of it. After a cleanup some residue may stay, such as an even rhythm or lots of "label: explanation" colons.

A single pattern means little; clusters from different groups carry weight. AI detectors are unreliable and their scores are not proof. Models and human writing habits change, and the catalog only reflects the Wikipedia pages as of 2026-10-29.

## Attribution and license

Derived from text by Wikipedia contributors: [ru revision 155487940](https://ru.wikipedia.org/w/index.php?oldid=155487940) and [en revision 1382312561](https://en.wikipedia.org/w/index.php?oldid=1382312561), retrieved 2026-10-29. Unmodified wikitext is in [sources/](sources/); details and the list of changes are in [ATTRIBUTION.md](ATTRIBUTION.md).

Licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), see [LICENSE](LICENSE).
