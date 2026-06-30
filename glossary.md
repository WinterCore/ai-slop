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
| **Eval set / dataset** | The collection of cases you score against (golden data). ~30–50 `{input, expected}` rows. Data, not code — grow it without touching harness logic. (Step 6) |
| **Case / sample** | One `{input, expected}` unit of an eval set. (Step 6) |
| **Ground truth / golden / reference** | The known-correct answer for a case — what you grade against. Must be hand-verified; a wrong one silently inverts the score. (Step 6) |
| **Label / class / category** | The expected answer in a classification task (e.g. `spam`/`promotions`/`personal`). (Step 6) |
| **Prediction / actual** | What the model returned, vs. the expected. Conventionally `y_pred` vs `y_true`. (Step 6) |
| **Unit under test** | The thing being scored — prompt + model + harness — as one black box. Start single-shot so eval flakiness ≠ agent flakiness. (Step 6) |
| **Runner** | The loop that feeds each input through the system and collects outputs. (Step 6) |
| **Grader / scorer** | Maps `(output, expected) → pass/fail` (or 0–1). Reach for the cheapest grader that can actually judge the case. (Step 6) |
| **Deterministic grader** | Rule-based scoring: exact match, regex, valid-JSON, number-within-tolerance. Free, 100% repeatable. (Step 6) |
| **Exact match** | Output equals expected verbatim. The simplest grader. (Step 6) |
| **Rubric** | The explicit criteria handed to an LLM-judge so its verdict is repeatable (not a vibe). (Step 6) |
| **Verdict** | The judge's structured result, e.g. `{pass, reason}` — parse it, read *why* it failed. (Step 6) |
| **Aggregate** | Collapsing per-case results into one number (the pass-rate). (Step 6) |
| **Per-category breakdown** | Pass-rate grouped by true label — shows *where* failures land, not just that they happened. (Step 6) |
| **Confusion matrix** | Counts of (true label × predicted label). Diagonal = correct; off-diagonal shows the *direction* of each mistake. (Step 6) |
| **Accuracy** | Overall fraction correct (= pass-rate, for classification). (Step 6) |
| **Precision** | Of the items predicted class X, how many were actually X. (Step 6) |
| **Recall** | Of the items actually class X, how many you caught. (Step 6) |
| **F1** | Harmonic mean of precision and recall. (Step 6) |
| **Class imbalance** | Unequal per-category counts that skew the aggregate — a model can ace the majority class, tank a rare one, and still score high. (Step 6) |
| **Baseline** | The reference score new runs are compared against. (Step 6) |
| **Regression** | A drop in score vs. baseline. Every production bug becomes a new case so it's regression-tested forever. (Step 6) |
| **Offline eval** | Fixed dataset run on demand (what you build this step). (Step 6) |
| **Online eval** | Scoring live production traffic — no pre-written expected; graded by proxy signals (retries, thumbs, a judge on a sample). (Step 6) |
| **Zero-shot / few-shot** | No examples / some examples included in the prompt. Holding few-shot back lets you later add it and watch the pass-rate move. (Step 6) |
| **Coverage / distribution** | How well your cases span real inputs; an all-softball set reports a meaningless 100%. (Step 6) |
| **Edge case / happy path** | Hard/unusual vs. easy/typical inputs. (Step 6) |
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

---

## 🪼 The Buzzword Petting Zoo — words to nod at solemnly in meetings while dying inside

Terms that are mostly marketing for things you've already built, plus the model/training jargon you skip the math on. Learn them only so you know what the thought-leader across the table is *actually* describing. Hype-flag included.

### "Agentic" everything
- **Agentic AI / agentic workflow** — LLM picks its next action in a loop instead of running a fixed script. *This is your Step 2–3 loop.* ~90% marketing.
- **Agent vs. workflow** — the one principled cut: **workflow** = predefined code paths; **agent** = model directs its own steps/tools. (Anthropic's distinction; worth keeping.)
- **ReAct (Reason + Act)** — named pattern for "think → act → observe → repeat." The academic label for your tool loop.
- **Multi-agent / orchestration** — several agents (planner, researcher, critic) run by an orchestrator. Real sometimes, oversold usually.
- **Subagent** — an agent another agent spawns to handle a sub-task in its own context.
- **Human-in-the-loop (HITL)** — a human approves/edits before the agent acts. Actually real.
- **Computer use / browser use** — model driving a GUI/browser via click & keystroke tool calls.

### Context words (your Step 4, rebranded)
- **Context engineering** — the agent-era rebrand of "prompt engineering": deciding what goes in the window. *Literally what Step 4 was.* Currently the trendiest term in the field.
- **Context rot / "lost in the middle"** — models degrade on info buried mid-context. Real, measured — the *why* behind compaction.
- **Memory (short/long-term)** — state that outlives one request (a file or vector store the agent reads back).

### Prompting / technique
- **Chain-of-thought (CoT)** — reason step-by-step before answering. Now baked into "reasoning models."
- **Guardrails** — validation/safety constraints around the model. Your Pydantic validation is one.
- **Grounding** — anchoring answers to provided data vs. model memory (RAG is a grounding technique).
- **Structured outputs / JSON mode** — forcing schema-shaped output. Your Step 3 instinct.
- **Prompt injection / jailbreak** — the security attacks: untrusted context hijacks instructions / bypasses safety. *Interviewers ask — know these.*

### Training & model jargon (know the name, skip the math)
- **Foundation / frontier / base model** — big pretrained model; "frontier" = current top tier.
- **Fine-tuning** — extra training on your data to specialize a model.
- **RLHF** — Reinforcement Learning from Human Feedback; how raw models become helpful/safe. The famous acronym.
- **Pre- vs post-training** — learn language from the internet vs. the later alignment/instruction phase.
- **Distillation** — train a small model to mimic a big one (how you get cheap/fast Haiku-tier models).
- **Quantization** — shrink weight precision to run cheaper/faster.
- **MoE (Mixture of Experts)** — only part of the model fires per token. Know the name, not the internals.
- **Reasoning model / test-time compute / inference-time scaling** — "think longer at answer time" for hard problems. Your `effort`/adaptive-thinking knobs.
- **SLM** — small language model; the cheap/on-device counterpart to LLM.

### Quality / safety
- **Benchmark** — standardized public test (MMLU, SWE-bench, GPQA). Different from *your* task-specific evals.
- **Red teaming** — adversarially attacking the model to surface failures.
- **Alignment** — making model behavior match human intent. Big umbrella word.

### Ops / infra
- **Inference** — running the model for output (vs. training); "inference cost" = per-call price.
- **LLMOps** — DevOps for LLM apps (deploy, monitor, eval, version prompts).
- **Latency / TTFT / throughput / TPS** — speed words: time-to-first-token, tokens-per-second, total volume.

### RAG vocabulary (Step 7 preview)
- **Chunking** — splitting docs into retrievable pieces.
- **Semantic search** — search by meaning (embeddings) vs. keywords.
- **Reranking** — a second model re-sorts retrieved chunks by relevance.
- **Hybrid search** — keyword + semantic combined.
- **GraphRAG / agentic RAG** — fancier retrieval (knowledge graphs / multi-step agent-driven). Mostly hype-adjacent; know the names.

### Emerging protocols
- **A2A (Agent-to-Agent)** — proposed protocol for agents to talk to *each other* (MCP = agent-to-tools). Newer, unsettled.

### Big-picture vibes
- **Multimodal / modality** — text + image + audio + video.
- **Scaling laws** — more data/compute → predictably better models.
- **Emergent abilities** — capabilities that appear only past some model size. Contested.
- **AGI / ASI** — artificial general / super intelligence. Mostly vibes; everyone defines them differently.
