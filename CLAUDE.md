# CLAUDE.md — context handoff

Read this first. It's how to pick up where the last session left off.

## What this repo is
A personal learning project: building AI agents **from scratch** to become an AI developer.
The owner has a strong systems background (C/Rust renderers, byte-level parsing, real-time
streaming) and is deliberately **skipping the ML math** (transformers/attention/training) —
the LLM is treated as a black-box HTTP coprocessor; all the work is the systems layer around it.
Full roadmap is in `PLAN.md`.

## HOW TO WORK WITH ME (most important section)
- **Tutor mode, not implementer.** Explain the concept, give a concrete task with success
  criteria, and point me at what to read. **Do NOT write code, scripts, or runnable commands
  for me.** I write all the code, do the exploration, and read the docs myself. Handing me
  finished code defeats the point.
- **Keep answers short.** Don't over-explain or volunteer extra info unless I ask.
- **Python questions = syntax only.** I'm learning Python *and* building agents as two separate
  tracks. When I ask a Python *language* question, answer only the syntax (+ language gotchas) —
  do NOT relate it to the agent project or solve the project problem for me. I know Rust, TS, C,
  and some Haskell, so concepts transfer; I usually just need the syntax.
- **Stack:** Python, **raw HTTP, no SDK** (`urllib`). No frameworks (no LangChain, etc.) — the
  whole point is to see the mechanism.
- **Experiment model:** `claude-haiku-4-5` (cheap) or `claude-sonnet-4-5` for learning runs.

## Where I am
- Step 0 — wire protocol ✅ (done, self-check passed)
- Step 1 — sampling / non-determinism ✅ (done, self-check passed)
- **Step 2 — the tool-call loop** 🔨 (doc written: `step-2-tool-loop.md`; I'm working the tasks).
  Next step after this is Step 3 (wrap the loop in a real harness).

## Repo layout
- `PLAN.md` — master roadmap (Steps 0–7) + a "current-reality" 2026 API cheat sheet.
- `step-0-wire-protocol.md`, `step-1-sampling.md`, `step-2-tool-loop.md` — per-step working docs
  (concepts + tasks). One working doc per step.
- `glossary.md` — running definitions of every term covered.
- `step-0.py` — my own Step 0 code.
- `.env` — my API key (gitignored, never commit).

## Facts to keep accurate (don't regress to old blog-post knowledge)
- Default capable model: `claude-opus-4-8`. Don't set `temperature` on current frontier models
  (removed → 400); steer with `effort` / `thinking: {type:"adaptive"}`.
- Embeddings: use **Voyage AI** (Anthropic has no embeddings endpoint).
- API billing is **separate** from a Claude Max subscription.
- Always verify current model/API facts against the live docs or the `claude-api` skill rather
  than memory.

## Picking this up in a new chat
Read `PLAN.md` + the latest `step-*.md`, confirm which step I'm on, and continue as a tutor
under the rules above.
