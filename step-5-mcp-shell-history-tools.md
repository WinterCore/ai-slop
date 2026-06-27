# Step 5 Project — Shell-History MCP Server (tool specs)

The protocol concepts live in `step-5-mcp.md`. This file is just the **tool surface** for the
project: 5 read-only tools over `~/.zsh_history`, exposed via your hand-rolled MCP server. You
write the code — these are the specs + success criteria.

**Whole-project done criterion:** Claude Code (a client you didn't write) discovers these 5 tools
via `tools/list` and successfully calls them via `tools/call` against your real history.

---

## Shared concerns (read once, applies to all 5)

- **All read-only.** Nothing here writes or executes. That's a deliberate, safe scope — no
  destructive ops, no confirmation gating needed. Say so in an interview.
- **The history format.** With `EXTENDED_HISTORY` on, each line is `: <unix-ts>:<elapsed>;<command>`
  (e.g. `: 1718900000:5;sleep 5`). Without it, each line is just the raw command. Your parser must
  handle **both** — strip the `: ts:elapsed;` prefix when present, fall back to the whole line when
  not. Tools that need the timestamp (#4) or elapsed (bonus) only work when extended history is on
  — detect that and return a clear "extended history not enabled" message instead of guessing.
- **Multi-line commands.** zsh escapes embedded newlines in history with a trailing `\`. Decide how
  you handle them (join, or treat naively) — just be consistent and don't crash.
- **Logging → stderr only.** stdout is the JSON-RPC channel. A `print()` to stdout corrupts the
  stream (Step 5 §5.1).
- **Schemas via Pydantic.** Each tool's `inputSchema` comes from a Pydantic model's
  `model_json_schema()`, same as Step 4. Validate `arguments` with `model_validate` — wire input,
  still untrusted (Step 3).
- **Output.** Return results as an MCP `content` array — typically one `{"type":"text","text":...}`
  block. Format the matched commands readably (one per line is fine).

---

## Tool 1 — `search_history`

**What:** find past commands matching a query, most-recent first.

**Description (the model reads this — write it to sell the tool):** *"Search the user's shell
command history for past commands containing a query string. Use when the user is trying to recall
or reconstruct a command they ran before (e.g. 'what was that ffmpeg command')."*

**Input:** `SearchHistory(query: str, limit: int = 20, regex: bool = False)`
- `query` — substring to match (or a regex if `regex` is true).
- `limit` — max results.
- `regex` — treat `query` as a regular expression.

**Output:** the matching command lines, newest first, capped at `limit`.

**Done when:** searching for a command you know you've run returns it; an obscure query returns an
empty (not erroring) result.

---

## Tool 2 — `recent_commands`

**What:** the last N commands you ran.

**Description:** *"Return the most recent shell commands the user ran, newest first. Use for 'what
was I just doing' or to get immediate context on the user's recent activity."*

**Input:** `RecentCommands(count: int = 20)`

**Output:** the last `count` commands, newest first.

**Done when:** it matches the tail of your actual history; `count` larger than your history size
returns everything without crashing.

---

## Tool 3 — `most_used`

**What:** frequency ranking — which commands you run most.

**Description:** *"Return the user's most frequently used shell commands with their run counts,
ranked high to low. Use to summarize the user's habits or find their common workflows."*

**Input:** `MostUsed(limit: int = 20, starts_with: str | None = None)`
- `starts_with` — optional filter, e.g. `"git"` to rank only git subcommands.

**Output:** command + count pairs, ranked. (Design decision for *you*: do you count the full command
line, or just the first token / `git push` vs `git push origin main`? Pick one and note why — this
is a real tool-design judgment call.)

**Done when:** the ranking looks plausible against your real usage; `starts_with="git"` narrows it.

---

## Tool 4 — `commands_since`

**What:** commands run after a given time. **Requires `EXTENDED_HISTORY`** (needs the timestamp).

**Description:** *"List shell commands the user ran since a given date or time, newest first. Use
for 'what have I run today' or 'what was I working on this morning'."*

**Input:** `CommandsSince(since: str, limit: int = 50)`
- `since` — a date/time the model passes (decide your accepted format — ISO date, or natural like
  "today"; simpler is fine, document it in the description).

**Output:** commands with timestamps after `since`, newest first.

**Done when:** it returns today's commands for `since="<today's date>"`; and when extended history
is **off**, it returns a clear "timestamps unavailable" message rather than wrong data.

---

## Tool 5 — `history_stats`

**What:** an aggregate summary of the whole history.

**Description:** *"Return summary statistics about the user's shell history: total command count,
number of unique commands, and the date range covered. Use for a high-level overview of the user's
activity."*

**Input:** `HistoryStats()` (no arguments — an empty object schema).

**Output:** total commands, unique commands, and (if extended history is on) earliest/latest
timestamps.

**Done when:** the numbers reconcile with `wc -l ~/.zsh_history` and your own spot-checks.

---

## Bonus (optional 6th) — `slowest_commands`

Uses the `elapsed` field you asked about: rank commands by run duration. `SlowestCommands(limit: int
= 20)`. Requires extended history. Fun, demonstrates you can use every field in the format. Skip if
you want to stay at 5.

---

## Suggested build order

1. **Parser first, standalone.** Before any MCP: write the function that turns `~/.zsh_history` into
   a list of `(timestamp, elapsed, command)`. Test it on your real file. Everything else is queries
   over this list. (This is the "app integration," and it's the only file-format work in the whole
   project.)
2. **Protocol skeleton** (Step 5 §5.6 tasks 1–2): stdio loop + `initialize` handshake.
3. **`tools/list`** returning all 5 schemas.
4. **`tools/call`** dispatching to the 5 query functions over your parsed list.
5. **Register with Claude Code** and drive it.

Get the parser solid in step 1 and the 5 tools are each a few lines of list-filtering on top.

---

## Self-check (done when you can answer)

- Why is a read-only tool surface a safe design choice here, and how would the picture change if you
  added a `delete_history_entry` tool?
- How does each tool's `inputSchema` get produced, and where does the untrusted-input validation
  happen?
- Which two tools degrade when `EXTENDED_HISTORY` is off, and how do you handle that without lying
  to the model?
- Why does the parser come before the protocol in the build order?
