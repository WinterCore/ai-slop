# Step 2 — The Tool-Call Loop

**Goal:** build the thing that makes an "agent" an agent — a loop where the model asks your code
to run a function, you run it, you feed the result back, and it continues. This is the entire
mechanism. Everything later (MCP, multi-step agents) is this loop with more tools bolted on.

Concepts + tasks. You write the harness. Raw HTTP, no SDK. ~1–2 days.

---

## 2.0 — The one thing to internalize first

**The model cannot execute anything.** It has no shell, no network, no Python. When you give it
tools, all it can do is emit a JSON block that *says* "I want to call `get_weather` with
`{city: "Cairo"}`." It then **stops and waits.** Running that function is *your* job. You run it,
hand the output back, and the model resumes with that output in its context.

So a "tool" is really a contract:
- **You → model:** here are the functions you may request, by name + schema.
- **Model → you:** "call this one, with these args" (it can't, so it asks).
- **You → model:** "here's what it returned."

The model is still the same stateless pure function from Step 0. Tool use doesn't change that —
you're just appending more turns to the array and resending, exactly like before. The *only* new
thing is one new `stop_reason` branch.

---

## 2.1 — The request side: declaring tools

You add one field to the request body: `tools`, an array. Each tool is three things:

| Field | What it is |
|---|---|
| `name` | The function's identifier, e.g. `get_weather`. How the model refers to it. |
| `description` | Plain-English explanation of *what it does and when to use it*. The model picks tools off this — treat it as the prompt that sells the tool. Vague description → wrong/missing calls. |
| `input_schema` | A **JSON Schema** object describing the arguments (types, which are required). This is the contract the model fills in. |

`input_schema` is just JSON Schema — `{"type": "object", "properties": {...}, "required": [...]}`.
You already know shapes like this from TypeScript types; this is the runtime-validatable version.

Optional but worth knowing now:
- **`tool_choice`** — steer whether/which tool fires. `{"type":"auto"}` (default — model decides),
  `{"type":"any"}` (must call *some* tool), `{"type":"tool","name":"x"}` (force this one). Useful
  in Step 6 evals to force a deterministic path.

---

## 2.2 — The response side: the `tool_use` block

When the model wants a tool, two things happen together:

1. `stop_reason` comes back **`"tool_use"`** (your new branch).
2. The `content` array contains a `tool_use` block:

```json
{
  "type": "tool_use",
  "id": "toolu_01A...",
  "name": "get_weather",
  "input": { "city": "Cairo" }
}
```

Note the `content` array can hold a `text` block *and* a `tool_use` block in the same response
(the model "thinking out loud" then calling). This is exactly why Step 0 hammered "never assume
`content[0]` is text — switch on `type`." Now it bites.

That `id` (`toolu_...`) matters: it's how you match your result back to *this* request. Hold onto
it.

---

## 2.3 — Feeding the result back (the part everyone gets wrong)

To continue, you append **two** messages to your array, then resend the whole thing:

1. **The assistant's turn, verbatim** — the entire `content` array you just got back (text block
   + tool_use block). You echo the model's own move back into the history. Skip this and the next
   call has a `tool_result` referencing a `tool_use` the model can't see → 400.

2. **A new `user` turn carrying the result** — its `content` is an array with a `tool_result`
   block:

```json
{
  "type": "tool_result",
  "tool_use_id": "toolu_01A...",
  "content": "18°C, clear"
}
```

`tool_use_id` must equal the `id` from §2.2 — that's the wire matching the request to its answer.
On failure, add `"is_error": true` and put the error message in `content`; the model will see it
and can recover (retry, apologize, try another tool) instead of crashing your program.

Then `POST` again. The model now has the tool output in context and either calls another tool
(`stop_reason: "tool_use"` again) or answers the user (`end_turn`).

---

## 2.4 — The loop

That's the whole agent:

```
send request (messages + tools)
loop:
  get response
  append assistant message to history
  if stop_reason == "tool_use":
      for each tool_use block:
          run the real function
          build a tool_result block (is_error on failure)
      append one user message containing all the tool_result blocks
      send again        ← resend full history, like always
  else (end_turn):
      done — show text to user, break
```

Two subtleties:

- **Parallel tool calls.** One response can contain *several* `tool_use` blocks at once. Run them
  all, and return **all** their `tool_result` blocks in **one** user message. Don't send one
  message per result.
- **Termination.** The loop ends when `stop_reason` is `end_turn`, not on a fixed count. But put a
  **max-iterations guard** in anyway — a buggy tool (always erroring) can make the model loop
  forever. A real failure mode; cap it.

---

## 2.5 — Why this is the spine of every agent

Strip away the words "agent," "ReAct," "function calling," "MCP" — underneath, all of it is this
loop. The model proposes actions; your code is the hands that perform them and the eyes that
report back. The model's "agency" is entirely on loan from the tools *you* expose. An agent with
no tools is just a chatbot; an agent's power is exactly the union of its tools.

Step 5 (MCP) is just a standardized way to *source* the tool list and *route* the execution over
a protocol instead of hardcoding functions. Same loop. Step 4 (context management) exists because
this loop grows the message array fast (every call + every result is appended), so you'll need to
trim it. Keep both in mind; don't build them yet.

---

## 2.6 — Tasks (build, don't just read)

1. **One tool, one round-trip.** Define a single tool — e.g. `get_weather(city)` that returns a
   hardcoded fake string. Ask "What's the weather in Cairo?". Confirm you get
   `stop_reason: "tool_use"`, pull out the `name`/`input`/`id`, and print them. Don't loop yet —
   just see the call.

2. **Close the loop.** Now append the assistant message + a `tool_result`, resend, and confirm the
   model produces a natural-language `end_turn` answer using your fake data. This is the core
   milestone — once this works, you have an agent.

3. **Make the tool real.** Replace the fake with an actual function — a calculator
   (`add(a, b)`), or read a local file, or hit some no-auth public JSON API. Watch the model do
   something it genuinely couldn't do alone.

4. **Multi-step.** Give it *two* tools and ask a question that needs both in sequence (e.g.
   `get_user_city(name)` then `get_weather(city)`). Confirm your loop fires twice before
   `end_turn`. This proves your loop generalizes past one round.

5. **Error path.** Make your tool raise/return an error and send it back with `is_error: true`.
   Watch the model react instead of your program dying. Then add the max-iterations guard and
   prove it stops a runaway.

6. **(Optional) Parallel calls.** Ask something that needs the same tool for two cities at once.
   See if you get two `tool_use` blocks in one response; return both results in one user message.

---

## 2.7 — Done when you can answer without looking

- What are the three parts of a tool definition, and which one does the model use to *decide* to
  call it?
name: used to refer to the tool when the model wants to call it
description: used by the model for the decision
input_schema: as the name implies, the input schema of the tool (number of args, types, etc)
- When `stop_reason` is `tool_use`, what exactly must you append to `messages` before the next
  request — and why does omitting the assistant turn break it?
I need to append the tool_use request by the assistant, not sure why though, i guess cuz it doesn't make sense for a tool result to be in the history without the request to use it
- What links a `tool_result` to the specific call it answers?
tool_use_id
- What makes the loop terminate? What stops it from looping forever?
a depth that i keep track of
- "The model executed the function." — what's wrong with that sentence?
The model doesn't execute the function, the model requests to use a tool (a function) but my code is what executes it.

---

## What this sets up
- **Step 3** wraps this loop in a real harness (system prompt, conversation management, the
  user-facing turn).
- **Step 4** trims the message array this loop keeps growing.
- **Step 5 (MCP)** swaps your hardcoded `tools` array + dispatch for a protocol — same loop,
  pluggable tools.
