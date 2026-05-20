# voice-flow-learning-loop

Reference index for Kai's dictation meta-improvement loop. Every piece is sourcelinked except Luca, which stays private for the time being.

## What the loop is

Kai dictates into Claude Code constantly via Wispr Flow. When the dictation pipeline mishears (a CLI name lands as an English word, a tool name lands as a homophone, a proper noun gets phonetically swapped), the next turn in chat already has the correction baked in - she or the model surfaces what was meant from context. That makes every voice mishear a self-labeled training pair, no human annotation needed.

The loop captures those pairs as structured corpus signal, indexes them locally, and routes them toward Wispr Flow's per-user dictionary so the same mishear doesn't recur. The sink is currently a manual curation step; the goal is for it to land as an MCP call against Wispr Flow directly.

```
dictation  ->  chat correction  ->  structured log block  ->  repo-recall index
                                                                     |
                                            ( Luca asker, private )  v
                                                                     |
                                            Wispr Flow dictionary  <-+
                                            ( currently manual; MCP lobbied for )
```

## Pieces

### Signal source: the structured log block

Emitted at the top of any chat turn where the model detects a voice mishear and corrects it. Format is exact:

```
- voice mangling
- Input speech: <verbatim mangled text from the user's input>
- Output correction: <what they meant>
```

One block per detected mishear. The leading `- voice mangling` phrase is the anchor that full-text indexing pins on. The two prefixed lines are stable enough for downstream regex parsing without an LLM pass.

### Detection rule: `writing-voice-mangle-log`

Thin skill carrying the format spec and the trigger surface. Lives in agentic-os-kai.

- Skill: [`writing-voice-mangle-log/SKILL.md`](https://github.com/coilysiren/agentic-os-kai/blob/main/.claude/skills/writing-voice-mangle-log/SKILL.md)
- Tracking issue: [coilysiren/agentic-os-kai#628](https://github.com/coilysiren/agentic-os-kai/issues/628)

Strict mode by default: only emit when both the mishear and the intended target are high-confidence. False-positive entries poison the dictionary signal.

### Recovery rule: `kai-collaboration`

The unconditional companion to the detection skill. Tells the model to recover seamlessly in the response body and emit the structured block at the top. Lives in agentic-os-kai.

- Rule: [`kai-collaboration/SKILL.md` "Recover from severely mangled dictation"](https://github.com/coilysiren/agentic-os-kai/blob/main/.claude/skills/kai-collaboration/SKILL.md)
- Origin: agentic-os-kai#492 (the original dictionary tracking issue this loop supersedes for the chat-emit path)

### Corpus indexer: repo-recall

Local-only Rust + axum + MCP daemon that scans on-disk repos, sessions, and commits and serves them via JSON and MCP (`recall_search`, `recall_dashboard`, `recall_session`, etc.). The structured log block lands in Claude Code session JSONL files and gets full-text-indexed on the next scan.

- Repo: [coilysiren/repo-recall](https://github.com/coilysiren/repo-recall)
- MCP surface: `recall_search` is the entry point. The Luca asker stack consumes from here.

### Asker: Luca (private)

Natural-language consumer over repo-recall data. Routes questions to a dispatch table and returns focused answers. The asker for this loop pulls recent log blocks and surfaces them as candidate dictionary entries. Private repo for the time being; capability described here, source not linked.

A staging instance is wired into mcporter as `luca-staging`. Auto-reached by Kai's session-config for any past-work-recall question.

### Sink target: Wispr Flow MCP (does not exist yet)

End state of the loop: the Luca asker calls a Wispr Flow MCP that ingests recent log blocks into the per-user dictionary, so the same mishear doesn't recur. The MCP doesn't exist today - Kai is lobbying Wispr Flow's team for one. Conversation started 2026-05-14, ongoing.

Until the MCP exists, the human-in-the-loop fallback is the legacy [agentic-os-kai#492](https://github.com/coilysiren/agentic-os-kai/issues/492) tracking issue: Kai (or the model on her behalf) appends entries in `heard / intended / one-line context` form. The chat-emit block is the source corpus; #492 is the human-curated output destination.

### MCP wiring: mcporter + tooling-mcp-servers

The Luca stack reaches into repo-recall via mcporter. Kai's session-config auto-reaches for the staging variants of all three (`repo-recall-staging`, `luca-staging`, `session-lattice-staging`) without being asked.

- Skill: [`tooling-mcp-servers/SKILL.md`](https://github.com/coilysiren/agentic-os/blob/main/.claude/skills/tooling-mcp-servers/SKILL.md)
- Hard-trigger rule + auto-reach scope landed in [coilysiren/agentic-os#109](https://github.com/coilysiren/agentic-os/issues/109).

## Invariant: corpus hygiene

**Mangle instances flow forward, never backward.** They live only in the chat-emitted log block (which flows into the corpus). They do **not** go into any SKILL.md, AGENTS.md, README.md, GitHub issue body, commit message, or other artifact that gets loaded as context or re-indexed.

Reason: SKILL.md descriptions load into every session's context, so listing mangled tokens there teaches the model to expect the mangles as canonical. repo-recall full-text-indexes those files too, so the mangles would appear as false-positive hits when the Luca asker searches for real voice-mangle events.

This invariant was learned the hard way in-session 2026-05-20:
- [coilysiren/agentic-os-kai#629](https://github.com/coilysiren/agentic-os-kai/issues/629) - scrub mangle examples from `writing-voice-mangle-log` SKILL.md.
- [coilysiren/agentic-os#111](https://github.com/coilysiren/agentic-os/issues/111) - strip mangle variants from `tooling-mcp-servers` triggers.

## Status

Live as of 2026-05-20. Source corpus is being written by every active Claude Code session that triggers the detection rule. Asker side is wired but the synthesis-to-Wispr-Flow step is still manual. Wispr Flow MCP is hypothetical.

## Open questions

- Does Wispr Flow ship an MCP? Lobbying in progress.
- Confidence threshold: currently strict (undercount). Move to loose-with-confidence-tag if dictionary curation volume becomes the bottleneck instead of false-positive risk.
- Cross-session deduplication: who decides when a given (mangled, intended) pair has been "learned" by Wispr Flow and stops appearing? Likely the asker, not the detector.
