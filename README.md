# voice-flow-learning-loop

Reference index for Kai's dictation meta-improvement work targeting Wispr Flow. Originally scoped to one loop (vocabulary mishears feeding the dictionary). After a ten-round empirical test of Wispr Flow's failure modes plus a read of [Wispr Flow's docs](https://docs.wisprflow.ai/), the project now spans three distinct interventions, only two of which are learning loops, and only one of which still requires Wispr Flow to ship something new.

Generic-purpose pieces live in this repo as their canonical home. Kai-specific glue (the collaboration rule that loads it into every session, the asker stack that synthesizes downstream) stays in private sibling repos and is described here abstractly.

## The three interventions

### Loop 1: vocabulary mangles → dictionary feed

Kai dictates into Claude Code constantly via Wispr Flow. When the dictation pipeline mishears acoustically (a CLI name lands as an English word, a proper noun gets phonetically swapped, a known token returns as a homophone), the next turn in chat already has the correction baked in. That makes every voice mishear a self-labeled training pair, no human annotation needed.

The loop captures those pairs as structured corpus signal, indexes them locally, and routes them toward [Wispr Flow's per-user dictionary](https://docs.wisprflow.ai/articles/4052411709-teach-flow-your-words-with-the-dictionary) so the same mishear doesn't recur. The sink is currently a manual curation step; the goal is for it to land as an MCP call against Wispr Flow directly.

```
dictation  ->  chat correction  ->  structured log block  ->  repo-recall index
                                                                     |
                                            ( asker, private )       v
                                                                     |
                                            Wispr Flow dictionary  <-+
                                            ( currently manual; MCP lobbied for )
```

**Scope of what this loop fixes:** acoustic mishears of proper nouns, casing losses on known titles, single-phoneme acronym swaps, compound-internal word substitutions where the dictionary can teach the canonical tokenization. The ten-round empirical test catalogued about seven of nineteen observed failure modes in this category.

**Scope of what this loop does NOT fix:** code-mode hallucinations (where Wispr Flow generates plausible-but-wrong shell commands from acoustic fragments), context-attractor substitutions (where the topic biases the parser toward domain-adjacent words the user didn't say), and pure invention (where the parser fabricates words to fill acoustic gaps). These are model-behavior categories, not vocabulary gaps; no dictionary entry addresses them.

### Loop 2: repeated phrases → Snippets

[Wispr Flow Snippets](https://wisprflow.ai/features) are user-configurable voice triggers that expand into pre-written text. The user dictates a short trigger phrase; Wispr Flow emits the long pre-defined expansion. The mechanism is exact-text substitution, which means it sidesteps the dictation accuracy problem entirely for the snippet-ized phrases.

The corpus already contains the signal needed to feed this loop. Claude Code session JSONL files include every dispatched command, every SSM parameter path, every issue-template opener, every long invocation Kai dictates repeatedly. A learning loop that detects repeat phrases above a frequency threshold and proposes Snippets for them turns repetition into shortcuts.

```
session JSONL  ->  repo-recall full-text index  ->  asker (repeat-phrase frequency)
                                                                     |
                                                                     v
                                                        Snippets file proposals
                                                                     |
                                                                     v
                                                       Kai picks which to import
```

**Scope of what this loop addresses:** any phrase Kai dictates more than N times that has a stable target expansion. CLI commands with long flag combinations. SSM parameter paths. Issue-body openers. Common code-mode targets that today hallucinate into the wrong command (because the snippet expansion is exact text, the hallucination category is sidestepped per-snippet).

**Behavioral cost:** Kai has to learn and use the new trigger phrases. This is opt-in per snippet. She doesn't change how she talks generally; she chooses which long phrases to shortcut and learns those specific triggers. The asker can propose, but only Kai's adoption activates the value.

**Why this loop is more compelling than Loop 1 in some ways:**

- The Wispr Flow surface already exists. No MCP is needed (though one would help with automated import); a Snippets file can be written and loaded today.
- The corpus signal is structurally cleaner. Repetition detection from session JSONL is mechanical; no false-positive risk from "did this token mangle or is it idiosyncratic-but-correct".
- Sidesteps the catastrophic failure categories from Loop 1's scope.

**Why Loop 1 still matters:** Loop 2 addresses repeated phrases, not new ones. The first time Kai dictates a CLI name in a sentence, no snippet exists yet. Loop 1's vocabulary feed is still needed for the long tail of one-off mentions.

### Intervention 3: Auto Cleanup off in technical contexts (settings, not a loop)

[Wispr Flow's Smart Formatting / Auto Cleanup](https://docs.wisprflow.ai/articles/5373093536-how-do-i-use-smart-formatting-and-backtrack) is the feature responsible for the most catastrophic failure modes in the ten-round test: code-mode shell-command hallucination, automatic bullet-list reformatting that ate trailing words, title-attractor reinterpretation that collapsed entire clauses, sentence-splitting that changed prepositional logic. It is togglable on Mac, Windows, and iOS via the Auto Cleanup tab (still rolling out on some platforms).

There is no learning loop here. The intervention is a settings change: turn Auto Cleanup off when dictating into terminals or code editors. The Wispr Flow ask is to support *per-app* Auto Cleanup so Kai doesn't have to toggle globally — off in iTerm/Warp, on in Slack/messages.

This intervention closes roughly seven of the nineteen failure modes from the test without any corpus signal at all.

## Pieces

### Signal source: the structured log block (Loop 1)

Emitted at the top of any chat turn where the model detects a voice mishear and corrects it. Format is exact:

```
- voice mangling
- Input speech: <verbatim mangled text from the user's input>
- Output correction: <what they meant>
```

One block per detected mishear. The leading `- voice mangling` phrase is the anchor that full-text indexing pins on.

### Signal source: repeat-phrase detection (Loop 2)

No structured chat block needed. The asker walks session JSONL directly, counts phrase frequencies, and proposes candidates above a threshold. Boilerplate text (e.g., the standard Issue body opener) is detected the same way as repeated CLI invocations.

### Detection rule: `writing-voice-mangle-log` (Loop 1 only)

Thin skill carrying the format spec and the trigger surface. Lives in this repo as the canonical home.

- Skill: [`.claude/skills/writing-voice-mangle-log/SKILL.md`](.claude/skills/writing-voice-mangle-log/SKILL.md)

Strict mode by default: only emit when both the mishear and the intended target are high-confidence.

### Recovery rule (private)

The unconditional rule that loads Loop 1's format into every Claude Code session lives in `kai-collaboration`, a generic-purpose meta-collaboration skill in the private agentic-os-kai sibling repo.

- Pointer: [`docs/recovery-rule-stub.md`](docs/recovery-rule-stub.md)

### Corpus indexer: repo-recall

Local-only Rust + axum + MCP daemon that scans on-disk repos, sessions, and commits and serves them via JSON and MCP. Both loops consume from here.

- Repo: [coilysiren/repo-recall](https://github.com/coilysiren/repo-recall)
- MCP surface: `recall_search` for Loop 1's structured-block queries; full session JSONL for Loop 2's repeat-phrase analysis.

### Asker: private

Natural-language consumer over repo-recall data. Source stays private; capability described here.

### Sink targets

- **Loop 1** sinks into [Wispr Flow's dictionary](https://docs.wisprflow.ai/articles/4052411709-teach-flow-your-words-with-the-dictionary), currently via manual curation, eventually via a Wispr Flow MCP that doesn't exist yet but is being lobbied for.
- **Loop 2** sinks into [Wispr Flow Snippets](https://wisprflow.ai/features), which already supports user-configurable triggers. A programmatic import path (file or MCP) would unlock the loop fully; manual entry from agent proposals works today.
- **Intervention 3** sinks into the Auto Cleanup tab in Wispr Flow's settings. No corpus, no automation.

### MCP wiring: mcporter + tooling-mcp-servers

Both loops reach into repo-recall via mcporter. Kai's session-config auto-reaches for the staging variants of the asker stack without being asked.

- Skill: [`tooling-mcp-servers/SKILL.md`](https://github.com/coilysiren/agentic-os/blob/main/.claude/skills/tooling-mcp-servers/SKILL.md) in coilysiren/agentic-os.

## Invariant: corpus hygiene

**Mangle instances flow forward, never backward.** They live only in the chat-emitted log block (which flows into the corpus). They do **not** go into any SKILL.md, AGENTS.md, README.md, GitHub issue body, commit message, or other artifact that gets loaded as context or re-indexed.

Reason: SKILL.md descriptions load into every session's context, so listing mangled tokens there teaches the model to expect the mangles as canonical. repo-recall full-text-indexes those files too, so the mangles would appear as false-positive hits when the asker searches for real voice-mangle events.

This invariant was learned the hard way in-session 2026-05-20 across two scrub commits (private agentic-os-kai and public coilysiren/agentic-os).

## Status

Live as of 2026-05-20.

- **Loop 1:** detection and corpus indexing live. Synthesis-to-Wispr-Flow step is manual.
- **Loop 2:** corpus signal already present in session JSONL; asker side not yet built. The lowest-friction next step is a one-off frequency analysis to seed the first batch of Snippets proposals.
- **Intervention 3:** confirmed available in Wispr Flow today; Kai needs to toggle Auto Cleanup off for technical contexts.

The ten-round empirical test that motivated the three-way split is captured in repo-recall's session corpus.

## Open questions

- Does Wispr Flow ship an MCP? Lobbying in progress.
- For Loop 2: what frequency threshold makes a phrase Snippet-worthy? Probably tunable downstream; the asker can present candidates with frequency counts and let Kai pick.
- For Loop 2: what trigger-phrase generation strategy works best? Short literal abbreviations? User-chosen mnemonics? Asker-proposed candidates?
- For Intervention 3: does Wispr Flow's Auto Cleanup expose per-app behavior, or only global? Per-app would close the catastrophic-hallucination category without requiring Kai to toggle on every context switch.
- Cross-session deduplication for Loop 1: who decides when a given (mangled, intended) pair has been "learned" by Wispr Flow and stops appearing? Likely the asker, not the detector.

## The reshaped Tanay conversation

Originally framed as "let our agent feed your dictionary" — a single big ask. The empirical test plus the docs read reshaped it into three smaller, sharper asks:

1. **Per-app Auto Cleanup** (off in terminal/code apps, on in messaging). Closes the catastrophic-hallucination category without needing any learning loop at all.
2. **Snippets API or import format** so an agent can write Snippets files programmatically. Loop 2's high-leverage sink.
3. **Dev-products list extension** — Wispr Flow already auto-recognizes "Supabase, Cloudflare, Vercel". Open this internal list to per-user additions. Smaller, sharper version of the original dictionary ask.
