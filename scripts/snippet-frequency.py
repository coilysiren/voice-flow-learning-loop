#!/usr/bin/env python3
"""Loop 2 layer 2: one-shot snippet-candidate mining over Claude Code session JSONL.

Walks session JSONL files, extracts Kai's dictation (user-role messages with
plain-string content), strips harness wrappers and Snippet expansions, and
counts word-n-grams above a length floor. Outputs a Markdown candidate list
shaped like layer 1's manual mining run.

Stdlib only. See voice-flow-learning-loop#16.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from collections import Counter
from dataclasses import dataclass

DEFAULT_SESSIONS_DIR = pathlib.Path.home() / ".claude" / "projects"
DEFAULT_N_MIN = 3
DEFAULT_N_MAX = 25
DEFAULT_LENGTH_FLOOR = 30
DEFAULT_TOP_K = 50

# Harness wrappers that show up inside user-role messages but are not Kai's
# dictation. Stripped before n-gram extraction.
WRAPPER_PATTERNS = [
    re.compile(r"<command-name>.*?</command-name>", re.DOTALL),
    re.compile(r"<command-message>.*?</command-message>", re.DOTALL),
    re.compile(r"<command-args>.*?</command-args>", re.DOTALL),
    re.compile(r"<command-stdout>.*?</command-stdout>", re.DOTALL),
    re.compile(r"<local-command-stdout>.*?</local-command-stdout>", re.DOTALL),
    re.compile(r"<bash-input>.*?</bash-input>", re.DOTALL),
    re.compile(r"<bash-stdout>.*?</bash-stdout>", re.DOTALL),
    re.compile(r"<bash-stderr>.*?</bash-stderr>", re.DOTALL),
    re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL),
    re.compile(r"<user-prompt-submit-hook>.*?</user-prompt-submit-hook>", re.DOTALL),
    re.compile(r"<task-notification>.*?</task-notification>", re.DOTALL),
    re.compile(r"<event>.*?</event>", re.DOTALL),
    re.compile(r"<summary>.*?</summary>", re.DOTALL),
    re.compile(r"<task-id>.*?</task-id>", re.DOTALL),
    # Fenced code blocks - paste-only, not dictation.
    re.compile(r"```.*?```", re.DOTALL),
    # URLs - paste-only.
    re.compile(r"https?://\S+"),
    # The $$..$$ Snippet expansion marker (see voice-flow-learning-loop#14).
    re.compile(r"\$\$.*?\$\$", re.DOTALL),
]

# Heuristics for "this looks like a Task-tool subagent prompt, not Kai's
# dictation." Subagent prompts get logged as user-role messages in the parent
# session JSONL, so the type=user / role=user filter alone isn't enough.
SUBAGENT_PROMPT_PREFIXES = (
    "you're labeling",
    "you are labeling",
    "you're a",
    "you are a",
    "you're an",
    "you are an",
    "your task is",
    "your job is",
    "output one ",
    "output only ",
    "below is ",
    "below are ",
    "given the ",
    "here is ",
    "here are ",
    "the following ",
    "summarize ",
    "label the ",
    "classify ",
    "rate the ",
    "score the ",
    "extract ",
)

# Real dictation tops out well under 2000 chars. Subagent prompts are usually
# much longer. Hard upper bound to filter the obvious cases.
MAX_DICTATION_LENGTH = 1500

# Tokens to drop word-by-word after wrapper stripping. Anything matching is
# treated as non-dictation cruft.
TOKEN_DROP = re.compile(r"^[^\w]+$")


@dataclass
class Candidate:
    text: str
    count: int
    n: int

    @property
    def length(self) -> int:
        return len(self.text)


def iter_session_files(root: pathlib.Path):
    yield from root.rglob("*.jsonl")


def extract_user_messages(jsonl_path: pathlib.Path):
    """Yield plain-string content from genuine user-role messages."""
    try:
        with jsonl_path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("type") != "user":
                    continue
                msg = rec.get("message") or {}
                if msg.get("role") != "user":
                    continue
                content = msg.get("content")
                # tool_result and other structured content arrive as a list of
                # blocks - skip those, they aren't dictation.
                if not isinstance(content, str):
                    continue
                if looks_like_subagent_prompt(content):
                    continue
                if len(content) > MAX_DICTATION_LENGTH:
                    continue
                yield content
    except (OSError, UnicodeDecodeError):
        return


def looks_like_subagent_prompt(content: str) -> bool:
    stripped = content.lstrip()
    head = stripped[:60].lower()
    if head.startswith("<"):
        # Wrapped harness injection (task-notification, etc).
        return True
    if head.startswith(SUBAGENT_PROMPT_PREFIXES):
        return True
    # Multi-section structured prompts (autonomous-engineering planner output,
    # AFK dispatch prompts, etc.) have multiple blank-line-separated sections
    # and / or numbered top-level lists. Real dictation rarely does.
    if content.count("\n\n") >= 3:
        return True
    if re.match(r"^\s*\d+\.\s", content) and content.count("\n") >= 5:
        return True
    return False


def strip_wrappers(text: str) -> str:
    for pat in WRAPPER_PATTERNS:
        text = pat.sub(" ", text)
    return text


def tokenize(text: str) -> list[str]:
    """Whitespace tokenize, drop punctuation-only tokens, keep case."""
    tokens = text.split()
    return [t for t in tokens if not TOKEN_DROP.match(t)]


def ngrams(tokens: list[str], n: int):
    for i in range(len(tokens) - n + 1):
        yield " ".join(tokens[i : i + n])


def mine(
    sessions_dir: pathlib.Path,
    n_min: int,
    n_max: int,
    length_floor: int,
) -> Counter:
    counter: Counter = Counter()
    files = list(iter_session_files(sessions_dir))
    print(f"# scanning {len(files)} session files under {sessions_dir}", file=sys.stderr)
    for i, path in enumerate(files, 1):
        if i % 100 == 0:
            print(f"# {i}/{len(files)} files, {len(counter)} distinct n-grams so far", file=sys.stderr)
        for content in extract_user_messages(path):
            cleaned = strip_wrappers(content)
            tokens = tokenize(cleaned)
            for n in range(n_min, n_max + 1):
                if len(tokens) < n:
                    break
                for gram in ngrams(tokens, n):
                    if len(gram) >= length_floor:
                        counter[(gram, n)] += 1
    return counter


def top_candidates(counter: Counter, top_k: int) -> list[Candidate]:
    rows = [Candidate(text=gram, count=count, n=n) for (gram, n), count in counter.items() if count >= 2]
    rows.sort(key=lambda r: (-r.count, -r.length))
    return collapse_substrings(rows)[:top_k]


def collapse_substrings(rows: list[Candidate]) -> list[Candidate]:
    """For rows with the same count, keep only those that aren't a substring
    of a longer row at the same count. Cuts down nested-n-gram noise (e.g.
    "coily ops gh" / "coily ops gh issue" / "coily ops gh issue create" all
    at count 30 collapse to the longest)."""
    by_count: dict[int, list[Candidate]] = {}
    for r in rows:
        by_count.setdefault(r.count, []).append(r)
    out: list[Candidate] = []
    for count in sorted(by_count.keys(), reverse=True):
        bucket = sorted(by_count[count], key=lambda r: -r.length)
        kept: list[Candidate] = []
        for r in bucket:
            if any(r.text in k.text for k in kept):
                continue
            kept.append(r)
        out.extend(kept)
    return out


def write_markdown(rows: list[Candidate], out_path: pathlib.Path, source: pathlib.Path) -> None:
    lines = []
    lines.append(f"# Snippet candidates - layer 2 frequency script")
    lines.append("")
    lines.append(f"Source: `{source}`")
    lines.append("")
    lines.append("Filter: user-role messages only, harness wrappers / fenced code / URLs / `$$..$$` stripped, length floor 30 chars, word-n-grams across configured range, minimum count 2, substring-collapsed within same-count buckets.")
    lines.append("")
    lines.append("Sorted by raw count desc, then length desc. Known limitation: overlapping sliding-window n-grams of the same phrase at the same count are not merged, so a single high-frequency long prompt produces many adjacent rows. Layer 6 (phrase-shape extractors) addresses this.")
    lines.append("")
    lines.append("| # | count | len | n | phrase |")
    lines.append("|---|------:|----:|--:|--------|")
    for i, row in enumerate(rows, 1):
        text = row.text.replace("|", r"\|").replace("\n", " ")
        lines.append(f"| {i} | {row.count} | {row.length} | {row.n} | `{text}` |")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions-dir", type=pathlib.Path, default=DEFAULT_SESSIONS_DIR)
    parser.add_argument("--n-min", type=int, default=DEFAULT_N_MIN)
    parser.add_argument("--n-max", type=int, default=DEFAULT_N_MAX)
    parser.add_argument("--length-floor", type=int, default=DEFAULT_LENGTH_FLOOR)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--out", type=pathlib.Path, required=True, help="Markdown output path")
    args = parser.parse_args(argv)

    counter = mine(args.sessions_dir, args.n_min, args.n_max, args.length_floor)
    rows = top_candidates(counter, args.top_k)
    write_markdown(rows, args.out, args.sessions_dir)
    print(f"# wrote {len(rows)} rows to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
