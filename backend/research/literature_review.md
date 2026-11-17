# Literature review table

Source: abstracts and catalogue records, checked 15 Nov 2026. Not read in full.
"not checked" means I have not seen it. The last column is my own view.

| # | Paper | Research problem | Method | Dataset | Findings (from abstract) | Limits | Relevance (my view) |
|---|---|---|---|---|---|---|---|
| 1 | Tufano & Bavota 2025 | Overview of code review automation | SLR of 119 papers | list of 32+ tools and datasets (not checked) | Task categories, techniques, datasets, metrics, limits | Preprint | Background for the review of related work |
| 2 | Naik et al. 2025 (CRScore) | Judging review comments without a human reference | Reference-free metric using LLM and static analyzer pseudo-references | CodeReviewer dataset, human-annotated scores | A metric that follows human judgement better than reference-based ones | Numbers not confirmed | Model for how to evaluate our AI review (Experiment B) |
| 3 | Alomari et al. 2025 (SmellyCode++) | Multi-label smell data | Dataset of text and metrics | 107,554 samples, 4 smells, Java | F1 per smell (see abstract) | Java (check Python), project count unverified | Shows how smell data is built. Not directly usable for Python |
| 4 | Ho et al. 2025 (EnseSmells) | Smell detection by deep learning | Embeddings from pre-trained models plus structural metrics | MLCQ | Gains of 5.98 to 28.26% over earlier methods on 4 smells | Deep model, not interpretable | Shows the value of combining metrics and semantics |
| 5 | Zaidi et al. 2025 | Review of ML for defect prediction | Literature review | not checked | Trends combining deep learning and ensembles | Review only | Background for ML choices |
| 6 | Grattan et al. 2024 | Defect prediction outputs are not informative | SLR, 132 of 861 papers | none | Outputs often miss type, severity, cause | Review only | Supports explaining findings, not one label |
| 7 | Alomari et al. 2026 | LLMs for code quality | SLR of 49 studies to Sep 2024 | none | Refactoring most common, LLM refactoring unreliable | Review only | Supports treating AI output as untrusted |
| 8 | Fudholi & Capiluppi 2026 | AI for code understanding | Mapping study, 4 RQs | study list on Zenodo | not checked | not checked | Background |
| 9 | Daza et al. 2025 | Industrial defect prediction | Systematic review | NASA datasets such as PC3, PC4 are mentioned | not checked | not checked | Background |
| 10 | Goyal 2025 | Class imbalance in defect prediction | SLR 2000-2025, PRISMA | not checked | Overview of sampling and ensemble methods | Review only | Needed if we train a model on imbalanced labels |

## Gaps seen so far (not a claim of novelty)

- No verified Python-labelled smell dataset among the 10 papers.
- Novelty of "static metrics + AI review + history" is NOT checked. Targeted search needed.