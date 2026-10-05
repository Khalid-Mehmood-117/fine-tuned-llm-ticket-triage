# PLAN.md

## Goal
Fine-tune Qwen2.5-0.5B-Instruct with LoRA (PEFT + TRL) so it reads one customer support ticket and
returns strict JSON with six fields. Deterministic business rules run in code after the model, so
the model never makes safety, legal or security calls on its own. Compare the fine-tuned model
against the base model and gpt-4o-mini on a held-out test set, and ship a free Gradio demo on
Hugging Face Spaces (CPU).

Public portfolio project. The point a client should take away: a 0.5B model that costs nothing
per call can match or beat a general API model on a narrow, well-defined task, with guardrails in
code and an honest evaluation.

## Output schema
Every system returns exactly this JSON object, validated by one Pydantic model (`schema.py`).
Labels are fixed sets. Anything outside a set, a missing field or extra text counts as invalid.

| Field | Type | Allowed values |
|---|---|---|
| category | enum (10) | billing, refund, shipping, account_access, technical_issue, product_question, cancellation, complaint, feature_request, other |
| priority | enum (4) | low, medium, high, urgent |
| sentiment | enum (3) | negative, neutral, positive |
| needs_human | bool | true, false |
| suggested_action | enum (10) | reply_with_kb_article, ask_for_details, route_to_billing, route_to_technical, route_to_shipping, start_refund_review, reset_account_access, process_cancellation, escalate_to_supervisor, escalate_to_safety_legal |
| reason | string | English, 1 sentence, at most 25 words (the only free text field) |

Example:
```json
{"category": "refund", "priority": "high", "sentiment": "negative", "needs_human": true,
 "suggested_action": "start_refund_review", "reason": "Customer was charged twice for one order and asks for the duplicate charge back."}
```

Label definitions (what makes a ticket "urgent" versus "high", when needs_human is true, and so
on) are written once in `labels.md` and used by the data generator, the gpt-4o-mini prompt, the
base model prompt and the hand check, so every part of the project agrees on what a label means.

## Business rules (code, after the model)
`rules.py` holds pure functions. Each rule has an id, reads the ticket text and the model output,
and can only escalate (raise priority, set needs_human to true, change the action to an escalation).
No rule ever lowers priority or clears needs_human. Every rule that changes the output is listed in
`rules_fired` with its id and what it changed. Keyword lists cover English plus the non-English
languages in the dataset.

| Id | Trigger | Effect |
|---|---|---|
| R1_SAFETY | injury, fire, smoke, burn, shock, choking, overheating, medical harm | needs_human=true, priority=urgent, action=escalate_to_safety_legal |
| R2_LEGAL | lawyer, lawsuit, sue, court, legal action, GDPR or data deletion request, regulator | needs_human=true, priority=urgent, action=escalate_to_safety_legal |
| R3_SECURITY | hacked, unauthorized charge or login, stolen account, fraud | needs_human=true, priority at least high |
| R4_CHARGEBACK | chargeback, dispute with my bank | needs_human=true, priority at least high |
| R5_ESCALATION_CONSISTENCY | model chose an escalate_* action | needs_human=true |

Rules are unit tested with positive and negative examples (including "I am not going to sue,
just want help" style negations, which are documented as a known keyword limitation if not handled).

## Pipeline
```
ticket -> fine-tuned Qwen (greedy) -> parse + validate
            invalid -> one retry (sampling, temperature 0.3, fixed seed) -> parse + validate
            still invalid -> gpt-4o-mini fallback, logged to logs/fallback.jsonl
        -> rules.py -> final JSON + rules_fired + model_used + latency_ms
```
`pipeline.py` owns this flow. The demo and the eval both call it, so there is one code path.

## Dataset
- Size: generate about 1,700 tickets with gpt-4o-mini so that about 1,500 remain after dedup.
- Labels come first: a sampler draws a target label set (category, priority, sentiment,
  needs_human, action) plus a product, a writing style and a language, then gpt-4o-mini writes a
  ticket that fits. The label is the sampled spec, not a gpt-4o-mini guess. Safety, legal and
  security tickets are sampled with labels that already agree with the rules.
- Products: six fictional companies (SaaS tool, online fashion store, mobile carrier, banking app,
  smart home device, food delivery). No real brands.
- Styles: formal, casual, angry, very short (under 10 words), rambling, typos and no punctuation,
  multi-issue, forwarded email with signature and quoted thread, written on a phone.
- Languages: about 85 percent English, 15 percent split across Spanish, French, German, Portuguese
  and Roman Urdu. Output labels and reason are always English.
- Hard cases on purpose: multi-issue tickets (label is the most urgent issue), negated keywords,
  sarcasm, tickets with almost no information (action ask_for_details).
- Dedup: exact match on normalized text, then near-duplicates with TF-IDF character n-grams and
  cosine similarity (threshold set from a look at the score distribution, starting at 0.9).
  Near-duplicate clusters are kept whole inside one split, so no near-duplicate crosses splits.
- Split: 80/10/10 train/validation/test, stratified by category, fixed seed. A check script
  proves the max cross-split similarity is under the threshold.
- Hand check: 50 test tickets, stratified by category, exported to `data/hand_check/test_50.csv`.
  Each label is marked correct or corrected. Corrections are applied to the test split, and the
  agreement rate per field goes in the data card.
- Data card: `data/DATA_CARD.md` with how it was made, label distribution, language and style mix,
  dedup counts, hand check results, known biases and license.
- README states clearly that all tickets are synthetic and generated by gpt-4o-mini.
- Known bias, stated up front: gpt-4o-mini wrote the tickets, which may favour gpt-4o-mini in the
  comparison. Labels from the sampler and the hand check reduce this but do not remove it.

## Training (Google Colab, free T4)
- `notebooks/train.ipynb`, runnable top to bottom on a free T4. It clones the public GitHub repo
  for the splits, reads HF_TOKEN from Colab secrets (`google.colab.userdata`), trains and pushes the
  LoRA adapter to `Khalid-Mehmood-117/qwen2.5-0.5b-ticket-triage-lora` on the Hub with a model card.
- TRL SFTTrainer, chat template of Qwen2.5, loss on the assistant JSON only.
- Starting hyperparameters: LoRA r=16, alpha=32, dropout 0.05 on all attention and MLP
  projections, lr 2e-4, cosine schedule, 3 epochs, effective batch 16, max length 512, fp16 (T4 has
  no bf16). Early stop on validation loss. Final values recorded in the notebook and model card.
- Short system prompt for the fine-tuned model (the label sets only). The model learns the rest.
- Local code never needs a GPU. Local inference loads base plus adapter on CPU with transformers
  and peft. 0.5B in float32 is about 2 GB of RAM.

## Evaluation
`eval/run_eval.py` runs the full test split (about 150 tickets) through three systems:
1. Base Qwen2.5-0.5B-Instruct with the strong prompt (label definitions plus few-shot examples
   from train), so the base model gets a fair chance.
2. Fine-tuned Qwen (base plus adapter) with its short training prompt.
3. gpt-4o-mini, temperature 0, with the same strong prompt and JSON output mode.
4. gpt-4o-mini with strict structured outputs (JSON schema). Marked "validity by design", since
   the API guarantees the schema, so its JSON validity is not comparable to the other rows.

Metrics per system:
- Exact accuracy per field (category, priority, sentiment, needs_human, suggested_action)
- Macro F1 for category and priority
- JSON validity rate (parses and passes the Pydantic schema) on the first try
- Latency per ticket (median and p95). Local models on this machine's CPU, which is close to the
  Space hardware. gpt-4o-mini end to end over the network.
- Cost per ticket. gpt-4o-mini from real token usage and the current list price (price kept in one
  constant and checked at M3). Local models have no API cost; the README says compute is not free
  in general but is here (free Space CPU).

Scored twice: raw model output, and final output after rules. The fine-tuned row is also shown
with and without fallback, with the fallback rate. The reason field is not scored for accuracy,
only checked for presence and length. `eval/results.md` is rewritten each full run;
`eval/history.md` gets one appended line per run (never rewritten). Per-ticket predictions saved
to `eval/predictions/` for error analysis. A confusion matrix for category goes in results.md.

## Demo (Hugging Face Spaces, free CPU)
- Gradio app in `space/`, deployed to a public Space under Khalid-Mehmood-117.
- Loads base plus adapter from the Hub at startup.
- UI: sample ticket dropdown (8 to 10 tickets covering the rules, multi-issue and non-English
  cases), free text box, JSON output, rules fired with what each changed, model used (fine-tuned
  or gpt-4o-mini fallback), latency.
- OPENAI_API_KEY set as a Space secret for the fallback. If it is missing, the app still works and
  shows that fallback is disabled.

## Repo layout
```
data/            raw/, splits/, hand_check/, DATA_CARD.md
src/triage/      schema.py, labels.md, prompts.py, parse.py, rules.py, qwen_local.py,
                 openai_client.py, pipeline.py
scripts/         generate_data.py, dedup_split.py, check_splits.py, hand_check.py
notebooks/       train.ipynb
eval/            run_eval.py, results.md, history.md, predictions/
space/           app.py, requirements.txt, README.md (Space card)
tests/           pytest, OpenAI and the Qwen model faked, no network, no GPU
docs/            architecture, screenshots, demo.gif
```

## Milestones
Each milestone ends with real output, an updated CLAUDE.md Status, and a commit pushed to origin main.

**M1 Dataset and splits with a data card**
- schema.py, labels.md, rules.py with tests, generate_data.py, dedup_split.py, check_splits.py
- About 1,500 deduplicated tickets in train, validation and test JSONL
- 50 test labels hand checked, corrections applied, DATA_CARD.md written
- Verified by: counts per split and label, cross-split similarity check output, generation cost,
  hand check agreement, pytest green

**M2 Training notebook and adapter on the Hub**
- notebooks/train.ipynb run end to end on a Colab T4 (by the owner, since Colab runs in the browser)
- Adapter and model card on the Hub; training and validation loss recorded
- qwen_local.py loads the adapter on CPU and returns valid JSON for a few validation tickets
- Verified by: Hub link, loss curve, local CPU inference output

**M3 Evaluation and results**
- pipeline.py with retry and fallback, run_eval.py, results.md, history.md
- Verified by: a full run on the test split for all three systems, metrics table, error analysis
  of the fine-tuned model's main mistakes, fallback log

**M4 Gradio Space live, README**
- space/ app deployed and working on the public Space URL
- README for a hiring client: description, results table, Mermaid architecture diagram, demo GIF,
  synthetic data statement, rules, known limitations, setup, design decisions, author line
- Verified by: the live Space tested with the sample tickets in a browser, fresh clone setup
  following the README, secret scan

## Out of scope
Real customer data, multi-turn conversations, training models larger than 0.5B, paid GPUs, a
production API service, automatic replies to customers.

## Decisions (approved 2026-10-05)
1. Label sets and rules approved as written.
2. gpt-4o-mini runs in JSON mode so its validity is measured on equal terms. A fourth eval row,
   gpt-4o-mini with strict structured outputs, is added and marked "validity by design".
3. Hand check: Claude does a blind first pass on 50 test tickets and writes a review file with the
   ticket, the dataset label, Claude's label and a blank confirm column. Khalid confirms each row,
   then the agreement rate goes in the data card and corrections are applied to the test split.
4. Khalid runs the Colab notebook. It is a single Run all with one settings cell at the top for
   the Hugging Face token (Colab secret name) and the adapter repo name.
5. HF_TOKEN is added before M2. M1 does not need it.
6. README heading fixed in M1. The gpt-4o-mini bias note stays in the README.
