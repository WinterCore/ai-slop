# Glossary — AI Agent Dev

Running list of terms. Step number in parens = where it gets used in depth.

| Term | Definition |
|---|---|
| **Token** | A sub-word chunk of text (the model's unit). ~¾ of a word in English. Punctuation/spaces can be their own tokens. |
| **Tokenization** | Splitting text into tokens via a fixed vocabulary lookup. Model-specific (don't use OpenAI's `tiktoken` for Claude). |
| **Context window** | Max tokens you can *send* in one request (system + history + your message). Opus 4.8 = 1M, Haiku 4.5 = 200K. |
| **max_tokens** | Cap on how many tokens the model can *generate* in one response. A ceiling, not a target. |
| **Statelessness** | The API keeps no memory between calls. You resend the full conversation every turn. |
| **Role** | Who "said" a message: `user` (input to model), `assistant` (model's output), `system` (operator instructions, highest authority). |
| **Content block** | One typed piece of a response. `content` is an array of them (`text`, `thinking`, `tool_use`, …). Switch on `type`; never assume `content[0]` is text. |
| **stop_reason** | Why generation stopped: `end_turn`, `max_tokens`, `tool_use`, `refusal`, `stop_sequence`, `pause_turn`. Drives your harness's next action. |
| **Stop token** | A special vocab token meaning "end of turn." When the model samples it → `end_turn`. |
| **Sampling** | Picking the next token by a weighted dice roll from the probability distribution (not always the top one). The source of randomness. |
| **Temperature** | Knob that flattens (high) or sharpens (low/0) the distribution before sampling. Low = near-deterministic. Removed on current frontier models (Opus 4.8 / Fable 5); still settable on Haiku/Sonnet 4.5. |
| **Autoregression** | The generation loop: produce a token → append → produce the next conditioned on all prior → repeat. |
| **Hallucination** | Model sampling a plausible-but-wrong token. Reducible (grounding/retrieval, allowing "I don't know", citations, verification pass), never fully fixable. |
| **Eval** | A scored test suite: many input cases + expected answers + a scoring function → a pass-rate %. Used to compare prompt/model versions. (Step 6) |
| **LLM-as-judge** | Using a second (cheap) model to score fuzzy outputs (e.g. "does this summary mention X? yes/no"). |
| **Pass-rate** | The aggregate eval score (e.g. 47/50 = 94%). What you track across versions — not a binary pass/fail, because output is probabilistic. |
| **Prefill** | Putting words in the assistant's mouth by ending `messages` on an `assistant` turn — the model continues it. 400s on current frontier models. |
| **Prompt caching** | Marking a stable prompt prefix so reusing it next request is ~0.1× the price. Doesn't replace resending — optimizes it. |
| **Streaming / SSE** | One long-lived HTTP response (`text/event-stream`) that pushes tokens as framed `event:`/`data:` records. One-directional (server→client). |
| **Tool use** | Model emits a `tool_use` JSON block (it can't execute anything); your harness runs the function and feeds back a `tool_result`. (Step 2) |
| **tool_result** | The message your harness sends back carrying a tool's output (with `is_error: true` on failure). |
| **Context management** | Your harness trimming/summarizing history to stay under the context window. (Step 4) |
| **Compaction / context editing** | Server-side helpers (beta) that summarize/prune history for you. Learn the manual version first. (Step 4) |
| **MCP** | Model Context Protocol — a stable interface (JSON-RPC over stdio/SSE) so any client can call any tool server without custom wiring. (Step 5) |
| **RAG** | Retrieval-Augmented Generation: fetch relevant chunks from your data, stuff them into the prompt so the model answers from them. (Step 7) |
| **Embedding** | Text → array of floats (a vector) from a model. Similar text → nearby vectors. Use Voyage AI (Anthropic has no embeddings endpoint). |
| **Vector DB** | Stores embeddings and finds the nearest ones fast (e.g. pgvector). |
| **Cosine similarity** | The "nearness" measure between two vectors. The DB computes it for you — the only math in RAG. |
| **effort** | Current-model knob (`low`→`max`) controlling how hard the model thinks/works. Replaced fixed thinking budgets. |
| **Adaptive thinking** | `thinking: {type:"adaptive"}` — model decides how much to reason per request. The current thinking mode. |
| **Client-side vs server-side tools** | Client-side tools run in *your* harness (model emits JSON, you execute). Server-side tools (web search, code execution) run on Anthropic's infra. |
