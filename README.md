# work-handoff

> Hand work off between models and platforms without losing what was already verified.

An agent skill for **relay handoff**. When a context window fills up, or you switch from Claude to Codex to DeepSeek, or move from CLI to a web chat, the next agent starts blind. This skill makes it start informed instead.

Two modes, chosen from what the user says:

- **Take over** — you just arrived: find the handoff doc, verify the baseline, report status, then continue.
- **Hand off** — you're leaving: update the doc in place and generate a paste-ready relay prompt.

## The one idea

A handoff document is written for the **next executor**, not for the user. It answers exactly three questions:

1. What has already been done?
2. What was concluded — including what was ruled out?
3. What happens next?

Anything else is commentary.

## Take-over mode

### Find the document first

Never assume a filename. Priority order:

1. A path the user gave you.
2. `WORK_HANDOFF*.md`, `HANDOFF*.md`, `*交接*.md`, `*handoff*.md` in the working directory and `docs/`.
3. Links from `AGENTS.md` / `CLAUDE.md` / `README.md`.

```bash
python3 scripts/find_handoff.py .
```

If several match, take the most recently modified one that actually contains "current state / next step / verified". If none exists, say so — **do not invent a status** — and offer to create one from the template.

### Read in order, not end to end

Read the handoff doc in full, but four sections verbatim: **verified facts, measured data, TODO (P0/P1/P2), no-go zones**. Read design docs only for sections relevant to the next step. Read runbooks only when executing the step they describe.

| Document | Role | How to read |
| --- | --- | --- |
| Handoff doc | Starting point: state, facts, TODO | Full |
| Design doc | Rationale: why, constraints | On demand, relevant sections |
| Runbook | Actions: exact commands | Step by step, during execution |

### Verify the baseline, don't re-investigate facts

Run the doc's "first thing on take-over" checklist and report real output: does `git log -1` match the recorded baseline, do tests build and pass, are the artifacts that "should not exist" really absent, do key `grep`s still hold.

The **verified-facts table is a contract**: a conclusion with `file:line`, URL and date is taken as given. Re-check only when the baseline commit moved, a file was moved or rewritten, or your own observation contradicts it. On contradiction: stop and report. Don't guess and patch.

### Report before acting

A take-over report of ten lines or fewer:

```
Baseline: <commit> (matches / does not match the doc)
Checks:   <actual test / build / check results>
State:    <one sentence>
Trusting: <verified facts carried over, a few>
Next:     <one action + acceptance criterion>
Risk:     <or "none">
```

If the next step is already specified, do it right after the report. If it spends money, sends messages, modifies data, deletes files or publishes anything, confirm first.

## Hand-off mode

Trigger it when context is near the limit, when switching models (Claude ↔ GPT/Codex ↔ DeepSeek/GLM), when switching platforms (CLI ↔ desktop ↔ web ↔ IDE plugin), or when a phase ends.

Update the doc **in place** — never create `HANDOFF_V2.md`. Minimum updates: date header, work round (request → action → conclusion → correction, failures included), verified facts with locations, measured data with method and limits, TODO with acceptance criteria, current state, document map, no-go zones.

Then generate the relay prompt for the next platform, and note which documents must travel with it:

```
You are taking over. Working directory: <abs path>. Baseline: <commit>.
Read first: <handoff doc> (full), then <design doc> sections <...> as needed.

Rules:
1. Do not re-investigate conclusions in the verified-facts table.
2. Do not extrapolate measured data; estimates are not measurements.
3. Do not touch anything in "no-go zones"; do not re-propose rejected options.
4. Give me a take-over report of ten lines or fewer before acting.

Next goal: <one sentence>.
Acceptance: <observable result>.
```

Cross-machine handoff also carries `git status` and branch state, untracked artifacts, external state (purchased resources, accounts, open orders), running processes and ports, the last key command and its output, and the **location** of local secrets — path only, never the value.

Platform differences are tabulated in `SKILL.md`: same-machine agents get a path plus a commit; web chats get the documents pasted plus explicit "please run this and paste the output" instructions; same machine with a swapped provider should trust the doc, not the previous chat.

### Audit before you leave

```bash
python3 scripts/handoff_audit.py <handoff-doc>
```

Then the human checklist: current state updated today, exactly one next action with acceptance criteria, every P0 has a concrete action, new facts have locations, measurements have methods and limits, dead ends recorded, no-go zones complete, no secrets.

Final question: **could the next model finish the next step from this document alone, without the chat history?** If not, keep writing.

## Requirements

Python 3.8+. No third-party packages. The skill stores no project state and is bound to no project name — state always lives in the project's own handoff document.

## Install

```bash
git clone https://github.com/jeremylinnnnn/work-handoff.git \
  ~/.workbuddy-ai/skills/work-handoff
```

For Claude Code, clone into `~/.claude/skills/work-handoff` instead.

## Layout

```
SKILL.md                        entry point, both modes, anti-patterns
references/handoff-template.md  document skeleton
scripts/find_handoff.py         locate the handoff doc
scripts/handoff_audit.py        structural audit
```

## Anti-patterns this skill exists to prevent

| Anti-pattern | Consequence |
| --- | --- |
| "90% done" with no acceptance criteria | Next agent doesn't know what's left |
| Conclusions without `file:line` or URL | Cannot tell if stale, must re-investigate |
| Chat summary passed off as a handoff | Decisions, rejections and evidence lost |
| `HANDOFF_V2.md` instead of an update | Two sources of truth, guaranteed divergence |
| "Keep optimizing" as a TODO | Not actionable |
| Making the next agent re-verify verified facts | Wasted context, possibly different conclusions |
| Estimates written as measurements | Decisions built on fake data |
| "Today / yesterday" instead of absolute dates | Meaningless tomorrow |
| Tokens or account IDs in the doc | Leak |
| Failures not recorded | Next agent walks the same dead end |

## License

MIT — see [LICENSE](LICENSE).
