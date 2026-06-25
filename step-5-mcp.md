# Step 5 — Wrap Your Tools as an MCP Server

**Goal:** take the tools you already built (Steps 2–4) and expose them over **MCP** — a standard
protocol — so a client you *didn't* write (Claude Code) can discover and call them. Nothing about
the tools changes; you're putting a standard socket on the front of them. This is the portfolio
piece: "I exposed my tools over MCP, and a third-party client drove them."

Concepts + tasks. You write the server. Raw JSON-RPC over stdio, no MCP SDK — same ethos as the
rest. ~portfolio-piece sized.

---

## 5.0 — The one-line mental model

MCP (Model Context Protocol) is to tools what a **syscall ABI is to the kernel**, or what
**LSP is to editors**: a stable, documented interface so *any* client can talk to *any* server
without bespoke wiring. Before MCP, every app that wanted your `get_weather` tool had to integrate
your code directly. With MCP, you run a **server** that speaks the protocol; any MCP **client**
(Claude Code, an IDE, someone else's agent) connects and uses your tools — zero custom glue on
their side.

Key reframe from Step 2: there, *your harness* owned both the model loop **and** the tools. MCP
**splits those apart.** The client owns the model loop; you own only the tool server. You're no
longer writing the agent — you're writing the thing the agent plugs into.

```
Step 2:   [ your harness: model loop + tool dispatch ]

Step 5:   [ Claude Code: model loop ]  ⟷ MCP ⟷  [ your server: tool dispatch ]
                (client)                              (server, what you build)
```

---

## 5.1 — It's JSON-RPC 2.0 over a transport

Two layers, both already in your wheelhouse:

**The message format is JSON-RPC 2.0** — a tiny, fixed envelope you've effectively already seen:
- **Request:** `{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{...}}`
- **Response:** `{"jsonrpc":"2.0","id":1,"result":{...}}` (the `id` echoes the request's `id`)
- **Error:** `{"jsonrpc":"2.0","id":1,"error":{"code":-32601,"message":"..."}}`
- **Notification:** a request with **no `id`** — fire-and-forget, no response expected.

You match responses to requests by `id`. (Sound familiar? It's the same wire-matching discipline
as `tool_use_id` in Step 2.)

**The transport is how bytes move.** Two standard ones today:
- **stdio** (what you'll use) — the client launches your server as a **subprocess** and talks to
  it over **stdin/stdout**. Messages are newline-delimited JSON (one JSON object per line). Local,
  zero networking, dead simple. This is your byte-stream/framing wheelhouse.
- **Streamable HTTP** — the remote transport (a single HTTP endpoint, server can stream responses
  back). This *replaced* the older "HTTP+SSE" two-endpoint transport you may see in stale blog
  posts. You don't need it for this step; know it exists for remote servers.

> ⚠️ **The stdio footgun, internalize it now:** on stdio, **stdout is exclusively for protocol
> messages.** A stray `print()` for debugging corrupts the JSON-RPC stream and the client chokes.
> All logging goes to **stderr**. (This is exactly why your Step 3 habit of printing to stdout has
> to change here.)

---

## 5.2 — The lifecycle: a handshake, then work

Every MCP connection opens with a negotiation, same shape as a TCP/TLS handshake:

1. **Client → `initialize`** (a request): "here's the protocol version I speak and what I support."
2. **Server → result:** "here's my protocol version and my **capabilities**" — e.g. "I have
   tools." This is where you advertise that you're a tools server.
3. **Client → `notifications/initialized`** (a notification, no `id`): "handshake done, go."
4. Then normal request/response traffic begins.

You branch on the incoming `method` exactly like you branched on `stop_reason` in Step 3 — it's
the same state-machine-on-a-discriminant shape. Methods you must handle for a tools server:

| `method` | What the client wants | Your response |
|---|---|---|
| `initialize` | Open the connection | Your capabilities + protocol version |
| `notifications/initialized` | Handshake ack | Nothing (it's a notification) |
| `tools/list` | "What tools do you have?" | Array of tool defs (name, description, **inputSchema**) |
| `tools/call` | "Run tool X with these args" | The tool's result as content |

---

## 5.3 — `tools/list`: you already have this

This is where Steps 2–4 pay off. A tool definition over MCP is the *same three things* as in the
Messages API, just renamed slightly:

- `name`
- `description`
- `inputSchema` — JSON Schema (note the camelCase; the Messages API called it `input_schema`).

Your Pydantic models already produce this via `model_json_schema()`. So `tools/list` is: walk your
tool classes, emit `{name, description, inputSchema}` for each. The `TOOLS` list you built in
Step 4 is 90% of the answer — you're reshaping the same data into the MCP envelope.

---

## 5.4 — `tools/call`: your dispatch, wrapped

`tools/call` params look like `{"name": "WeatherTool", "arguments": {"city": "Cairo"}}`. This is
**exactly** your Step 2/3 dispatch: look up the tool by name, validate `arguments` (Pydantic
`model_validate` — your untrusted-input guard from Step 3 still applies; the args came over the
wire from a client you don't control), run it, return the output.

The result shape is an MCP `content` array (a tagged-block list — same idea as the Messages API's
`content`): typically `{"content": [{"type": "text", "text": "<your tool output>"}]}`. On failure,
there's an `isError` flag — your `is_error` instinct from Step 2 carries over conceptually.

So `tools/call` is a thin adapter: MCP request shape in → your existing validate-and-execute →
MCP result shape out. The tool *logic* is untouched.

---

## 5.5 — Connecting Claude Code (the demo)

The payoff: register your server with a client you didn't write and watch it work. Claude Code
connects to a local stdio server via its MCP config — you tell it the **command** to launch your
server (e.g. `python /path/to/your_mcp_server.py`) and it spawns it as a subprocess and handshakes.

The registration is done with the `claude mcp add` command (stdio is the default transport for a
local command). Verify the exact current invocation against Claude Code's own docs or the
`claude-code-guide` — don't trust my memory of the flag names. Once registered, you ask Claude
Code something that needs your tool, and it calls *your* server over MCP.

> Verify the current MCP **protocol version string** and the exact `initialize` result shape
> against the spec at **modelcontextprotocol.io** before you code — the version is a dated string
> that bumps over time, and the client may reject a mismatch. The *structure* (JSON-RPC, the
> methods above) is stable; the version literal is the thing that drifts.

---

## 5.6 — Tasks (build the server)

1. **Echo the protocol.** Write the stdio read loop: read a line from stdin, parse JSON, print the
   parsed method to **stderr** (not stdout), loop. Confirm you can see messages arriving. (Test it
   by piping a hand-written `initialize` JSON line into your script.)

2. **Handshake.** Respond to `initialize` with your capabilities + protocol version, and handle the
   `notifications/initialized` notification (do nothing, but don't crash on the missing `id`).

3. **`tools/list`.** Return your Step 4 tools reshaped as `{name, description, inputSchema}`. Reuse
   `model_json_schema()`.

4. **`tools/call`.** Wire it to your existing dispatch: look up by `name`, `model_validate` the
   `arguments`, execute, return the result as an MCP `content` array. Keep the Step 3 validation
   guard — these args are untrusted wire input.

5. **Drive it from Claude Code.** Register the server with `claude mcp add`, then ask Claude Code
   something that forces a tool call. Watch it discover (`tools/list`) and invoke (`tools/call`)
   your tools. That's the done criterion.

6. **(Optional) Break it on purpose.** Add a `print()` to stdout mid-session and watch the stream
   corruption. Then move it to stderr and watch it recover. Burn in the stdout rule.

---

## 5.7 — Done when you can answer without looking

- What problem does MCP solve that your Step 2 harness didn't — i.e. what does "any client can call
  any server" buy you?
- In MCP terms, who owns the model loop and who owns the tools — and how is that different from
  Step 2?
- What's the message format, and how does a response get matched to its request?
- Why must *nothing* but protocol messages go to stdout on the stdio transport?
- Walk the lifecycle: what are the first three messages on any connection?
- How does an MCP tool definition map to the tool definition you already wrote for the Messages
  API?

---

## What this sets up
- This is the **portfolio artifact** — "my tools, exposed over MCP, driven by a client I didn't
  write." Concrete and demonstrable in an interview.
- **Step 6 (evals)** can run against either your Step 2–4 harness or this server — you now have a
  clean tool boundary to test through.
- Conceptually closes the loop on the whole roadmap: Step 2 showed the model can't execute
  anything (your harness does); MCP shows that "your harness" can be *anyone's* harness, as long as
  you both speak the protocol.
