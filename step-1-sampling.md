# Step 1 — Why Output Is Non-Deterministic

**Goal:** understand the *one* fact about how the box generates text — that output is **sampled,
not computed** — and see it with your own eyes. This is the only "how the model works" you need
before building agents. Half a day, no math.

Concepts + tasks. You run the experiments.

---

## 1.1 — The mechanism (this is the whole thing)

Each step, the box does this:

1. Looks at all tokens so far.
2. Outputs a **probability distribution** over the entire vocabulary — "next token is `the` 8%,
   `a` 5%, `Nice` 0.3%, …" for every possible token.
3. **Samples** one token from that distribution (a weighted dice roll), appends it.
4. Repeats from step 1 with the new token included.

That loop — generate-one-token-conditioned-on-all-previous, append, repeat — is called
**autoregression**. It's why streaming arrives token-by-token (you're literally watching the loop
run), and why a longer reply costs more (more iterations).

**What you skip entirely:** *how* the distribution in step 2 is computed. That's the
transformer/attention/training math. You never touch it. You only need the consequence of step 3:

> The next token is **picked by a weighted random draw**, not deterministically calculated.

---

## 1.2 — What that one fact explains

- **Non-determinism.** Same prompt, run twice → can give different text, because step 3 is a dice
  roll. Nothing is broken; it's the design.
- **Hallucination.** If the distribution puts non-trivial probability on a plausible-but-wrong
  token, sampling will sometimes pick it. You can reduce this, never fully "fix" it — it's
  baked into how generation works.
- **Why you test with evals, not `assert ==`.** You can't assert the output equals a fixed string
  when the output legitimately varies. So you score *behavior* across many cases as a pass-rate %
  (that's Step 6). This single fact is *why* Step 6 exists.

### The historical lever: `temperature`
Sampling used to be tunable with `temperature` — low (→0) makes the draw greedy and
near-deterministic (always grab the highest-probability token); high (→1+) flattens the
distribution so lower-probability tokens get picked more, giving more variety.

Note for 2026: on **current frontier models** (`claude-opus-4-8`, Fable 5) `temperature` is
*removed* — sampling still happens, they just manage it for you and you steer with `effort` /
prompting instead. But on the **older model you're testing with** (`claude-haiku-4-5`,
`claude-sonnet-4-5`) you *can* still set `temperature` — which makes for a clean experiment below.

---

## 1.3 — Tasks

1. **See the variance.** Send the *exact same* prompt ~8 times and compare the replies. Use a
   prompt that invites variety, e.g. "Give me one random animal and a one-line fun fact." Watch
   them differ across identical requests.

2. **Collapse the variance (temperature).** On `claude-haiku-4-5`, send the same prompt several
   times with `temperature: 0`, then several times with `temperature: 1`. Observe: near-identical
   at 0, varied at 1. You just watched the dice roll get sharp vs. flat.

3. **Find the near-deterministic case.** Ask something with one dominant answer ("What is 7 × 8?
   Reply with just the number."). Note it barely varies even at higher temperature — because the
   distribution is already spiked on one token. Variance depends on how *peaked* the distribution
   is, not just on temperature.

4. **Write it in your own words** (a few sentences): sampling → autoregression → why this forces
   evals instead of equality assertions. If you can write that cleanly, you own Step 1.

Samping is when the model computes the probability of the next word based on all the previous words filter based on temperature and then do a dice role to pick the winner token. autoregression is basically the loop that keeps doing this to produce more text (tokens). Why we can't use assert is because the output is non deterministic due to the sampling step. this is why we need to do evals, we basically run many human created test cases and compare the model output against the human response and give a score for each test case, some test cases may be black and white (in the case of the email classifier returning an enum). or it may be more nuanced than that (checking how close a summary is to the original text) which may come from another LLM (llm as judge)
---

## 1.4 — Done when you can answer

- Why can two identical requests return different text?
- What is autoregression, in one sentence?
- What does `temperature` actually change about step 3 — and why does a "What is 2+2" prompt
  barely vary regardless?
- Why does this fact mean you validate an agent with a pass-rate over many cases, not `assert ==`?

---

## What this sets up
- **Step 6 (evals)** is the direct consequence of this step — you'll build a scored test suite
  *because* output is sampled.
- **Step 2** doesn't depend on this, but keep it in mind: a tool-calling model can emit different
  tool calls for the same input, so your harness must be robust to *what* it asks for, not assume
  a fixed script.
