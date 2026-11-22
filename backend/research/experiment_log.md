# Experiment log

## Phase 0: checking the existing validator and analyzer (10 Nov 2026)

- Objective: check that the metric rules in methodology.md are applied correctly by the code.
- Method: 20 small test cases in tests/test_phase0.py. Expected values were worked out by
  hand before running the tests.
- Result: passed 20 of 20. (Fill in after running. Do not guess.)
- What this does NOT show: that our definitions are good or match other tools. The tests
  only check that the code follows our own rules.
- Notes: ___


## Phase 1: input rules (date: ___)

- Objective: check that unsafe, unsupported, or too-large input is refused or skipped, and
  that good input is read correctly.
- Method: 21 test cases in tests/test_input_manager.py. Expected values decided before running.
- Result: passed 20 of 21 (skipped 1). Fill in after running. Do not guess.
- What this does NOT show: that the rules catch every attack. The tests are the cases we
  thought of. They are not a security audit.
- Notes: ___


## Phase 2: language detection (date: ___)

- Objective: check that the rules in methodology.md section 3 are followed.
- Method: 15 test cases in tests/test_languages.py. Expected values decided before running.
- Result: passed ___ of 15. Fill in after running. Do not guess.
- What this does NOT show: how accurate the detector is on real repositories. That needs a
  set of real projects with known languages. Planned, not done.
- Notes: ___


## Phase 3: code validation (date: ___)

- Objective: check that the rules in methodology.md section 4 are followed.
- Method: 13 test cases in tests/test_validation.py. Expected values decided before running.
  The 20 Phase 0 tests were run again to check the validator rewrite.
- Result: passed ___ of 13. Phase 0 tests passed ___ of 20. Fill in after running. Do not guess.
- What this does NOT show: how many real-world errors we catch or wrongly flag. That needs real
  projects, some with known errors. Planned, not done.
- Notes: ___


## Phase 4a: function, class and documentation metrics, code smells (date: ___)

- Objective: check that the rules in methodology.md section 5 are applied correctly.
- Method: 15 test cases in tests/test_static_analysis.py. Expected values decided by hand
  before running. The 20 Phase 0 tests were run again, because the complexity code was moved.
- Result: passed ___ of 15. Phase 0 tests passed ___ of 20. Fill in after running. Do not guess.
- What this does NOT show: that our complexity numbers match other tools, or that the smell
  limits are good. Both need real code and a comparison (Experiment A, planned in Phase 4b).
- Notes: ___


## Phase 4b: Ruff and Bandit integration (date: ___)

- Objective: check that tool results are read correctly, mapped to our finding format, and
  that a missing, failing or slow tool does not break the review.
- Method: 14 test cases in tests/test_external_tools.py (9 without tools, 5 with the real tools).
  Expected values decided before running. Tool versions: Ruff ___, Bandit ___.
- Result: passed ___ of 14, skipped ___. Fill in after running. Do not guess.
- What this does NOT show: how good the findings are. We have not measured how many are
  false alarms or how many real problems are missed. That needs real projects and human
  checking. Planned, not done.
- Notes: ___


## Phase 4c: duplicate code (date: ___)

- Objective: check that the rules in methodology.md section 7 are followed.
- Method: 12 test cases in tests/test_duplication.py. Expected values worked out by hand before running.
- Result: passed ___ of 12. Fill in after running. Do not guess.
- What this does NOT show: how many real duplicates we find or miss. Needs real projects and human checking.

## Experiment A: our complexity vs Radon (date: ___)

- Objective: see how far our per-function cyclomatic complexity is from Radon's.
- Method: python -m analyzer.evaluation.radon_comparison on these folders: ___
  Radon version: ___. Our metrics version: ___.
- Result: (paste the printed numbers. Do not rewrite them)
- Reasons for the biggest differences (checked by reading the code): ___
- Limits: ___

python -m analyzer.evaluation.radon_comparison "$lib\email" --json research/radon_email.json
Radon version: 6.0.1   Our metrics version: python-static-0.1
Files compared: 28   Functions matched: 530
Only in our result: 0   Only in Radon: 0   Radon errors: 0
Exact match: 509 (96.0%)
Within 1: 527 (99.4%)
Mean absolute difference: 0.05
Mean difference (ours - Radon): -0.05
Ours higher: 0   Ours lower: 21
Largest difference: 3

Biggest differences (top 10):
  _header_value_parser.py:2442 get_parameter  ours=45 radon=48
  header.py:503 _ValueFormatter._append_chunk  ours=11 radon=13
  message.py:104 _decode_uu  ours=8 radon=10
  _header_value_parser.py:445 AngleAddr.addr_spec ours=4 radon=5
  _header_value_parser.py:743 MimeParameters.params  ours=16 radon=17
  _header_value_parser.py:1014 _get_ptext_to_endchars  ours=6 radon=7
  _header_value_parser.py:1105 get_unstructured  ours=13 radon=14
  _header_value_parser.py:2152 parse_message_id  ours=3 radon=4
  _header_value_parser.py:2737 parse_content_transfer_encoding_header  ours=6 radon=7
  charset.py:245 Charset.get_body_encoding  ours=3 radon=4

Saved to research/radon_email.json


## Phase 5: feature extraction (date: ___)

- Objective: check that features are built as defined in methodology.md section 9, that missing
  values stay missing, and that every row follows the schema.
- Method: 13 test cases in tests/test_features.py. Expected values worked out by hand before running.
- Result: passed ___ of 13. Fill in after running. Do not guess.
- What this does NOT show: that the features are useful. Whether they relate to real quality
  problems is a Phase 7 question and needs labelled data.
- Notes: ___


## Phase 6: AI review engine (date: ___)

- Objective: check that answers are read safely, that invented lines are caught, that service
  errors do not break the review, and that limits work.
- Method: 21 test cases in tests/test_ai_engine.py, with a fake AI service (no network).
  Expected values decided before running.
- Result: passed ___ of 21. Fill in after running. Do not guess.
- What this does NOT show: anything about the quality of real AI reviews.

## Experiment B (planned, NOT done): quality of AI reviews

- Plan: pick a small set of real code files. Run the review with one or more models. A person
  judges each kept issue (correct / wrong / unclear, useful or not) and notes real problems that
  were missed. Report: share judged correct, share of dropped issues by reason, per model.
  Each judgement must be recorded with who made it.
- Needs: a file set, a judging sheet, and enough time. Sample size and who judges are not decided.
- Result: none yet.

## Phase 7a: pipeline and research database (date: ___)

- Objective: check that one call runs every step, that data is saved safely and completely, and
  that missing values and AI columns behave as defined in methodology.md section 11.
- Method: 12 test cases (tests/test_pipeline.py, tests/test_data_store.py). Ruff and Bandit were
  switched off in the tests, and a fake AI was used. Expected values worked out by hand.
- Result: passed ___ of 12. Fill in after running. Do not guess.
- What this does NOT show: anything about real code.

## Data Collection Log

**Collection date:** 15-Nov-2026  
**Target project:** `deepfake_detector`  
**Collection database:** `data/research.db`

| Date | Project name | Source (own / public repo) | Permission or licence | Files | Analysed | Notes |
|---|---|---|---|---:|---:|---|
| 15-Nov-2026 | `deepfake_detector` (initial whole-project run) | Own | Own project; verify third-party components separately | 19 | 16 | AI-assisted run; 80 issues reported; run ID `65b0ae8c73a3` |
| 15-Nov-2026 | `backend` | Own | Own project; verify third-party components separately | 6 | 6 | 20 issues; run IDs `0de05d2b9c21`, `9e06fe9cbecd` |
| 15-Nov-2026 | `data` | Own | Own project; verify third-party components separately | 2 | 2 | 15 issues; run IDs `98387d8800c9`, `273f2d534e0a` |
| 15-Nov-2026 | `frontend` | Own | Own project; verify third-party components separately | 3 | 0 | Files found but none analysed; run IDs `be6cc554cb75`, `efe5eb4dcdf0` |
| 15-Nov-2026 | `models` | Own | Own project; verify third-party components separately | 5 | 5 | 21 issues; run IDs `9d12a47cbb7a`, `51c07e8ecb30` |
| 15-Nov-2026 | `training` | Own | Own project; verify third-party components separately | 3 | 3 | 24 issues; run IDs `20ebbc481db8`, `68af54d3d3d7` |
| 15-Nov-2026 | `logs` | Own | Own project | 0 | 0 | Skipped: no supported source files found |
| 15-Nov-2026 | `notebooks` | Own | Own project | 0 | 0 | Skipped: no supported source files found |

> **Counting note:** The initial whole-project run and the later subfolder runs overlap. Do not add their file counts together as if they were independent files. The final collection summary reported 57 file records, 48 analysed records, 19 distinct file contents, and 38 repeated-content records.

## Collection commands

### 1. Initial whole-project AI collection

```powershell
python -m data_science.collect D:\\COLLEGE\\SEM6\\MinorProjectII\\deepfake_detector --ai --yes
```

- Provider: `openai_compatible`
- Model recorded in terminal: `llama-3.3-70b-versatile`
- Files: 19
- Analysed: 16
- Issues reported: 80
- Run ID: `65b0ae8c73a3`

### 2. AI collection by subfolder

```powershell
python -m data_science.collect D:\\COLLEGE\\SEM6\\MinorProjectII\\deepfake_detector --each-subfolder --ai --yes
```

The command reported:

| Subfolder | Files | Analysed | Issues reported |
|---|---:|---:|---:|
| `backend` | 6 | 6 | 20 |
| `data` | 2 | 2 | 15 |
| `frontend` | 3 | 0 | 0 |
| `models` | 5 | 5 | 21 |
| `training` | 3 | 3 | 24 |
| `logs` | Skipped | — | — |
| `notebooks` | Skipped | — | — |

### 3. Subfolder collection without AI

```powershell
python -m data_science.collect D:\\COLLEGE\\SEM6\\MinorProjectII\\deepfake_detector --each-subfolder
```

The command created another set of five collection runs for the supported subfolders.

### Final database summary

| Metric | Value |
|---|---:|
| Total runs | 11 |
| Projects recorded | 6 |
| File records | 57 |
| Analysed file records | 48 |
| Not analysed file records | 9 |
| Distinct file contents | 19 |
| Repeated-content records | 38 |
| Analysis coverage | 84.21% |


## Phase 7b: analysis tools (date: ___)

- Objective: check that the statistics code gives the values worked out by hand, and that the
  report runs end to end.
- Method: 18 test cases (tests/test_eda.py, tests/test_plots_and_report.py). Expected values
  worked out by hand: quantiles, outlier limits, Spearman 0.8 on a 5-point example, the exact
  Mann-Whitney p of 0.1, Kruskal-Wallis H of 7.2.
- Result: passed ___ of 18. Fill in after running. Do not guess.
- What this does NOT show: anything about real code. The tests use tiny hand-made tables.

## Exploratory analysis run 1 (NOT done yet)

- Database: ___ (runs ___, projects ___, files used for statistics ___)
- Seed ___, resamples ___. Library versions: copy from report.md.
- What the numbers show (only what the report shows; mark by_design pairs):
- Surprises, checked by reading the code of the files concerned:
- Limits for this run (few projects? mixed thresholds?):


## Phase 1b: API (date: ___)

- Objective: check that the API follows the contract and that limits and errors behave as defined.
- Method: 19 test cases in tests/test_api.py (fake AI, Ruff and Bandit off). Then a manual run with
  the VEDIX frontend on: ___ (project name, number of files).
- Result: passed ___ of 19. Manual run, what VEDIX showed: ___ (write what you saw, not what you expected).
- What this does NOT show: behaviour under many users, or on slow networks.


## Experiment tools (date: ___)

- Objective: check that sampling, sheets, scoring and agreement are computed as defined.
- Method: 12 test cases in tests/test_judging.py. Expected values worked out by hand (Wilson
  intervals, kappa 0.6, counts).
- Result: passed ___ of 12. Fill in after running. Do not guess.
- What this does NOT show: anything about the quality of real findings.

## Experiment A run (date: ___)

- Folders: ___ . Radon version: ___ . Metrics version: ___ .
- Printed result: (paste, do not rewrite)
- Biggest differences, after reading the code of those functions: ___
- Limits: stdlib code is not student code.

## Experiment B run (date: ___)

- Projects (name, where from, permission): ___ . Files: ___ .
- Settings: per-source ___, seed ___, AI provider and model ___, prompt version ___ .
- Judges (initials, experience): ___ . Time spent: ___ .
- Printed result: (paste, do not rewrite)
- Kappa: ___ on ___ items. Raw agreement: ___ .
- Things judges said in "notes" that matter: ___
- Limits for this run: ___


## Step 7d: history and recommendation tools (date: ___)

- Objective: check that run metrics, comparability rules, run comparison, trends and
  recommendations are computed as defined.
- Method: 11 test cases (tests/test_history.py, test_recommendations.py, test_profile_report.py).
  Expected values worked out by hand (weighted duplication 12.0, smells per 100 lines 10.0 and 50.0,
  finding counts 3 persistent / 1 resolved / 1 new).
- Result: passed ___ of 11. Fill in after running. Do not guess.
- What this does NOT show: anything about real projects or about the advice.

## History run 1 (NOT done yet)

- Projects (name, where from, permission) and how many runs each: ___
- Settings kept the same between runs? (thresholds, Ruff / Bandit / Radon versions): ___
- What changed in the code between runs (from your own notes, not from the numbers): ___
- Printed result: (paste, do not rewrite)
- Metrics marked "not comparable" and why: ___
- Limits for this run: ___