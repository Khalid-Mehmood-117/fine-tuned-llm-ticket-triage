# CLAUDE.md

## Project
Qwen2.5-0.5B-Instruct fine-tuned with LoRA to turn one customer support ticket into strict JSON
(category, priority, sentiment, needs_human, suggested_action, reason). Deterministic business rules
run in code after the model. Evaluated against the base model and gpt-4o-mini on a held-out
synthetic test set, with a Gradio demo on Hugging Face Spaces (free CPU).
Public portfolio project on GitHub, shown to Upwork clients. Code quality, README and evaluation
results matter.

## Owner
Khalid Mehmood, AI Engineer. Working with Claude Code as the daily coding partner. Windows machine,
repo at C:\Data\Projects\fine-tuned-llm-ticket-triage. Commits are authored as
Khalid Mehmood <khalidmehmood117@gmail.com> (repo-local git config).
GitHub: Khalid-Mehmood-117/fine-tuned-llm-ticket-triage. Hugging Face: Khalid-Mehmood-117.

## Stack (fixed, do not change without asking)
- Local code: Python 3.13, CPU only (no GPU needed anywhere outside Colab)
- Model: Qwen/Qwen2.5-0.5B-Instruct with a LoRA adapter
- Training: transformers, PEFT and TRL SFTTrainer in notebooks/train.ipynb on a free Colab T4
- Data generation and comparison model: gpt-4o-mini through the direct OpenAI SDK (no LangChain)
- Schema and validation: Pydantic
- Dedup and metrics: scikit-learn
- Hub: huggingface_hub for the adapter and the Space
- Demo: Gradio on Hugging Face Spaces, CPU basic (free)
- Tests: pytest with OpenAI and the Qwen model faked (no network, no GPU, no model download)

## Rules
- Follow PLAN.md. Milestones M1 to M4 in order. Do not start the next milestone until the current one is verified with real output.
- Never commit .env, OPENAI_API_KEY, HF_TOKEN or any other token. .env.example is the only env file in git. The Colab notebook reads HF_TOKEN from Colab secrets and never prints it; notebook outputs are checked for tokens before commit.
- Label sets are fixed in schema.py. Every system's output is validated against the same Pydantic model. Anything outside the sets is invalid, never silently mapped.
- Business rules live in rules.py as pure functions that only escalate (raise priority, set needs_human, switch to an escalation action). They never lower priority or clear needs_human. Every change a rule makes is recorded in rules_fired. The model never makes safety, legal or security calls alone.
- Fallback: if the fine-tuned model returns invalid JSON after one retry, pipeline.py falls back to gpt-4o-mini and logs it. The demo and the eval use the same pipeline.py code path.
- Test split is held out: never used for training, prompt few-shot examples, threshold tuning or rule writing. Few-shot examples come from train only.
- Do not tune prompts or rules to make individual test tickets pass. A rule must be a general business rule, covered by unit tests, and visible in rules_fired when it acts.
- The data is synthetic and the README and data card say so. Report the known bias that gpt-4o-mini wrote the tickets.
- Report eval results honestly, including where the fine-tuned model loses. eval/history.md is append only.
- No em dashes in any file, README, comment or notebook.
- Prefer small, readable functions over clever code. This repo is read by clients.
- Commit after every verified milestone with a clear message, then push to origin main.
- Progress visibility: for any task with more than 3 steps, first write a numbered todo list of the steps, then mark each one done as you finish it and post a one-line note ("Step 2 of 6 done: tickets generated"). Never go silent for a long stretch; if a step is taking longer than expected, say what is slow and why.

## Self-maintenance (mandatory)
At the end of every milestone, before telling the owner it is done:
1. Update the Status section below: what is complete, what was verified and how, what is next.
2. Update PLAN.md if any design decision changed.
3. Commit CLAUDE.md and PLAN.md together with the milestone code.
Do this without being asked. A milestone is not complete until this is done.

## Status
- Environment verified (2026-10-05): Python 3.13.5, Git 2.55.0. Repo cloned, remote
  https://github.com/Khalid-Mehmood-117/fine-tuned-llm-ticket-triage.git (renamed from the
  misspelled ine-tuned-llm-ticket-triage), fetch verified. .env holds OPENAI_API_KEY and an empty
  HF_TOKEN. .env is gitignored.
- Done: PLAN.md, CLAUDE.md, .env.example, .gitignore. Plan approved 2026-10-05 with decisions:
  gpt-4o-mini in JSON mode plus a fourth "strict structured outputs" row marked validity by design,
  Claude does a blind first pass on 50 test labels and Khalid confirms, Khalid runs the Colab
  notebook (one Run all, settings cell at the top), HF_TOKEN not needed before M2.
  Committed and pushed as 5369ad4.
- Done: M1 dataset and splits (2026-10-06). .venv with pinned requirements.txt, package installed
  editable from pyproject.toml. src/triage: schema.py (label sets, Pydantic Triage model),
  labels.md (label definitions), rules.py (R1 to R5, keyword lists in 6 languages, escalate only).
  scripts: scenarios.py (60 scenarios, 6 fictional companies, 9 styles, 6 languages),
  generate_data.py (labels sampled first, gpt-4o-mini writes ticket and reason), dedup_split.py,
  check_splits.py, hand_check.py (sample, build, apply).
- M1 verification: 30-ticket pilot read by hand (fixed repeated order numbers and generic
  reasons). Full run 1,700 tickets, 0 failures, 597,669 input and 186,029 output tokens including
  the pilot, about $0.20. Dedup removed 2 exact and 18 near-duplicates (0.85), 1,680 kept. Split
  1,343 / 169 / 168, grouped at 0.7; check_splits.py passes with max cross-split similarity 0.698.
  Rule keywords widened using train and validation misses only (9 of 149 missed before, 0 after);
  11 known over-escalations (8 negation, 3 loose wordings) kept on purpose (owner decision: they
  are documented and on the safe side). Hand check: Claude's blind first pass agreed with the
  dataset on 38/50 rows; a human reviewer confirmed 41/50 dataset labels (82%) and corrected 9
  (priority 5, sentiment 4, one row also category and action), all matching the first pass.
  Corrections applied to data/splits/test.jsonl, agreement in data/hand_check/agreement.json and
  data/DATA_CARD.md. README heading fixed, synthetic data and bias notes added. pytest: 59 passed.
- Notes from M1: the review CSV must be closed in Excel before scripts write it (Windows lock).
  Reason sentences were not hand checked; the t00047 reason was rewritten to match its corrected labels (reason is
  not scored). Test rule coverage has not been looked at; report it in M3.
- Next: M2. Needs HF_TOKEN with write access in .env and as a Colab secret. Build
  notebooks/train.ipynb (settings cell at the top, single Run all), Khalid runs it on a free T4,
  then qwen_local.py loads the adapter on CPU.
