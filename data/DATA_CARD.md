# Data card: synthetic support ticket triage

## Summary
1,680 synthetic customer support tickets, each labelled with category, priority, sentiment,
needs_human, suggested_action and a one sentence reason. Split 80/10/10 into train (1,343),
validation (169) and test (168) with no near-duplicates across splits.

**All tickets are synthetic.** They were written by gpt-4o-mini from sampled specs. No real
customer data was used. Company names (TaskNest, Threadline, Zephyr Mobile, Kestrel Bank,
Glowhome, Dashbite) are fictional.

## Files
| File | Content |
|---|---|
| `raw/generated.jsonl` | All 1,700 generated tickets with their spec and token usage |
| `splits/train.jsonl`, `validation.jsonl`, `test.jsonl` | Deduplicated splits used for training and evaluation |
| `dedup_report.json` | Duplicate counts, thresholds and ids removed |
| `hand_check/` | 50-ticket hand check: blind file, first pass, review file, agreement |

Each split row: `id`, `ticket`, `labels` (the six output fields), `language`, `style`, `product`,
`scenario`, `flag`.

## How it was made
1. **Labels first.** `scripts/generate_data.py` samples, with a fixed seed, a category, then a
   scenario within it (60 scenarios, each fixing the suggested action and the allowed priorities
   and sentiments), then a priority, sentiment, product, writing style and language.
   needs_human follows the definition in `src/triage/labels.md`.
2. **Ticket second.** gpt-4o-mini (temperature 1.0, JSON mode) writes one ticket that fits the
   spec plus a reason sentence. The label is the sampled spec, never a model guess. Tickets that
   must trigger a business rule (safety, legal, security, chargeback) are told to say so plainly;
   all other tickets are told to avoid those topics.
3. **Pilot.** A 30-ticket pilot was read by hand. Two fixes followed: varied order references
   (the pilot reused #123456) and reasons that name the concrete problem instead of "fits the
   category".
4. **Dedup and split.** `scripts/dedup_split.py`, see below.
5. **Hand check.** 50 test tickets, see below.

Label definitions: `src/triage/labels.md`. Scenario catalog: `scripts/scenarios.py`.

## Generation cost
1,700 tickets plus a 30-ticket pilot with gpt-4o-mini: 597,669 input tokens and 186,029 output
tokens, about **$0.20** at the list price of $0.15 and $0.60 per million tokens. No failed
generations (12 parallel requests).

## Deduplication
Text is normalized (lowercase, accents, digits and punctuation removed, so tickets that differ
only by order number are equal). Similarity is cosine over TF-IDF character 3 to 5 grams.

| Step | Removed |
|---|---|
| Exact duplicates after normalization | 2 |
| Near-duplicates, similarity 0.85 or more | 18 |
| Kept | 1,680 of 1,700 |

The 0.85 threshold was picked by reading pairs at each band: pairs above 0.85 are paraphrases
of the same message; pairs between 0.7 and 0.85 are close rewrites of the same template.
Tickets with similarity 0.7 or more are linked into groups (largest group: 8 tickets), and each
group goes to one split. `scripts/check_splits.py` confirms the highest similarity between two
tickets in different splits is **0.698**, below the 0.7 group threshold. Near-duplicates inside
one split are allowed (for example three "add dark mode" requests in test).

## Split
StratifiedGroupKFold, 10 folds, stratified by category, grouped by near-duplicate group, seed 42.
Fold 0 is test, fold 1 is validation, folds 2 to 9 are train.

### Category
| category | train | validation | test | total |
|---|---|---|---|---|
| account_access | 121 | 15 | 15 | 151 |
| billing | 144 | 18 | 18 | 180 |
| cancellation | 136 | 17 | 17 | 170 |
| complaint | 125 | 16 | 15 | 156 |
| feature_request | 137 | 18 | 17 | 172 |
| other | 122 | 15 | 16 | 153 |
| product_question | 146 | 18 | 18 | 182 |
| refund | 149 | 19 | 19 | 187 |
| shipping | 139 | 17 | 17 | 173 |
| technical_issue | 124 | 16 | 16 | 156 |
| **total** | **1,343** | **169** | **168** | **1,680** |

### Language
| language | train | validation | test | total |
|---|---|---|---|---|
| English | 1,145 | 145 | 138 | 1,428 (85.0%) |
| German | 51 | 6 | 9 | 66 |
| Portuguese (Brazil) | 47 | 3 | 7 | 57 |
| Roman Urdu | 39 | 5 | 6 | 50 |
| French | 34 | 7 | 3 | 44 |
| Spanish | 27 | 3 | 5 | 35 |

Labels and reasons are always English. With 3 to 9 test tickets per non-English language,
per-language test scores are anecdotal; only the English versus non-English split is reported.

### Other fields (all splits)
| field | distribution |
|---|---|
| priority | low 652, medium 591, high 311, urgent 126 |
| sentiment | negative 808, neutral 663, positive 209 |
| needs_human | false 1,248, true 432 |
| suggested_action | reply_with_kb_article 638, escalate_to_supervisor 136, route_to_shipping 136, start_refund_review 127, reset_account_access 126, route_to_billing 126, route_to_technical 109, escalate_to_safety_legal 105, process_cancellation 104, ask_for_details 73 |
| style | casual 243, formal 234, multi_issue 201, forwarded 198, typos 185, phone 179, very_short 175, rambling 174, angry 91 |
| product | Dashbite 349, Zephyr 322, Glowhome 294, TaskNest 287, Threadline 225, Kestrel 203 |
| rule flag | legal 57, safety 48, security 43, chargeback 19, negation 11, none 1,502 |

Word count per ticket: minimum 5, median 54, maximum 281. 10 of 175 "very short" tickets run
to 16 to 22 words.

## Business rules against the data
Rule keyword lists (`src/triage/rules.py`) were reviewed against **train and validation only**.
The first pass missed 9 of 149 flagged tickets there ("I'll dispute the charge", "got super sick
after eating", "seek legal help", a Portuguese data deletion request). General phrasings for these
were added with unit tests, and the rules now fire on all 149. Test rule coverage was not looked
at and is reported in M3.

Known over-escalation in train and validation (11 tickets, rules raise labels that a human would
not): 8 negation tickets ("no smoke, no burning smell") and 3 loose wordings ("the unauthorized
charge" for a charge after cancelling, "I don't want to risk an allergic reaction"). Rules only
escalate, so these errors go in the safe direction.

## Hand check (50 test tickets)
5 test tickets per category, seed 7. Process:
1. Claude labelled the 50 tickets blind (ticket text only, labels hidden), with an English gloss
   for the 9 non-English tickets.
2. `hand_check/test_50_review.csv` shows ticket, dataset label, Claude's label and the fields
   that differ, with blank confirm columns.
3. A human reviewer confirmed each row (Y, or N with corrections) after reading the ticket and
   both labels. `scripts/hand_check.py apply` applied the corrections to the test split and wrote
   `hand_check/agreement.json`. Reviewed rows carry `hand_checked: true` in `splits/test.jsonl`,
   and corrected rows also carry `hand_checked_correction` with the fields that changed.

First pass (Claude, blind) against the dataset label:

| field | agreement |
|---|---|
| category | 49/50 (98%) |
| priority | 44/50 (88%) |
| sentiment | 44/50 (88%) |
| needs_human | 50/50 (100%) |
| suggested_action | 49/50 (98%) |
| all five fields | 38/50 (76%) |

All 12 disagreements are boundary calls: low versus medium or medium versus high priority (6),
neutral versus positive or negative sentiment (6), and one ticket (customer subscribed to the
wrong product) read as cancellation instead of other. This is the expected noise level for
priority and sentiment, and it caps how high any system can score on those two fields.

### Final result (human review)
The human reviewer confirmed the dataset label on **41 of 50 rows (82%)** and corrected 9.

| field | dataset label correct | Claude first pass matches final |
|---|---|---|
| category | 49/50 (98%) | 50/50 (100%) |
| priority | 45/50 (90%) | 49/50 (98%) |
| sentiment | 46/50 (92%) | 48/50 (96%) |
| needs_human | 50/50 (100%) | 50/50 (100%) |
| suggested_action | 49/50 (98%) | 50/50 (100%) |
| all five fields | 41/50 (82%) | |

Corrections: priority raised to high on 3 tickets (a double charge, and two "no signal for days"
tickets), priority raised from low to medium on 1 price check, sentiment changed on 4 tickets
(1 to positive, 3 to neutral), and t00047 (subscribed to the wrong product by mistake) relabelled
from other / low / reply_with_kb_article to cancellation / medium / ask_for_details. All 9
corrections agreed with the blind first pass; on the other 3 first pass disagreements the
reviewer kept the dataset label.

What this means: about 1 in 5 sampled labels needed a fix, almost all on the fuzzy priority and
sentiment boundaries; needs_human was right every time. The 118 test tickets outside the sample
were not hand checked and carry similar noise, so test scores on priority and sentiment have a
ceiling below 100%. Only labels were checked: the reason sentences were not reviewed, and the
reason of t00047 still describes the original "wrong company" label (reason is not scored).

## Known biases and limitations
- **gpt-4o-mini wrote the tickets.** Its phrasing and its idea of a "typical" ticket are built
  into the data, which may favour gpt-4o-mini in the comparison. Sampled labels and the hand check
  reduce this but do not remove it.
- Synthetic tickets are cleaner and more on-topic than real ones, even in the "typos" and
  "rambling" styles. Real-world accuracy will be lower.
- Priority and sentiment have fuzzy boundaries (see hand check). Exact accuracy on them should be
  read with that in mind.
- Each scenario fixes one category and action, so some combinations never appear, for example a
  shipping ticket that needs escalate_to_supervisor.
- Non-English tickets are 15% of the data with 35 to 66 tickets per language.
- Generated text sometimes includes made-up names, addresses and account numbers. They are
  fictional.

## Reproduce
```bash
python scripts/generate_data.py --n 1700 --out data/raw/generated.jsonl
python scripts/dedup_split.py
python scripts/check_splits.py
```
Generation is not byte-for-byte reproducible (gpt-4o-mini at temperature 1.0), but the specs
are: the same seed gives the same labels, products, styles and languages.
