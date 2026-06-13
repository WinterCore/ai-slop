# Step 0 — See the Actual Wire Protocol

**Goal:** stop thinking of "the AI" as magic and see it for what it is on the wire — an HTTP
endpoint that takes JSON and returns JSON. By the end you'll have proven, by hand, that the model
is a **stateless pure function**, and seen exactly what your future harness sends and parses.

Raw HTTP from **Python, no SDK**. This doc is concepts + tasks — *you* write the code. ~1 day.

---

## 0.0 — Setup

- Get an API key from **console.anthropic.com** (Settings → API Keys). Pay-per-token, *separate*
  from any Claude.ai / Max subscription.
- Put it in your environment (`export ANTHROPIC_API_KEY=...`) and read it from Python — don't
  hardcode it in a file.
- You'll parse responses with `json.loads`. The body is structured data, not text — don't reach
  for regex.
- Use a cheap model while experimenting: `claude-haiku-4-5`.

---

## 0.1 — The pure-function model

The whole API is one endpoint: `POST https://api.anthropic.com/v1/messages`.

In types you already know:

```
messages: Message[]   ──►   POST /v1/messages   ──►   Message
```

It is **referentially transparent**: no hidden server state. There is no `session_id`, no
"conversation" object on Anthropic's servers. The server forgets you the instant it responds. To
make the model "remember" turn 1 at turn 2, *you* resend turn 1. That's the entire trick — and
it's why your harness's main job is **owning the message array.**

---

## 0.2 — Anatomy of a request

The body is a JSON object. The fields that matter:

| Field | What it is |
|---|---|
| `model` | Which box. `claude-haiku-4-5` while learning. |
| `max_tokens` | Hard ceiling on the **output** length, in tokens. Hit it → cut off mid-sentence (`stop_reason: "max_tokens"`). A cap, not a target. |
| `messages` | The **entire** conversation so far, oldest first. The stateful part — *you* own it. |
| `messages[].role` | `"user"` or `"assistant"`. First message must be `user`. |
| `messages[].content` | A string, **or** an array of typed content blocks (you'll need the array form once images/tool results appear). |

Three headers: `x-api-key` (auth), `anthropic-version: 2023-06-01` (pins the API contract, like an
ABI version), `content-type: application/json`. That's the whole request — **notice there's no
session header.** Its absence is the point.

---

## 0.3 — Anatomy of a response

You get back something shaped like:

```json
{
  "id": "msg_...",
  "type": "message",
  "role": "assistant",
  "model": "...",
  "content": [
    { "type": "text", "text": "..." }
  ],
  "stop_reason": "end_turn",
  "stop_sequence": null,
  "usage": { "input_tokens": 17, "output_tokens": 28 }
}
```

Two fields drive your entire future harness:

### `content` is an array of **tagged blocks** (a sum type)
It's `content[]`, not a string, because one response can interleave kinds of output. Today it's
one `{type:"text"}` block; later the same array might hold a `{type:"thinking"}` block then a
`{type:"tool_use"}` block. Your code switches on `block["type"]` — like matching a Rust enum.
**Never** assume `content[0]` is text; check the type first.

### `stop_reason` is the **discriminant that drives your loop**
The most important field for Step 2/3 — it tells your harness why the box stopped, so it knows
what to do next:

| `stop_reason` | Meaning | What your harness does |
|---|---|---|
| `end_turn` | Finished naturally | Done — show text, await user |
| `tool_use` | Wants to call a tool | Run it, append `tool_result`, loop (Step 2) |
| `max_tokens` | Hit your output cap | Raise `max_tokens` or continue |
| `refusal` | Declined for safety | Surface it; don't blindly retry |
| `pause_turn` | Server-side tool hit its cap | Resend to resume |
| `stop_sequence` | Hit a custom stop string | Usually done |

`usage`: `input_tokens` (what you sent — grows every turn because you resend history) +
`output_tokens` (what it generated). You pay for both; output is ~5× input price.

---

## 0.4 — Prove statelessness to yourself (the key experiment)

Make three calls and watch what happens.

**Call 1 — set a fact:** send one message —
`user: "My name is Winter. Remember it."`

**Call 2 — ask WITHOUT resending history:** send only —
`user: "What is my name?"`
→ It has **no idea.** No server-side memory of call 1 existed. This is the whole lesson.

**Call 3 — ask WITH history rebuilt by you:** send three messages —
`user: "My name is Winter..."`, `assistant: "Got it, Winter."`, `user: "What is my name?"`
→ Now it knows. Nothing changed on the server — *you* carried the state forward by rebuilding the
array, including the assistant's own prior reply. That rebuild-the-array move is the spine of
every agent you'll write.

---

## 0.5 — Tokens (the box's unit of account)

Text is chopped into integers from a fixed vocabulary (a lookup table — not math you need). That's
why there's a context limit and why you pay per token. Tokenization is **model-specific** — do
**not** use OpenAI's `tiktoken` (wrong tokenizer, undercounts Claude). Ask Anthropic via the
`POST /v1/messages/count_tokens` endpoint instead.

Your Step 4 context-management code will lean on this endpoint to know when to trim history.

---

## 0.6 — Streaming is just SSE

You've done WebSocket streaming; this is simpler and one-directional — a single long-lived HTTP
response with `Content-Type: text/event-stream`, framed records separated by blank lines. Add
`"stream": true` to the body.

The frames look like this (this is the shape you'll reassemble in code):

```
event: message_start
data: {"type":"message_start","message":{...}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Packets"}}

event: content_block_stop
data: {"type":"content_block_stop","index":0}

event: message_delta
data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":17}}

event: message_stop
data: {"type":"message_stop"}
```

Read it as a frame protocol:
- `message_start` → metadata for the whole message
- `content_block_start` / `_delta` / `_stop` → one block built incrementally; `index` says *which*
  block (a message can stream several)
- `message_delta` → carries the final `stop_reason` + output token count
- `message_stop` → end of stream

To rebuild the reply, concatenate the `text_delta`s per `index`. In Python: send `stream:true`,
then iterate the response object line by line (it yields as data arrives), keep the `data:` lines,
`json.loads` each, and act on the event `type`.

---

## 0.7 — Tasks (do these, don't just read)

1. Send a basic request; print the whole response and find every field in §0.3.
2. Run the **0.4 statelessness experiment.** Confirm call 2 fails and call 3 works. Sit with *why*.
3. Set `max_tokens` to `5` on a request that needs a long answer. Confirm `stop_reason` comes back
   `"max_tokens"` and the text is cut off. (A real Step-3 failure mode.)
4. Handle a non-200: send a bad request (e.g. an invalid model id) and print the error body +
   status instead of crashing.
5. Stream a longer response. Print tokens as they arrive. Find the `stop_reason` in the
   `message_delta` event.
6. Hit `count_tokens` on (a) one English sentence, (b) the same length of source code. Compare.

---

## 0.8 — You're done with Step 0 when you can answer these without looking

- Why is there no session ID in the request or response?
Cuz the thing is stateless, you have to pass in the entire chat history on every request unless you decide to use token caching which i haven't learned about yet
- Exactly what must you resend on turn N to keep continuity?
Every message from 0 to N-1. basically the entire message history
- Why is `content` an array, and how should code read it?
Cuz content has multiple types and the response may contain more than one content type
- For `end_turn`, `tool_use`, `max_tokens`, `refusal` — what does your harness do next in each?
1. end_turn basically means that the model finished responding, i need to send the next prompt role: user
2. tool_use model wants to execute a tool, which means i need to execute it for it and pass the result back
3. max_tokens model hit max tokens in the response which is min(request.max_tokens, model response tokens)
4. refusal model refused to respond due to safety measures
- Why can't you parse the response body with a regex?
what kind of question is this? the response is a json. i don't understand
- Why does `usage.input_tokens` grow every turn in a long conversation?
cuz we're passing all the history as input 

---

## What this sets up
- **Step 1** is just noticing the `content` text is *sampled* — send the same prompt a few times,
  watch it vary.
- **Step 2** is this exact request/response loop, plus a `tools` array in the request and one new
  branch on `stop_reason == "tool_use"`. You'll already have the whole skeleton in your head.
