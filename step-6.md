# Step 6 — Evals

**Goal:** build a test suite for a non-deterministic system. Output is *sampled* (Step 1), so
`assert output == expected` is meaningless — two correct runs produce different text and your test
"fails." So you stop testing for equality and start measuring **pass-rate**: a set of cases, each
scored, aggregated into a **percentage** you can move and regression-test. An eval's result is
"84% passed," not green/red. Almost no one's portfolio has this — it's the most underrated
interview signal in the whole roadmap.

Concepts + tasks. You write the harness. It's your Messages API call in a loop + a scorer +
a tally — no new wire protocol, no framework.

---

## 6.0 — The one-line mental model

**An eval is a test suite whose output is a number, not a boolean.** Unit tests assume a
deterministic function: same input → same output → `assert ==`. The box breaks that assumption at
the root (Step 1: output is sampled). So you replace the boolean with a **rate**: run N cases,
score each pass/fail, report `passed/N`. A single flaky case isn't a bug — a *dropping pass-rate*
is.

```
Unit test:   f(input) == expected            →  true / false
Eval:        score( agent(input), expected )  →  pass/fail, ×N  →  "84%"
```

The reframe: you're no longer asking "is this output correct?" (unanswerable for one sample). You're
asking "across a representative set, how often is it correct?" — and "did that fraction go up or
down when I changed the prompt/model?"

---

## 6.1 — Anatomy: an eval harness is 4 parts

Every eval system, from your 30-line script to a vendor platform, is these four pieces:

1. **Eval set (golden dataset / ground truth).** ~30–50 cases, each `{input, expected}`. The
   `expected` is the **reference answer** — your known-good to grade against. This is *data*, not
   code: a JSON/list file you can grow without touching harness logic.
2. **Task runner.** Feed each `input` through the thing under test → collect the raw output. The
   "thing" is either a single model call or your whole Step 2–4 agent.
3. **Grader (scorer).** Maps `(output, expected) → pass/fail` (or a 0–1 score). This is the part
   with real design choices — see 6.2.
4. **Aggregator.** Tally to a pass-rate %, ideally broken down per category, and printed so you can
   compare two runs (version A vs. version B).

That's it. The intelligence is in the *dataset* and the *grader*, not the plumbing.

---

## 6.2 — The three grader types (pick the cheapest that works)

Graders go from cheap+rigid to expensive+flexible. **Always reach for the cheapest one that can
actually judge the case** — a model-graded check on something a string-match could verify is wasted
money and a new source of flakiness.

| Grader | How it scores | Use for | Cost / reliability |
|---|---|---|---|
| **Deterministic / rule** | exact match, regex, "did it call the right tool", valid-JSON, number-within-tolerance | classification, extraction, structured output, tool-selection | free, 100% repeatable |
| **Programmatic** | `expected in output`, set overlap, key presence | "answer mentions X", partial-credit checks | free, repeatable |
| **LLM-as-judge** | a *second* model call grades against a rubric | summaries, explanations, "is this faithful / helpful / correct in meaning" | costs tokens, itself non-deterministic |

The skill is **matching the grader to the case.** If you can phrase the success condition as a
string/rule check, do that. Only fall to LLM-as-judge when correctness is genuinely semantic and
no rule captures it.

---

## 6.3 — Designing the eval set (this is the real work)

The harness is trivial; a *good dataset* is where evals live or die.

- **Reference answers must be genuinely known-good.** A wrong `expected` silently inverts the
  score. Hand-verify them.
- **Cover the distribution, not just the happy path.** Include easy cases, hard cases, edge cases,
  and known failure modes you've actually seen. An eval that's all softballs reports 100% and tells
  you nothing.
- **Tag cases by category** (e.g. "extraction", "tool-choice", "refusal-handling"). Per-category
  pass-rate tells you *where* a regression landed, not just that one happened.
- **Start tiny, grow.** 5–10 cases to get the loop running, then scale toward 30–50. You add cases
  forever — every production bug becomes a new eval case (this is how you prevent regressions).
- **Deterministic-gradeable first.** Choosing inputs whose answers are string-checkable lets you
  build the whole harness before you ever touch a judge.

---

## 6.4 — LLM-as-judge, done right

When you do need it: a second model call reads `(input, output, reference)` and returns a verdict.
It's just another Messages API call — but it has failure modes a string-match doesn't:

- **Give it a rubric, not a vibe.** "Score 1 if the summary states the refund window in days,
  else 0" beats "is this a good summary?". Tight rubric → repeatable judge.
- **Force a structured verdict.** Make the judge emit `{pass: bool, reason: str}` (structured
  output / a tool-shaped response), so you can parse it and read *why* it failed — not free prose.
- **Use a cheap grader model.** `claude-haiku-4-5` is the grader. You don't need a frontier model
  to check a rubric, and you'll run it 30–50× per eval pass.
- **Know the biases.** LLM judges have **position bias** (favor the first option in A/B), **length
  bias** (favor longer answers), and **self-preference**. Mitigate by keeping the rubric narrow and,
  for comparisons, swapping order. The judge is a *measuring instrument* — sanity-check it (spot-grade
  a few by hand) before you trust its number.
- **The judge is itself non-deterministic.** That's fine — you're measuring a rate, and a tight
  rubric keeps judge variance low. But never treat its output as ground truth; treat it as a noisy
  sensor.

> Model knobs reminder (your repo facts): you don't set `temperature` on current models — it's
> removed (HTTP 400). Steer the grader with a sharp rubric, not a temperature. Verify the current
> grader-model id and any structured-output flags against the live docs / `claude-api` skill, not
> memory.

---

## 6.5 — The payoff: pass-rate as a regression metric

The done criterion ("change a prompt, watch the % move") is the entire point. Once you have a
pass-rate, prompt-engineering stops being vibes:

- Change a system prompt → re-run → did 84% become 91% or 72%?
- Swap `haiku` for `sonnet` under the agent → does the rate justify the cost?
- A production bug slips through → add it as case #51 → it's regression-tested forever.

This is **offline eval** (a fixed dataset you run on demand). Know the term **online eval** exists
(scoring real production traffic) — you won't build it here, but interviewers like that you know the
distinction.

---

## 6.6 — Tasks (build the harness)

Build deterministic-only first. Adding the judge before the skeleton works means you can't tell
whether a failure is your *agent* or your *grader*.

1. **Pick the unit under test.** Start **single-shot** (one model call: a classification or
   extraction task with string-checkable answers), *not* your full multi-step agent — so eval
   flakiness can't be confused with agent flakiness. You'll point it at the full agent later.

2. **Write the dataset.** 5–10 cases as `{input, expected}` in a list/JSON file (scale to 30–50
   once the loop runs). Keep it as data, separate from harness logic. Tag each with a category.

3. **Runner + deterministic grader.** Loop the cases: run each `input`, grade `output` vs.
   `expected` with an **exact-match or rule** check. No judge yet.

4. **Aggregate + report.** Print `X/N passed (Y%)`, and for each failure print the case id, the
   `expected`, and the actual `output`. The failure printout is what makes the suite usable.

5. **Prove it's wired right.** Deliberately corrupt one `expected` → the % must drop and the harness
   must name that case. (Your "break it on purpose" check from Step 5.)

6. **Add the LLM-as-judge (phase 2).** Add 5–10 cases whose correctness is *semantic* (no string
   check works). Grade them with a `claude-haiku-4-5` call against a tight rubric that returns a
   structured `{pass, reason}`. Spot-check a few judge verdicts by hand to confirm the judge is
   trustworthy before you believe its number.

7. **Move the number.** Change a prompt (or the model) on the thing under test, re-run, and watch
   the pass-rate shift. That's the done criterion.

---

## 6.7 — Done when you can answer without looking

- Why can't you unit-test an LLM agent with `assert output == expected`? What do you measure instead?
- What are the four parts of any eval harness?
- Given a case, how do you decide between a deterministic grader and an LLM-as-judge?
- What makes a *good* eval dataset (vs. one that reports a meaningless 100%)?
- Name two biases an LLM judge has, and how you'd reduce them.
- What does "change a prompt and watch the pass-rate move" actually buy you over eyeballing outputs?
- Offline vs. online eval — what's the difference?

---

## What this sets up

- **Interview soundbite, earned:** "Output's sampled, so I validate with evals — a scored dataset
  and a pass-rate — not equality assertions. I use deterministic graders where I can and an
  LLM-as-judge only for semantic cases."
- This is the **measuring instrument** for everything else: any future change (a new prompt, a new
  model, the Step 7 RAG layer) is now something you can *score* instead of guess at.
- **Step 7 (RAG)** plugs straight in — once you're retrieving chunks, an eval set of
  question→expected-answer pairs is exactly how you'll prove retrieval actually helped.
