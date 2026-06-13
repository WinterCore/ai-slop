# Becoming an AI Agent Developer — Master Plan

> Mental model that makes all of this tractable for a systems person:
> **The LLM is a black-box coprocessor you send work to over HTTP. You never open it.**
> The "math" (transformers, attention, training) is inside the box and you skip it entirely.
> Everything that makes an "agent" is the systems work *around* the box: a wire protocol,
> a loop, a state machine, a dispatch table, a context buffer. That part is 100% your wheelhouse.

Two facts about the box explain ~80% of everything below. Burn them in:

1. **It's stateless.** There is no server-side memory. Every turn you resend the *entire*
   conversation. The API is a pure function: `(all_messages) -> next_message`.
2. **Its output is sampled, not computed.** The box emits a probability distribution over the
   next token; something picks one. So output is non-deterministic — which is why you test
   with **evals** (pass-rate %), not `assert ==`.

---

## How to use this repo

- This file = the map. Check things off as you go.
- One working doc per step (e.g. `step-0-wire-protocol.md`). Each is hands-on: run the
  commands, do the exercises, answer the self-check questions before moving on.
- Resource discipline: build, don't watch. Anthropic's **Messages API reference** + **tool-use
  docs** are your only "course." Tutorials push you into frameworks that hide the exact
  mechanism you're trying to learn.

## Current-reality cheat sheet (2026 — don't trust older blog posts)

- **Default model:** `claude-opus-4-8`. Cheap/fast for high-volume + eval grading:
  `claude-haiku-4-5`. Balanced: `claude-sonnet-4-6`.
- **You don't set `temperature` anymore.** On current frontier models `temperature`/`top_p`/`top_k`
  are removed (sending them = HTTP 400). The knobs now are `effort` (`low`→`max`) and
  `thinking: {type:"adaptive"}`. The "output is sampled" point still holds — the lever just
  moved.
- **Embeddings are a different vendor.** Anthropic has no embeddings endpoint; the Messages
  API is generation only. Use **Voyage AI** (Anthropic's recommended provider) for text→vectors
  in RAG.
- **API billing ≠ Claude Max.** Raw API calls (your own key from console.anthropic.com) are
  billed per-token and are *separate* from a Max subscription. Verify what any "credit" covers
  before assuming the API tab is free. Steps 0–6 cost a few dollars total to learn by hand.

---

## The Steps

### Step 0 — See the actual wire protocol  ·  ~1 day  ·  `step-0-wire-protocol.md`
Don't touch an SDK. `curl` the Messages API by hand so you internalize what a model call *is*:
an HTTP POST, JSON in, JSON out. Prove statelessness to yourself. See tokens. Watch streaming
arrive as SSE.
- [ ] Send a basic request, read every field of the response JSON
- [ ] Prove the model is stateless (forget vs. remember experiment)
- [ ] Stream a response and read the raw SSE event sequence
- [ ] Count tokens with `/v1/messages/count_tokens`; read the `usage` block
- **Done when:** you can explain why there's no session ID, what you resend each turn, and what
  `stop_reason` tells your code to do next.

### Step 1 — Why output is non-deterministic  ·  ~0.5 day  ·  no math
The box outputs a distribution over the next token; sampling picks one; it's appended and fed
back in; repeat. That loop is **autoregression**. You do *not* need to know how the distribution
is computed (that's the transformer math — skip it). You only need: **output is sampled, not
deterministic.** That single fact is the root of non-determinism, "hallucination," and why
Step 6 (evals) exists instead of unit tests.
- [ ] Send the *same* prompt 5×, observe variation
- [ ] Write one paragraph in your own words: sampling → autoregression → why evals not equality
- **Done when:** you can say why two identical requests can return different text.

### Step 2 — Hand-build the tool-call loop, no framework  ·  3–5 days  ·  the core
This is the heart of agents and it's pure systems work. Mechanism:
1. In the request you include a list of **tools** — each just a `name` + JSON Schema of its args.
2. The model can reply with a structured `tool_use` block (`call read_file with {path: ...}`)
   instead of text. **It cannot execute anything — it only emits JSON.**
3. Your harness parses that, runs the real function, appends the result as a `tool_result`
   message, and calls the API again.
4. Loop until the model returns plain text (`stop_reason == "end_turn"`).

Build it with 2–3 real tools (`read_file`, `list_dir`, `run_command`), ~150 lines of TS.
No LangChain — frameworks hide the exact mechanism you're learning.
- [ ] Define tools as JSON Schema; send them
- [ ] Detect `stop_reason == "tool_use"`, dispatch to the real function
- [ ] Append `tool_result`, loop, terminate on `end_turn`
- Note: the official SDK has a "tool runner" that hides this loop. Build the manual version
  first so you understand what it's hiding.
- **Done when:** the model asks to read a file, your harness reads it, feeds it back, and the
  model answers using the contents — all in your own loop.

### Step 3 — Harden the loop into a real state machine  ·  week 2
This is what separates "did a tutorial" from "can talk about it in an interview." The
`stop_reason` field is your state machine's transition table. Handle the failure modes:
- [ ] Model emits malformed/invalid tool JSON → validate, feed the error back as a `tool_result`
- [ ] Tool throws → catch, return the error as a tool result (with `is_error: true`), let it recover
- [ ] Infinite loop (model keeps calling tools) → max-iteration cap
- [ ] `stop_reason == "max_tokens"` → you truncated; bump the limit / handle continuation
- [ ] `stop_reason == "refusal"` → safety decline; handle, don't blindly retry
- [ ] `stop_reason == "pause_turn"` → server-side tool hit its cap; resend to continue
- [ ] Runaway cost → token/spend budget per run
- **Done when:** every `stop_reason` has an explicit branch and bad tool JSON can't crash you.

### Step 4 — Context management  ·  a few days
Because the box is stateless with a finite window, *your harness* decides what to keep each turn.
Learn the manual version first: a buffer you trim or summarize (with a cheap model call) as it
grows. Then know the server-side helpers exist (`compaction`, `context editing` betas) — and
you'll actually understand *why* they exist.
- [ ] Track token count of your message buffer
- [ ] Trim oldest turns when near the window; OR summarize them with a `claude-haiku-4-5` call
- **Done when:** a long conversation stays under the context window without crashing, by your code's decision.

### Step 5 — Wrap your tools as an MCP server  ·  portfolio piece
MCP is to tools what a syscall ABI is to the kernel: a stable interface (JSON-RPC over
stdio/SSE) so *any* client can call *any* tool server with no custom wiring. Expose your Step 2
tools as an MCP server, point Claude Code at it, watch it work. Concrete, demonstrable.
- [ ] Implement an MCP server exposing `read_file`/`list_dir`/`run_command`
- [ ] Register it with a client (Claude Code) and drive your tools through it
- **Done when:** a client you didn't write can call tools you did, over MCP.

### Step 6 — Evals  ·  the most underrated interview signal
Output is sampled (Step 1) so you can't unit-test with equality. So: collect ~30–50 input cases
with known-good answers, run your agent over them, score each (exact match, rule check, or have
a *second* model grade it — use `claude-haiku-4-5` for the grader), track pass-rate across
prompt/model versions. It's a test suite scored in percentages. Almost no one's portfolio has this.
- [ ] Build a 30–50 case eval set with expected outputs
- [ ] Score programmatically; print a pass-rate %
- [ ] Add an "LLM-as-judge" grader for the fuzzy cases
- **Done when:** you can change a prompt and see the pass-rate move.

### Step 7 — RAG, only when a project needs it
Stripped of mystique: an **embedding model** is another black-box API call — text in, array of
floats out (ignore how it's computed; and note it's a *different vendor* — Voyage AI). Store the
vectors; at query time, embed the question and find the nearest stored vectors. "Nearest" =
cosine similarity, one line the DB runs for you. Stuff the matched chunks into the prompt. It's a
search index + prompt-stuffing step, nothing more. Use **pgvector** since you know Postgres.
- [ ] Chunk + embed a corpus (Voyage), store vectors in pgvector
- [ ] Embed a query, retrieve top-k by cosine similarity
- [ ] Stuff retrieved chunks into the Claude prompt, answer with citations
- **Done when:** the agent answers a question it could only know from your retrieved chunks.

---

## What to explicitly skip
Transformers, attention, backprop, gradient descent, training, fine-tuning internals, tokenizer
training. Know the name + one-sentence "what it does" for each so you're not caught flat —
**never implement them.** None of it is tested for agent / full-stack-AI roles.

## Interview soundbites you'll have *earned* by doing this
- "The model's stateless, so I resend context each turn and manage the window myself."
- "Tool calls are structured outputs my harness dispatches — the model never executes anything."
- "Output's sampled, so I validate with evals, not equality assertions."
- "I exposed my tools over MCP so any client can use them."
- "Client-side tools run in my harness; server-side tools run on Anthropic's infra — I know the difference."

## Timeline
Steps 0–5: very doable in 2–3 weeks. Steps 6–7: ~1 more week. Start applying + building a
portfolio project in parallel after Step 5 — by then you've built an "agent runtime from scratch,"
which is the project.
