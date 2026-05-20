---
name: writing-voice-mangle-log
description: Emit a structured voice-mangle log block when a Wispr Flow dictation mishear is detected and corrected. Format feeds repo-recall, eventually a Luca asker for Wispr Flow's per-user dictionary. Strict mode - undercount, don't poison the corpus. Triggers - voice mangling, dictation mangle, mishear, Wispr Flow, I meant, mangled token, mangled name, voice clipping, transcription error, phonetic mistype, homophone swap.
---

# voice-mangle-log

Kai dictates into Claude Code constantly via Wispr Flow. Common mangle shapes: CLI / repo / tool names misheard as English words, random English nouns where a tool name was expected, phonetic neighbors of technical terms, dropped or doubled syllables, homophone swaps. Specific mangle examples do not belong in this file - they live in the structured log entries themselves and feed forward to the dictionary. Putting them here would pollute every session's context with the wrong spellings.

When you detect a mangle and correct it, emit one block per detected mangle at the **top of your response**, before the body. This keeps the corpus signal in a predictable position for repo-recall full-text search and the future Wispr Flow asker.

## Format

Exact, verbatim:

```
- voice mangling
- Input speech: <verbatim mangled text from Kai's input>
- Output correction: <what she meant>
```

One block per mangle. If a turn has three mangles, emit three blocks back-to-back.

## Strict mode

Only emit when **both** are true:

1. High confidence the mishear is real (the word is out-of-place enough that a reader would notice, and you have a plausible target).
2. You can name the intended target with high confidence from context (existing CLI name, repo name, prior chat, AGENTS.md content).

If either is shaky, skip. False-positive entries poison the dictionary signal that will eventually feed Wispr Flow. Better to undercount.

**Do skip:**
- Single-letter typos.
- Plausible spellings that just look unfamiliar.
- Anything you'd silently recover from without commentary.
- Repeated mangles in the same turn (one block per distinct mangle, not per occurrence).

**Do emit:**
- Absurd-looking mishears where the durable fix matters.
- CLI / repo / tool-name mangles (highest-value entries for the dictionary).
- Proper-noun mangles where Kai's intent is clear from context.

## Why

Kai's dictation pipeline produces (mangled, intended) pairs constantly, and her next turn corrects them - so every pair has built-in ground truth without human labeling. The structured block puts that signal into repo-recall's full-text index. A future "luca-wispr-asker" tool will pull recent blocks and surface them to Wispr Flow (currently via manual curation of [agentic-os-kai#492](https://github.com/coilysiren/agentic-os-kai/issues/492), eventually via a Wispr Flow MCP that doesn't exist yet but is being lobbied for).

## Relationship to kai-collaboration

[[kai-collaboration]] section "Recover from severely mangled dictation" carries the recovery rule (continue with the right interpretation, don't stall). This skill carries the **format** of the durable signal. Apply both together: recover seamlessly in the response body, emit the structured block at the top of the turn.
