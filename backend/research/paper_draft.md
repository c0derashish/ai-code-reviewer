# A Data-Driven Framework for AI-Assisted Code Review and Software Quality Assessment

Working title. DRAFT. Not for submission.
Tags: [WRITTEN] stays if the facts hold. [TODO-RESULT] needs numbers from results.md.
[TODO-CHECK] needs a source or a decision.

## Abstract [TODO-RESULT]

Fill this in LAST, from results.md. One sentence each:
1. Problem: developers get little detailed feedback on code quality.
2. What we built: a pipeline that combines static checks, an AI review and review history (Python only).
3. How we evaluated it: [number] projects, [number] findings judged by [number] people.
4. Main results: [only numbers that exist, with intervals].
5. Limits: [one sentence].
Do not write a result here that is not in results.md.

Keywords: code review, static analysis, large language models, software quality, code smells

## 1. Introduction [WRITTEN, check facts]

Developers, and students in particular, often get little detailed feedback on their code. Static
analysis tools give many warnings, and many are not useful. Large language models can explain
problems in words, but they can be wrong and can invent details [7]. [TODO-CHECK: add a source that
LLM review comments can be wrong.]

We built a code review pipeline for Python that (1) runs checks that read the code (validation,
metrics, smell rules, Ruff, Bandit, a duplicate finder), (2) asks an AI model for a review, and
(3) stores every review so that later reviews of the same project can be compared.

We make five modest contributions:
1. An open pipeline that keeps the findings of each source apart. [TODO-CHECK: repository link]
2. A check that ties each AI finding to a real line of code, and counts the findings it cannot tie.
3. Rules for when two reviews can be compared (same rules, thresholds, tool versions).
4. A toolkit to build a dataset from reviews and to analyse it.
5. An evaluation: [TODO-RESULT].

We do NOT claim a new detection algorithm, a validated quality score, or that our advice improves
a developer's skill.

## 2. Background [WRITTEN]

2.1 Cyclomatic complexity. McCabe [15] defined a measure of the paths through a function and
suggested 10 as a reasonable limit. We count 1 + the number of decision points per function.
This matches McCabe's measure for structured code with one exit. It may differ from other tools.
2.2 Code smells: signs of design problems, for example long methods. [TODO-CHECK: one source.]
2.3 AI review: a model reads code and writes comments. Studies report that code refactored by
LLMs is not always reliable [7]. So we treat AI output as untrusted.

## 3. Related work [WRITTEN from abstracts only. Read the full texts before submitting.]

3.1 Automated code review. A literature review covers 119 papers on automating code review [1].
CRScore [2] scores review comments without a human-written reference. It uses claims and issues
found by LLMs and static analyzers. We did not implement CRScore.
3.2 Code smell detection. SmellyCode++ [3] is a multi-label dataset with 107,554 samples for four
smells. It is a Java dataset. [TODO-CHECK: Python coverage] EnseSmells [4] combines structural metrics
with embeddings of pre-trained models. A study of four LLMs on nine smells in 30 Java projects found
that combining LLMs with traditional tools by voting improved results for 5 of 9 smells [12].
3.3 Defect prediction. A review argues that predictions should say more than "defective or not"
(for example type and severity) [6]. Other reviews cover ML approaches [5], industrial use [9] and
class imbalance [10].
3.4 LLMs and static analysis. A review of 49 studies on LLMs for code quality finds refactoring
the most common task [7]. A mapping study covers AI for code understanding [8]. A Tencent study
reports that hybrids of LLMs and static analysis remove most false positives [13]. CodeQUEST [11]
scores code with an LLM and checks the scores against Pylint, Radon and Bandit.
3.5 Personalised feedback. A classroom study gave students personalised feedback from static
analysis and reports fewer violations than a control group [14].

## 4. Gap and contribution [WRITTEN, wording is careful]

Earlier work combines static analysis and LLMs [11, 12, 13] and gives personalised feedback from
static analysis [14]. In a limited search we did not find one open pipeline that also (a) keeps
the origin of each finding, (b) verifies AI findings against the code, (c) records versions so
reviews can be compared over time, and (d) derives advice from repeated reviews and states how
much evidence stands behind it. Our contribution is this integration and its evaluation.
[TODO-CHECK: repeat the search in IEEE Xplore, ACM DL, Scopus, Google Scholar. Keep the queries
in research/literature_search_log.md. If a paper does all of this, change this section.]

## 5. Research questions [DECISION NEEDED]

RQ1 How can static metrics, AI findings and history be combined in one pipeline while their
    origins stay separate and checkable?
RQ2 How often are the findings of each source correct and useful?
RQ3 Which static features are associated with smells, lint and security findings, and how close
    are our complexity numbers to Radon's?
RQ4 Do repeated reviews show recurring problems that support advice? (descriptive)
RQ5 (conditional) Can ML classify smells from our features? Only with a verified labelled dataset.
    If there is none, delete RQ5 and say why in the limits.

## 6. System [WRITTEN, check against the code before submitting]

Input: files are checked (2 MB per file, 500 files, 25 MB in total, UTF-8 text, no ignored folders).
Languages: 11 are recognised. Python gets all checks. Other languages are listed, and only the AI
can review them.
Validation: syntax, compile, and a check of imports that point inside the project. Code is never run.
Own static checks: per-function length, parameters, complexity, nesting, docstrings, five smell rules.
Tools: Ruff (F rules only) and Bandit (without B101). Duplicates: our own token-based finder.
Features: 17 numbers per file. Missing stays missing (not 0).
AI review: provider-independent. One request per file. The answer is strict JSON. Each finding must
quote its line. A finding whose line cannot be verified is dropped and counted. The maximum severity
is "high".
Data: a SQLite database with four tables. No source code is stored.
History: reviews are compared only for metrics measured the same way.
Advice: rule-based, with limits (3 projects, 2 with the pattern, 40%).
API and interface: a small HTTP API and the VEDIX web interface. [TODO: figure with the architecture]

## 7. Methodology [WRITTEN in research/methodology.md, sections 1-15. Copy the final text here.]

## 8. Experimental setup [TODO-RESULT for the numbers]

Data: [projects, where from, permission, number of files, dates]. Only own projects, or projects
whose owner or licence allows it.
Experiment A: our complexity against Radon on [folders]. Radon version [x].
Experiment B: [n] findings per source, [m] judges, blinded, 3 questions. See methodology section 14.
Experiment C (conditional): [dataset, split by project, metrics].
Experiment D (planned, not done): does the advice help? Needs before/after reviews and a comparison group.

## 9. Results [TODO-RESULT. Only copy numbers from results.md. Nothing else goes here.]

9.1 Dataset description. 9.2 Experiment A. 9.3 Experiment B (correct and useful, with intervals,
and kappa). 9.4 Exploratory analysis (mark by-design pairs). 9.5 History and advice (descriptive).

## 10. Discussion [TODO-RESULT]

Write only after reading the code behind any surprising number. Separate "the data shows" from
"a possible reason".

## 11. Threats to validity [WRITTEN, extend with the real data]

- Our own metric definitions and thresholds are choices. They are not standards.
- Small data, and files of one project are not independent.
- A project is identified by its folder name.
- The AI result holds for one model and one prompt version, and AI output is not deterministic.
- "Correct" depends on the judge. Blinding is imperfect.
- Python only. Own projects are not a random sample of code.
- Results depend on tool versions.
- No measure of problems that were missed.

## 12. Ethics and privacy [WRITTEN]

The AI review sends code to a third-party service. We used only [own projects / projects with
permission]. The research database holds numbers, paths and titles, not source code. File paths and
project names can identify people, so [what we did about it].

## 13. Conclusion and future work [TODO-RESULT]

Future work (honest candidates): other languages, a validated quality score, a controlled test of
the advice, safe fetching of GitHub repositories.

## References (verified, see research/references.md. Number them in order of first use.)