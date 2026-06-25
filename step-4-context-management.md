# Step 4 — Context Management

**Goal:** the box is stateless with a *finite* window, and your Step 2/3 loop appends to the
message array on every single turn (user msg, assistant msg, tool_use, tool_result — it grows
fast). Left alone, a long conversation eventually exceeds the window and every request 400s. Step
4 is the harness deciding, each turn, **what to keep and what to drop** so you never cross that
line.

Concepts + tasks. You write it. ~a few days.

---

## 4.0 — Why this is *your* problem, not the API's

Two facts you already own collide here:

1. **Stateless** (Step 0) → you resend the *entire* history every turn.
2. **Finite window** → there's a hard ceiling on how much you can send (`claude-sonnet-4-5`: 1M
   tokens; `claude-haiku-4-5`: 200K).

So `input_tokens` climbs every turn (you watched it grow in Step 0), and the tool loop accelerates
it — a single user question can add an assistant turn + a tool_use + a tool_result + another
assistant turn before you're done. Cross the window → `400`. The API will **not** trim for you.
Your harness is the only thing standing between a long session and a hard crash. That's the whole
step: *you* are the memory manager.

This is the same budget you started tracking in §3.5 — there it was about *cost*; here it's about
*not exceeding the window*. Same number, two reasons to watch it.

---

## 4.1 — The budget: what counts against the window

The window bounds the **input** side: system prompt + every message in the array + your `tools`
definitions, all summed in tokens. Your `max_tokens` (the output) is a *separate* allowance, but
the response still has to fit alongside the input — so your practical ceiling is

```
window  −  max_tokens (room for the reply)  −  a safety margin
```

Two ways to know the number:
- **After the fact:** `usage.input_tokens` on every response tells you exactly what that request
  cost. Cheap, already in your hand.
- **Before the fact:** the `count_tokens` endpoint (from Step 0) lets you measure the array
  *before* sending — useful when you want to trim *before* a request rather than react after one.

Don't estimate with `len(text)/4` or `tiktoken` — wrong tokenizer, wrong number (Step 0). Use the
real count.

---

## 4.2 — The strategies (pick per situation; real harnesses combine them)

**A. Sliding window / truncation.** Keep the most recent N turns, drop the oldest. Dead simple,
zero extra cost, and *lossy* — the model forgets the start of the conversation entirely. Fine for
chat where old turns don't matter; bad when turn 2 set a constraint you still need at turn 40.

**B. Summarization (a.k.a. compaction).** When you near the limit, take the oldest chunk of
history and replace it with a short summary produced by a **cheap model call** (`claude-haiku-4-5`
— "summarize this conversation so far in a paragraph, preserving names, decisions, and open
tasks"). You swap many tokens for few while keeping the gist. Costs one extra call and is itself
lossy (summaries drop detail), but far less lossy than hard truncation.

**C. Hybrid (what production does).** Keep the system prompt always, keep the last few turns
verbatim (recency matters most), and replace the bloated middle with a running summary. Some
designs also "pin" specific facts (the user's name, the task spec) so they survive every trim.

There's no free lunch: **every** strategy loses information. The skill is choosing *what* is safe
to lose for *your* app.

---

## 4.3 — The trap: you can't trim blindly (the tool-loop constraint)

Here's where Step 3's iron rule comes back to bite. The message array isn't a flat list of
interchangeable strings — it has **structural pairing**:

- Every `tool_use` block (in an assistant turn) **must** be answered by a `tool_result` (in the
  next user turn). Drop the assistant turn but keep its `tool_result` — or vice versa — and you've
  orphaned a block → `400`.
- The array **must start with a `user` message.** Naively slicing off the oldest turns can leave
  an `assistant` message first → `400`.
- The system prompt isn't in the `messages` array (it's its own field) — so it's *not* something
  you trim by slicing messages, but it *does* count against the window.

So "drop the oldest 10 messages" is wrong. You drop in **structurally valid units** — a complete
user→assistant(→tool_use→tool_result→assistant) exchange — and you keep the array's invariants
intact. Trimming is a parser-aware operation, not a list slice.

---

## 4.4 — Know the server-side helpers exist (but build manual first)

Anthropic ships beta features — **context editing** / **compaction** — that do versions of 4.2
*server-side* so you don't hand-roll it. They're real and worth using eventually. But build the
manual version first: if you reach for the helper before you understand window accounting and the
structural-pairing trap, you won't know *why* it does what it does, or how to debug it when it
drops something you needed. Same reason you built the tool loop before touching the SDK's tool
runner.

---

## 4.5 — Tasks (build it)

1. **Instrument.** Print `usage.input_tokens` every turn and watch it climb across a multi-turn
   tool conversation. Get a feel for how fast the tool loop inflates it.

2. **Set a budget.** Define a threshold well under your model's window (leave room for
   `max_tokens` + margin). Detect when the *next* request would cross it — using `count_tokens` on
   the array before sending, or projecting from the last `usage`.

3. **Sliding window.** When over budget, drop oldest turns — but **respect §4.3**: never orphan a
   `tool_use`/`tool_result` pair, always leave a `user` message first. Prove a long conversation
   now stays under the window instead of 400-ing.

4. **Summarize instead.** Replace the truncation with a `claude-haiku-4-5` summary call: collapse
   the oldest exchanges into one summary message, splice it in, keep recent turns verbatim.
   Compare what survives vs. plain truncation.

5. **Force the failure first.** Before fixing, *prove the problem exists*: loop a conversation
   long enough to actually exceed the window and watch it 400. Then turn on your manager and watch
   the same conversation survive. (You only understand the fix once you've seen the break.)

---

## 4.6 — Done when you can answer without looking

- Why does `input_tokens` grow every turn, and why does the *tool loop* make it grow faster than
  plain chat?
Because we're sending the entire history with every new message. A tool loop makes it grow faster because it's recursive and a tool might call other tools.
- What exactly counts against the context window on a request?
System prompt + tools + input (which is basically the entire history input + output)
- Why can't you implement trimming as a simple "drop the oldest K messages" slice?
Because older messages might contain context that the user cares about
- Truncation vs. summarization: what does each cost, and what does each lose?
Truncation loses old context which might be important.
Summarization may decide to omit useful information especially in the last few messages which is what the user is currently working on.
A hybrid approach is preffered in most cases. which is basically keep the last n messages and summarize everything before that. this way the things that the user is currently working on stay intact.
- Why build the manual trimmer before using the server-side compaction beta?
So i understand how it works and the edge cases i have to keep in mind when truncating/summarizing

---

## What this sets up
- **Step 5 (MCP)** and **Step 6 (evals)** both run on top of this — an eval suite that drives long
  conversations needs the window managed or it'll crash mid-run.
- **Step 7 (RAG)** is the *other* half of "what's in the context": Step 4 decides what to **drop**
  from history; RAG decides what to **add** from an external store. Together they're the full
  answer to "what does the model see this turn?" — you trim the conversation *and* inject retrieved
  knowledge.
