# Recovery rule stub

This is a pointer, not an extract.

The recovery side of the loop (continue the conversation seamlessly when the dictation pipeline mishears; emit the structured log block at the top of the same turn so the corpus signal lands) is wired into every Claude Code session by a single rule in Kai's private `kai-collaboration` skill, which lives in the agentic-os-kai sibling repo.

`kai-collaboration` is a generic-purpose meta-collaboration skill (elevate-effort gating, self-care echo rules, manual-issue handoff format, and so on). The dictation-mangle recovery is one section within it. The skill stays private as a whole because most of its content is unrelated to this loop; the relevant rule is named here just so the loop is legible from this public-only vantage.

For the *format* of what gets emitted when the recovery rule fires, see [`writing-voice-mangle-log`](../.agents/skills/writing-voice-mangle-log/SKILL.md) in this repo. That part is public and canonical here.
