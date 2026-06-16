# Step 3 — Harden the Loop into a Real State Machine

**Goal:** turn your Step 2 loop from "works on the happy path" into something that can't be
crashed by the model, a bad tool call, or a runaway. This is the step that separates "did a
tutorial" from "can defend it in an interview." The work is pure systems: a transition table and
its failure branches.

Concepts + tasks. You write it. ~week 2.

---

## 3.0 — The reframe: `stop_reason` is a transition table

Stop thinking "loop that sometimes calls tools." Start thinking **state machine**. Each API
response is a state; `stop_reason` is the input that picks the transition; your harness is the
machine that decides the next action. You already know this shape from byte-level parsers — a
`match` on a discriminant driving what happens next.

Right now your loop handles two transitions (`tool_use`, `end_turn`) and falls through everything
else into "re-send identical history and spin until the depth guard." Step 3 is: **every
`stop_reason` gets an explicit, intentional branch.** No silent fall-through.

The full input alphabet:

| `stop_reason` | What happened | The transition your machine must make |
|---|---|---|
| `end_turn` | Model finished | Terminal — return text, await next user input |
| `tool_use` | Wants tool(s) | Run them, append `tool_result`(s), loop |
| `max_tokens` | Hit your output cap mid-generation | You truncated it — continue or bump the cap (§3.3) |
| `refusal` | Safety decline | Surface it; **do not blindly retry** (§3.4) |
| `pause_turn` | A server-side tool hit its own cap | Resend as-is to resume (§3.4) |
| `stop_sequence` | Hit a custom stop string you set | Usually terminal |

If your `match` doesn't have an arm for each, you have a hole.

---

## 3.1 — Two layers of failure, kept separate

A robust harness distinguishes *who* failed. Don't conflate these — they need different handling:

- **The tool failed** (your code threw, network died, file missing). The *request to the model*
  was fine; the *execution* wasn't. → `tool_result` with `is_error: true`, content = the error.
  The model sees it and recovers. You already do this. ✅
- **The model's request was malformed** (asked for a tool that doesn't exist, or `input` that
  doesn't match your schema — wrong type, missing required field). The model produced garbage. →
  also a `tool_result` with `is_error`, but the content is a *validation* message ("unknown tool
  `X`" / "missing required arg `city`"). The model corrects itself next turn.

Both routes feed an error back through the same channel (`tool_result`), but for different
reasons. The point of Step 3 is that **neither one can throw out of your loop** — an exception
escaping `process_tool_use` crashes the program; a fed-back error becomes a conversation the model
can repair.

---

## 3.2 — Validate before you dispatch

Right now your dispatch is `if item["name"] == "get_weather": ...`. Two unhandled holes:

1. **Unknown tool name.** The model hallucinates a tool you never defined → none of your `if`s
   match → you append an *empty* `tool_use_content` or skip it, and the model gets a `tool_result`
   with no answer (or a missing one → 400). Add a final `else`: unknown tool → `is_error`
   result naming the bad tool.
2. **Bad/missing input.** You index `item["input"]["city"]` directly — if the model omits `city`,
   that's a `KeyError` that escapes as an uncaught exception (your `try` catches it, but as a tool
   failure, not a validation message — sloppy). Check the shape *before* you call the real
   function, and feed back a precise validation error if it's wrong.

You don't need a JSON Schema validator library — for 3 tools, a few explicit checks are fine. The
*concept* is what matters: **never pass model-supplied JSON to your real function without checking
it first.** It's untrusted input, exactly like a request body off the wire.

---

## 3.3 — `max_tokens`: you cut it off

`max_tokens` in your request is a hard ceiling on *output*. If the model is mid-sentence when it
hits it, `stop_reason` comes back `max_tokens` and the `content` is **truncated** — incomplete
text, or worse, a half-emitted `tool_use` block.

Your machine must notice this and not treat the partial output as a finished answer. Two valid
responses:
- **Bump and retry / continue** — the answer was legitimately long; raise `max_tokens`.
- **Surface "response truncated"** — at least don't silently present half an answer as complete.

The trap: a truncated `tool_use` is unusable (you can't run a half-specified call). Detect
`max_tokens` *before* you try to process tools.

---

## 3.4 — `refusal` and `pause_turn`: don't paper over them

- **`refusal`** — a safety classifier declined (HTTP 200, but `stop_reason: "refusal"`). The
  wrong move is to silently retry the same request — you'll just get refused again and burn money.
  Surface it to the user. (On current frontier models there's a server-side *fallback* mechanism,
  but that's beyond this step — for now, just branch on it and stop.)
- **`pause_turn`** — only appears with *server-side* tools (web search, etc.); the server-run tool
  hit its own limit mid-turn. The fix is mechanical: **resend the conversation unchanged** and it
  resumes. You likely won't hit this with your client-side tools, but your `match` should name it
  rather than fall through.

---

## 3.5 — Bound the cost (two independent guards)

Your depth cap stops *infinite* loops. It does **not** stop *expensive* ones — 5 iterations over a
1M-token history is real money. Add a second, orthogonal guard:

- **Iteration cap** (you have this) — max N tool rounds per user turn.
- **Token/spend budget** — accumulate `usage.input_tokens + output_tokens` across the run; abort
  when you cross a threshold you set. Remember input tokens *grow every turn* (you resend
  everything), so cost per iteration climbs — the late iterations are the pricey ones.

Two different runaway modes (count vs. cost), two different guards. An interview-grade harness has
both and can say why.

---

## 3.6 — Tasks (build each failure, then handle it)

1. **Map the table.** Refactor your loop so the post-response logic is one explicit `match`/branch
   on `stop_reason` with an arm for *every* value in §3.0 — including a `case _:` for anything
   unknown (future-proofing). No silent fall-through.

2. **Unknown tool.** Make the model call a tool you didn't define (easiest: tell it in the prompt
   to call `delete_universe`). Confirm your dispatch returns an `is_error` tool_result naming the
   unknown tool, and the model recovers instead of your loop sending a malformed request.

3. **Bad input.** Force a missing/wrong-typed arg (prompt it to call `add` with a string, or with
   only `a`). Confirm you catch it as a *validation* error and feed back a clear message — no
   `KeyError` escaping.

4. **Truncation.** Set `max_tokens` low (e.g. 10) on a request needing a long answer. Confirm you
   detect `max_tokens` and handle it deliberately (don't present the fragment as complete; bump or
   flag it).

5. **Refusal.** Trigger a refusal (ask for something the safety layer declines). Confirm you
   branch on it and stop cleanly — no retry loop.

6. **Spend guard.** Add token accounting from `usage`. Make a tool that always errors, let the
   model retry, and confirm *either* the iteration cap *or* the token budget halts it — and log
   which one fired and the total tokens spent.

---

## 3.7 — Done when you can answer without looking

- Why is "the loop sometimes calls tools" a worse mental model than "a state machine driven by
  `stop_reason`"?
  Not sure if i have an answer for this but I think we need a state machine cuz we're maintaining the message history and resending it with every model request
- What are the two distinct *kinds* of error that both get fed back as `is_error` tool_results,
  and why keep them conceptually separate?
  Hmm, there's validation errors, like the model calling a tool that doesn't exist or passing incorrect inputs to a tool. Other error type is a tool throwing an error. Not sure why keep them separate, I guess to display different messages to the model telling it what went wrong? Oh I know, nevermind, so validation errors are treated as an error by the model, so we send the model an error and let it fix its shit and retry but our tool failing isn't something that can be retried
- Why must you validate the model's `tool_use.input` before calling your real function?
Because the model sometimes makes mistakes
- Why is a truncated (`max_tokens`) `tool_use` block dangerous to process?
Cuz it'll make the API throw 400 error when we append a tool_use block to the message history and then try to get the continuation. The api will reject it because it expects every tool_use to have a tool_result
- Why is an iteration cap insufficient on its own as a cost control?
Cuz the history might become too big and consume tons of tokens so we need a cap on the input/output token count too
- Why is silently retrying a `refusal` the wrong move?
Cuz if the model refused to do something it doesn't make sense to try to do the exact same thing again cuz it'll be rejected

---

## What this sets up
- **Step 4 (context management)** plugs into the same loop: now that every turn is accounted for,
  you'll trim/summarize the history this loop keeps growing, using the token counts you started
  tracking in §3.5.
- This hardened loop is the artifact you'll wrap as an **MCP server** (Step 5) and run an **eval
  suite** against (Step 6). Get the state machine clean here — everything downstream rides on it.
