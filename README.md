# voice-flow-learning-loop

Reference index for Kai's dictation meta-improvement loop. Generic-purpose pieces live in this repo as their canonical home; Kai-specific glue (the collaboration rule that loads it into every session, the asker stack that synthesizes downstream) stays in private sibling repos and is described here abstractly.

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

Thin skill carrying the format spec and the trigger surface. Lives in this repo as the canonical home.

- Skill: [`.claude/skills/writing-voice-mangle-log/SKILL.md`](.claude/skills/writing-voice-mangle-log/SKILL.md)

Strict mode by default: only emit when both the mishear and the intended target are high-confidence. False-positive entries poison the dictionary signal.

### Recovery rule (private)

The unconditional rule that loads the format into every Claude Code session lives in `kai-collaboration`, a generic-purpose meta-collaboration skill in the private agentic-os-kai sibling repo. The dictation-mangle recovery is one section within it. The skill stays private as a whole because most of its content is unrelated to this loop; only the relevant rule is named here.

- Pointer: [`docs/recovery-rule-stub.md`](docs/recovery-rule-stub.md)

### Corpus indexer: repo-recall

Local-only Rust + axum + MCP daemon that scans on-disk repos, sessions, and commits and serves them via JSON and MCP (`recall_search`, `recall_dashboard`, `recall_session`, etc.). The structured log block lands in Claude Code session JSONL files and gets full-text-indexed on the next scan.

- Repo: [coilysiren/repo-recall](https://github.com/coilysiren/repo-recall)
- MCP surface: `recall_search` is the entry point. The asker stack consumes from here.

### Asker: private

Natural-language consumer over repo-recall data. Routes questions to a dispatch table and returns focused answers. The asker for this loop pulls recent log blocks and surfaces them as candidate dictionary entries. Source stays private; capability described here.

### Sink target: Wispr Flow MCP (does not exist yet)

End state of the loop: the asker calls a Wispr Flow MCP that ingests recent log blocks into the per-user dictionary, so the same mishear doesn't recur. The MCP doesn't exist today; Kai is lobbying Wispr Flow's team for one.

Until the MCP exists, the human-in-the-loop fallback is manual curation: Kai (or the model on her behalf) appends entries in a `heard / intended / one-line context` form to a private tracking issue. The chat-emit block is the source corpus; the manual queue is the human-curated output destination.

### MCP wiring: mcporter + tooling-mcp-servers

The asker reaches into repo-recall via mcporter. Kai's session-config auto-reaches for the staging variants of the asker stack without being asked.

- Skill: [`tooling-mcp-servers/SKILL.md`](https://github.com/coilysiren/agentic-os/blob/main/.claude/skills/tooling-mcp-servers/SKILL.md) in coilysiren/agentic-os.

## Invariant: corpus hygiene

**Mangle instances flow forward, never backward.** They live only in the chat-emitted log block (which flows into the corpus). They do **not** go into any SKILL.md, AGENTS.md, README.md, GitHub issue body, commit message, or other artifact that gets loaded as context or re-indexed.

Reason: SKILL.md descriptions load into every session's context, so listing mangled tokens there teaches the model to expect the mangles as canonical. repo-recall full-text-indexes those files too, so the mangles would appear as false-positive hits when the asker searches for real voice-mangle events.

This invariant was learned the hard way in-session 2026-05-20 across two scrub commits (private agentic-os-kai and public coilysiren/agentic-os).

## Status

Live as of 2026-05-20. Source corpus is being written by every active Claude Code session that triggers the detection rule. Asker side is wired but the synthesis-to-Wispr-Flow step is still manual. Wispr Flow MCP is hypothetical.

## Open questions

- Does Wispr Flow ship an MCP? Lobbying in progress.
- Confidence threshold: currently strict (undercount). Move to loose-with-confidence-tag if dictionary curation volume becomes the bottleneck instead of false-positive risk.
- Cross-session deduplication: who decides when a given (mangled, intended) pair has been "learned" by Wispr Flow and stops appearing? Likely the asker, not the detector.
