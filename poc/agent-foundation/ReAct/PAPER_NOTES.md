# Close reading: ReAct (Yao et al., 2022)

**Paper:** *ReAct: Synergizing Reasoning and Acting in Language Models*
**Authors:** Shunyu Yao, Jeffrey Zhao, Dian Yu, Nan Du, Izhak Shafran, Karthik Narasimhan, Yuan Cao
**Venue:** ICLR 2023 (arXiv:2210.03629, Oct 2022)
**Code:** https://github.com/ysymyth/ReAct · https://react-lm.github.io/

This note is for building intuition you can later cite, not for summarizing abstracts. Read it with the implementation in `react_foundations/loop.py` open.

---

## 1. The problem ReAct actually poses

Two LLM literatures were running in parallel in 2022:

| Line | What the model emits | Failure mode |
|---|---|---|
| **Reasoning** (Chain-of-Thought, Wei et al. 2022) | Free-form verbal traces, then an answer | Un-grounded. Facts are sampled from parameters. Hallucinations propagate because later thoughts condition on earlier invented facts. |
| **Acting** (WebGPT, SayCan, Inner Monologue, ALFWorld agents) | Domain actions (`search`, `go to desk 1`, click) | Under-reasoned. Hard to decompose goals, track progress, or recover when an observation is useless. |

ReAct’s claim is not “tools are good” and not “let’s think step by step.” It is that **those two streams should be the same policy**, interleaved, because each repairs the other:

- Thoughts let the policy *induce, track, and update* an action plan, and handle exceptions.
- Actions let the policy *leave its own parameters* and pull observations that later thoughts can use.

If you already ship an MCP tool loop, you are looking at a descendant. The research question is which parts of that descendant are load-bearing (interleaving, observation grounding, plan revision) versus incidental (framework objects, JSON schemas, multi-agent roles).

---

## 2. Formalism (Section 2) — keep this in working memory

Standard interactive setup:

- Observation \(o_t \in \mathcal{O}\)
- Action \(a_t \in \mathcal{A}\)
- Context \(c_t = (o_1, a_1, \ldots, o_{t-1}, a_{t-1}, o_t)\)
- Policy \(\pi(a_t \mid c_t)\)

ReAct **augments the action space**:

\[
\hat{\mathcal{A}} = \mathcal{A} \cup \mathcal{L}
\]

A thought \(\hat{a}_t \in \mathcal{L}\) does **not** call the environment. There is no new \(o_{t+1}\) from Wikipedia / ALFWorld / WebShop. The only effect is:

\[
c_{t+1} = (c_t, \hat{a}_t)
\]

That is the entire trick. Thoughts are context writes. Actions are environment writes. Observations are environment reads. The model is prompted to emit both from one frozen LLM.

Two scheduling regimes, because tasks differ:

1. **Dense thoughts (HotpotQA, FEVER).** Alternate Thought / Action / Observation every step. Reasoning is the bottleneck; you can afford a thought per action.
2. **Sparse thoughts (ALFWorld, WebShop).** Long horizons (50+ steps). Thoughts appear only when useful: decompose the goal, mark a subgoal done, apply commonsense (“lamps live on desks”), or recover from a dead end. The model is allowed to emit actions without thoughts.

This distinction matters later when you look at your own orchestrator. A thought on every MCP call is HotpotQA-style density. A planner that writes a brief and then issues a burst of tools is ALFWorld-style sparsity. ReAct argues both are valid; the paper does not claim one schedule is universally better.

---

## 3. Thought types (what “reasoning” is doing)

The paper is unusually concrete about *kinds* of thoughts. When you read traces, label them:

1. **Goal decomposition / plan** — “I need to search \(x\), find \(y\), then find \(z\).”
2. **Commonsense injection** — “desklamps are probably on desks or shelves.”
3. **Observation extraction** — “\(x\) was started in 1844.” Compress a noisy page into a fact the next step can use.
4. **Progress tracking** — “now I have the company; next I need HQ city.”
5. **Exception handling / plan revision** — “the paragraph does not tell \(x\); maybe search \(x\) (film) instead.”
6. **Answer synthesis** — “1844 < 1989, so Arthur’s Magazine.”

Act-only baselines fail most often on (1), (4), (5), and (6). CoT-only fails on (3) and (5) because there is no observation to extract and no external exception — the model just invents the missing fact.

---

## 4. Knowledge tasks: Wikipedia as a deliberately weak tool (Section 3)

### Setup

- **HotpotQA:** multi-hop QA over Wikipedia. Metric: exact match (EM).
- **FEVER:** claim → SUPPORTS / REFUTES / NOT ENOUGH INFO. Metric: accuracy.
- **Question-only:** no gold passages. Either parametric memory or retrieve.

### Action space (this repo implements these three)

| Action | Environment effect |
|---|---|
| `search[entity]` | If the page exists, return the **first 5 sentences**. Else return top-5 similar titles from the Wikipedia search engine. |
| `lookup[string]` | Ctrl+F: next sentence on the current page containing `string`. |
| `finish[answer]` | Terminate. |

The paper is explicit that this API is **weaker** than a real retriever (BM25, DPR, RAG). That is the point. They want to simulate a human at a Wikipedia search box, forcing *language* to do query reformulation. If you replace this with a strong retriever, you are no longer testing ReAct’s claim about reasoning-to-act; you are testing RAG.

HotpotQA ReAct uses **6** human-written trajectories as shots. FEVER uses **3**. They report that more shots did not help. Decoding is greedy. Step cap: **7** on HotpotQA, **5** on FEVER (almost no correct traces were longer).

### Baselines (ablate the trace, keep the examples)

Constructed from the *same* human trajectories:

- **Standard:** strip thoughts, actions, observations → QA exemplars.
- **CoT:** keep thoughts, strip tools.
- **CoT-SC:** sample 21 CoT traces at \(T=0.7\), majority vote (Wang et al. 2022).
- **Act:** keep tools, strip thoughts (WebGPT-shaped, but prompting not RL).

### The result that should change how you talk about agents

PaLM-540B, Table 1 (prompting):

| Method | HotpotQA EM | FEVER Acc |
|---|---|---|
| Standard | 28.7 | 57.1 |
| CoT | 29.4 | 56.3 |
| CoT-SC | 33.4 | 60.4 |
| Act | 25.7 | 58.9 |
| ReAct | 27.4 | 60.9 |
| CoT-SC → ReAct | 34.2 | 64.6 |
| ReAct → CoT-SC | **35.1** | 62.0 |
| Supervised SoTA (then) | 67.5 | 89.5 |

Read this slowly:

- ReAct **beats Act** on both datasets. Thoughts help acting, especially final synthesis.
- ReAct **loses to CoT on HotpotQA** (27.4 vs 29.4) and **wins on FEVER** (60.9 vs 56.3). FEVER labels often hinge on a small factual difference; retrieval matters more.
- The **best prompting method is a combination**, not ReAct alone. Heuristics:
  - ReAct → CoT-SC: if ReAct hits the step cap with no answer, back off to self-consistent CoT.
  - CoT-SC → ReAct: if the majority answer occurs in fewer than \(n/2\) samples, internal knowledge is not confident; switch to ReAct.

If your production agent “always tools,” you are betting against this table. The paper’s own best system uses *internal knowledge when it is consistent* and *external knowledge when it is not*.

Also sit with the SoTA gap: 35 vs 67 EM. Few-shot ReAct is not a HotpotQA solver. It is a *policy shape*.

### Human error analysis (Table 2) — memorize this taxonomy

On 200 labeled HotpotQA traces:

| | ReAct | CoT |
|---|---|---|
| Success that is actually true-positive | 94% | 86% |
| Success that is false-positive (hallucinated but EM-correct) | 6% | 14% |
| Failure: reasoning error (incl. repetitive loops) | **47%** | 16% |
| Failure: empty/useless search | **23%** | — |
| Failure: hallucination | **0%** | **56%** |
| Failure: label ambiguity (right idea, EM miss) | 29% | 28% |

Implications for your later eval harness:

- EM is necessary and insufficient. CoT can be EM-correct for the wrong reasons.
- ReAct’s distinctive failure is **structural rigidity + bad search**, not making facts up.
- A frequent ReAct bug: the model repeats the previous thought/action. They dump this in “reasoning error” and suspect greedy decoding. You will see this in real MCP agents as “retry the same tool with the same args.”
- 29% label noise/ambiguity is a HotpotQA problem, not a model problem. Execution-based metrics still collide with messy labels.

### Finetuning (Figure 3) — the other headline

Prompting ReAct is *worst* at 8B/62B (hard to learn two behaviors from 6 shots). After finetuning on **3,000 bootstrapped correct traces**:

- Finetuned ReAct is the **best** of {Standard, CoT, Act, ReAct}.
- 8B-ft ReAct beats all 62B prompting methods.
- 62B-ft ReAct beats all 540B prompting methods.
- Finetuning Standard/CoT is weak: you are teaching the model to memorize (possibly hallucinated) facts. Finetuning Act/ReAct teaches a *skill* (how to use Wikipedia).

STaR-style bootstrapping (Zelikman et al. 2022) is the data engine: keep traces whose *final answer* matched gold. That is noisy supervision on the rationale.

---

## 5. Decision-making tasks (Section 4)

### ALFWorld

Text household, 6 task types, >50 locations, expert horizon >50 steps. Sparse thoughts: decompose, track subgoals, commonsense locations. **One or two** in-context trajectories per task type.

- Best ReAct: **71%** success vs best Act **45%** vs BUTLER IL **37%** (BUTLER trained on ~1e5 expert trajectories).
- Relative gain of ReAct over Act across 6 prompt permutations: 33–90%, mean 62%.
- Ablation **ReAct-IM**: Inner Monologue-style dense verbalization of *external* state (“I see X, I need Y”). ReAct-IM **53%** vs ReAct **71%**. Internal planning thoughts beat “narrate the observation.”

### WebShop

1.18M real products, noisy catalog text, buy a product matching a constraint. One-shot.

- ReAct success rate **40%** vs Act **30%** vs IL+RL **29%**. Humans **59.6%**.
- Gain is mostly “bridge noisy observation → relevant option,” i.e. thoughts as alignment between instruction and catalog language.

Takeaway you can reuse: **sparse reasoning over long-horizon tools** is where ReAct’s advantage is largest, not on HotpotQA EM.

---

## 6. What ReAct is *not*

- **Not** Inner Monologue. IM injects environment feedback into language; it does not freely plan, revise, or inject commonsense. The ALFWorld ablation is the evidence.
- **Not** WebGPT. WebGPT acts in a browser but does not model thoughts; it uses expensive RLHF.
- **Not** RAG as commonly shipped. RAG retrieves then generates one rationale. ReAct retrieves *conditionally*, multiple times, with thoughts in between.
- **Not** a multi-agent system. One frozen model, one prompt, one trajectory.
- **Not** modern function calling. There is no JSON schema, no tool list of 44 MCP servers. The grammar is `Name[argument]`. Progressive disclosure and protocol-level discovery are later problems.

---

## 7. Limitations the authors already admit (use these in your own write-ups)

1. Context length: complex action spaces need more demonstrations than a prompt can hold. They point to finetuning.
2. Prompting ReAct underperforms prompting CoT on HotpotQA. Groundedness costs flexibility.
3. Search quality dominates. 23% of ReAct failures are “the API returned nothing useful.”
4. Repetition loops under greedy decoding.
5. Supervised SoTA still crushes few-shot prompting on knowledge tasks.
6. Safety: hooking an LLM to an environment can retrieve private/inappropriate content or take harmful actions. Their experiments bound the action space (Wikipedia / non-purchasing WebShop).

When you write a paper, steal this honesty. A limitations section that names *your method’s distinctive failure* (here: rigidity + search misses, not hallucination) is the part reviewers trust.

---

## 8. Mapping onto the Intelligence Hub / MCP work

| ReAct piece | IH analogue | Research caution |
|---|---|---|
| `search` / `lookup` / `finish` | MCP tools | Same loop. Different discovery and auth. |
| Thought as context write | Orchestrator “scratchpad” / plan | Dense vs sparse is a real design knob. Measure it. |
| Wikipedia observation | Tool result | Groundedness vs flexibility tradeoff still applies. |
| Act-only baseline | Tool calls with no planner | Paper says this is strictly worse when synthesis is hard. |
| CoT-only baseline | In-context solving with no tools | Paper says this hallucinates; on some tasks it still wins EM. |
| ReAct → CoT backoff | “If tools fail, just answer” | Best HotpotQA prompting method. You should test this backoff. |
| Table 2 taxonomy | MAST (later) | ReAct’s taxonomy is QA-specific; MAST is multi-agent. Do not conflate. |
| Finetuning on traces | Qwen agentic FT branch | Paper’s result: teach *how to act*, not *what the fact was*. |

The roadmap’s Phase 3 hypothesis (“does orchestration beat flat in-context?”) is already sitting in Table 1. ReAct is the *flat* tool-using agent. Orchestration has to beat *this*, not beat Standard prompting.

---

## 9. What to implement so the idea is in your hands

Minimum viable reproduction (this folder):

1. Parser for `Thought i` / `Action i` / `Observation i` (original notebook format).
2. Wikipedia env with the three actions, including “similar entities” on miss and Ctrl+F `lookup`.
3. 7-step cap, greedy loop, few-shot prefix from `prompts_naive.json`.
4. HotpotQA EM + token F1 (not LLM-as-judge).
5. Ablations: Standard, CoT, Act, ReAct on the same questions.
6. Failure tags aligned with Table 2.

Then, and only then, swap the scripted LLM for a real model and the local wiki for live Wikipedia. If you start with LangChain’s ReAct agent you will learn an API, not the result.

---

## 10. Next paper in the stack

**Reflexion** (Shinn et al., 2023) — verbal self-critique written back into memory between *episodes*, not between tool calls. ReAct is intra-episode interleaving; Reflexion is inter-episode credit assignment without weight updates. Implement that second. Do not skip it for MAST.
