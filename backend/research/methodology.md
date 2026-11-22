# Methodology

Status: describes the code as of 10 Nov 2026 (Phase 0). Updated every phase.

## 1. Static metrics for Python (our own counting rules)

These are OUR definitions. They are simple on purpose. They are not the only correct
definitions and may give different numbers than other tools.

| Metric | How we count it |
|---|---|
| total_lines | Lines in the file. Only LF, CRLF and CR end a line. A final line ending adds no empty line. |
| blank_lines | Lines with only spaces or tabs. |
| comment_lines | Lines whose first non-space character is "#". |
| code_lines | total_lines - blank_lines - comment_lines. Docstring lines count as code lines. |
| functions | Every "def" and "async def", including methods and inner functions. Lambdas are not counted. |
| classes | Every "class". |
| imports | Every name imported. "import os, sys" counts as 2. |
| variables | Different simple names that are assigned anywhere in the file, in any scope. Attributes like "self.x" are not counted. |
| cyclomatic_complexity | 1 + decision points for the WHOLE FILE (not per function yet). |
| max_nesting_depth | Deepest level of if / for / while / try / with blocks. Functions and classes add no depth. |

Decision points: each "if" and "elif", "for", "while", "except", ternary expression,
each extra operand of "and"/"or", each loop in a comprehension, each "if" in a comprehension.

## 2. Known limits (we do not hide them)

- A line starting with "#" inside a multi-line string is counted as a comment line.
- "else:" followed by a single "if" is treated like "elif" for nesting depth.
- Complexity is for the whole file. Per-function complexity comes in Phase 4.
- "match" statements are not counted yet.
- Variable counting merges the same name used in different functions.

## 3. Not done yet

- Comparing our numbers with Radon on the same files (Experiment A).
- Choosing and justifying thresholds for code smells.


## 2. Input rules (Phase 1)

Every way of giving code (one file, many files, a local folder) is turned into the same list
of (path, bytes). Then ONE set of checks is applied. This keeps the rules in one place.
The backend never trusts the browser, so it repeats the checks the browser already did.

| Rule | Value |
|---|---|
| Largest single file | 2 MB |
| Most source files per project | 500 |
| Largest project (accepted files together) | 25 MB |
| Files looked at when scanning a local folder | 20,000 |
| Text format | UTF-8 (a leading BOM is removed). Files with a null byte count as binary |
| Ignored folders | node_modules, .git, build output, virtual environments, tool caches |
| Paths | Only "/" is used. Absolute paths, "..", and control characters are refused |
| Symbolic links | Never followed. The file or folder is skipped |

A skipped file is not an error. It is listed with a reason (only the first 200 are named,
all are counted). A project with NO usable file, or one that breaks the count or size limits,
is refused with a clear message.

Limits of this design: only 19 file extensions are read. Non-UTF-8 text files are skipped.
Nothing from the uploaded code is ever executed.


## 3. Language detection (Phase 2)

Order of checks for each file:
1. File extension (case-insensitive). 19 extensions map to 11 languages.
2. ".h" files are ambiguous (C or C++). We look for C++ words (class, namespace, template,
   std::, some C++ headers, public:/private:). If none are found, we say C.
3. If the extension is not known, a first line like "#!/usr/bin/env python3" can decide.
   Only Python, Node, ts-node and PHP are recognized this way.
4. Otherwise the language is "unknown".

Project language mix: for each language we count files and NON-BLANK lines (comments included).
Percentage = language lines / all lines. If all lines are blank, files are used instead.
Primary language = most lines; tie: more files; tie: alphabetical id.

Limits: extension is trusted over content (except ".h"). The ".h" rule is a guess.
Lines are a size measure, not a quality measure. A language with many comment lines or
long generated files can look bigger than its real share of the work.


## 4. Code validation (Phase 3)

We check each file in stages and keep the stage in the result:
1. syntax: can Python read the code? (the parser, ast.parse)
2. compile: does Python accept the whole program? (compile, which builds code but never runs it)
3. dependency: for Python files that passed 1 and 2, do imports that point inside the project
   find a file? Standard library and outside packages are only listed. They are not checked.

Result of a file: "valid", "invalid" or "not_checked". Only errors make a file invalid.
Warnings (such as a missing local module) do not. Languages without a validator are
"not_checked". They are never reported as valid.

We never run uploaded code. Runtime errors are therefore not detected.

Limits: Python only. One error per file. Imports from outside the project are not verified.
Local import checks can be wrong for "src/" layouts or when files were skipped on upload.

Mapping to review findings (used by the API): syntax and compile errors become "high" severity,
category "bug". Unresolved local imports become "medium", category "bug". These choices are
ours. They are not from a standard.


## 5. Function, class and documentation metrics (Phase 4a)

Per function (methods and inner functions included): start line, end line, length (physical
lines from "def" to the last line, blank lines and comments included), parameters (all kinds,
"self" and "cls" not counted in methods), cyclomatic complexity (1 + decision points of the
function's OWN body), max nesting depth, number of returns, number of ternary expressions,
has a docstring.
An inner function is measured on its own and its parent does not count it. Lambdas count toward
the function that contains them.

Per class: start line, end line, length, number of methods, has a docstring.

Documentation coverage = (functions + classes that have a non-empty docstring) / (all functions
+ all classes) * 100. The module docstring is reported separately. A file with nothing to
document has coverage "none", not 0.

Code smells (rule-based). A smell appears when a value is GREATER than its limit:

| Smell | Value checked | Our starting limit |
|---|---|---|
| Long method | function length in lines | 50 |
| Too many parameters | parameters | 5 |
| Deep nesting | max nesting depth | 4 |
| High complexity | cyclomatic complexity of one function | 10 |
| Large class | class length in lines, or number of methods if length is fine | 300 lines, 20 methods |

These limits are our choices. They are not standards and are not proven. They can be
changed and should be tuned and tested on real code.
In the VEDIX findings, a smell is "low" severity, or "medium" if the value is more than double
the limit. Categories: "complexity" for nesting and complexity, "code_smell" for the rest.
A smell is a hint about maintainability, not a confirmed defect.

Every result stores the metrics version ("python-static-0.1") and the limits used, so numbers
from different versions are never mixed.

Not done yet: unused imports, security checks, lint rules (Phase 4b, with established tools);
duplicate code (Phase 4c); comparison of our complexity with Radon on the same files.


## 6. Established tools (Phase 4b)

We use existing tools instead of inventing our own checks for lint and security.

- Ruff, only the "F" rules (Pyflakes family: unused imports and variables, undefined names,
  redefined names, and similar). Config files are ignored, so results do not depend on the
  user's setup.
- Bandit, security checks for Python, all default checks except B101 (assert), because B101
  flags every assert and is noise here.

How we run them: all valid Python files of a project are written to a temporary folder under
safe names (f0001.py, ...). Each tool runs once on that folder, with no shell and a 60-second
limit. Results are mapped back to the original paths. The folder is deleted afterwards.
The analysed code is never run. Tool name and version are saved with every run.

Mapping to review findings: ours, not from the tools.
- Ruff: unused import / variable = "maintainability", low. Undefined name = "bug", high.
  Redefined name, comparing a literal with "is" = "bug", medium. Other rules = "code_smell", low.
  An unused import in __init__.py is ignored, because it is often a re-export.
- Bandit: category "security". Bandit's severity (low/medium/high) is kept as it is. Nothing from
  Bandit is "critical", because a tool cannot confirm that code can be exploited. Bandit's
  confidence and CWE number are shown in the explanation.

Limits: only some Ruff rules are used. Each file is checked alone. Both tools guess:
false positives and missed problems are possible. A "# noqa" or "# nosec" comment in the
code hides a finding. Results can change when a tool is updated.

Not done yet: Pylint (slower, and needs a safe way to run it), duplicate code (Phase 4c),
comparison of our complexity numbers with Radon (Phase 4c).


## 7. Duplicate code (Phase 4c)

Method: token matching on Python files. Comments, blank lines and spacing are removed.
Every other token is kept, including line ends and indentation changes, so block structure counts.
We look at every run of N tokens (N = min_tokens, start value 50). A run that appeared earlier
in the project is a match. Neighbouring matches are joined into one clone. A clone is kept if
it has at least min_tokens tokens, and both copies span at least min_lines lines (start value 5).
These values are our choices, not standards.

A run is compared only with the FIRST place it appeared. A block copied 3 times is reported as
2 clones, each paired with the original. Two copies in the same file cannot overlap.

What is found: identical code that differs only in comments, blank lines, spacing.
What is NOT found: renamed variables, changed numbers or strings, reordered statements, code
that works the same but is written differently. This is not a semantic duplicate detector.

Numbers: a line counts as duplicated if it lies inside a clone, in either copy. Only non-blank
lines are counted (comment lines included).
duplication_ratio = duplicated lines / non-blank lines. Reported per file and for the project.

In review findings: one finding per clone, on the later copy. Category "code_smell". Severity
"low", or "medium" if the copy has 20 lines or more. Our choice.

Limits: Python only. Clones can start or end in the middle of a statement. Projects over
500,000 tokens are skipped. Import blocks and constant tables can be reported.
jscpd (a Node.js tool for many languages) was considered. Not used now, because it needs Node
and a separate process. A comparison with it is possible later.

## 8. Comparing our complexity with Radon (Phase 4c, Experiment A)

Radon is an existing tool that measures cyclomatic complexity per function. Functions are matched
by the line of their "def". We report: how many functions match exactly, how many differ by at most
1, mean absolute difference, mean difference (ours minus Radon), and the largest differences.
Radon is NOT treated as the truth. Two tools can disagree because their counting rules differ.
Differences are explained only after reading the code of the functions concerned.

Limits: functions that exist in only one result are counted and listed, not compared. The result
depends on the code we test on, and on the Radon version, which is saved.


## 9. Feature extraction (Phase 5)

Every analysed file becomes one row of 17 numeric features. Files that could not be analysed
(syntax errors, languages without analysis) also get a row, with an "analysis_status" of
"not_analyzed", a note, and empty features. Row counts therefore match file counts.

| Feature | Origin | Unit | Meaning |
|---|---|---|---|
| loc | own lines | lines | all lines minus blank lines and comment-only lines |
| blank_lines | own lines | lines | lines with only spaces or tabs |
| comment_lines | own lines | lines | lines starting with # |
| functions, classes | own AST | count | functions and methods; classes |
| imports | own AST | count | names imported |
| variables | own AST | count | different simple names assigned in the file |
| avg_function_length, max_function_length | own AST | lines | over the functions of the file |
| avg_cyclomatic_complexity, max_cyclomatic_complexity | own AST | points | over the functions of the file |
| max_nesting_depth | own AST | levels | whole file |
| documentation_coverage | own AST | percent | functions and classes with a docstring |
| duplication_ratio | own duplicate finder | percent | non-blank lines inside a duplicated block |
| code_smells | own rules | count | our five smell rules |
| lint_violations | Ruff | count | F-rule findings |
| security_findings | Bandit | count | findings, except B101 |

Missing values: a number is missing (not 0) when it could not be measured: no functions in the
file, nothing to document, a tool that was not run or failed, a duplicate check that was skipped.
Zero means "measured, nothing found". Mixing the two would give wrong statistics.

Origin: every feature records where it comes from. Numbers from our own code, from Ruff and from
Bandit are never merged. Labels from the AI review (Phase 6) will be stored in a separate table.

Run record: each extraction has a run id and a record with the tool versions, the version of our
metric rules, the smell thresholds, the duplicate-check settings, the Python version and the time.
Rows point to it with the run id.

Identifiers: file id (project id + path) and a SHA-256 hash of the file content. The hash will be
used to keep identical files out of both the training and test set.

Not stored: the source code itself.

Limits: function features do not cover code outside functions. Averages ignore function size.
Lint and security counts cover only the rules we chose. The features describe code. They are not
shown to measure quality. No quality score is defined yet.


## 10. AI review engine (Phase 6)

An AI model reads one file at a time and returns issues as JSON. For each file it gets: the file
with line numbers, the Python errors found by the validator, a short list of problems our other
checks already found ("do not repeat these"), and a few static numbers.
The provider and model are settings (any service with an OpenAI-style endpoint, or Anthropic).
The prompt text has a version number. Provider, model and prompt version are saved with every review.

We treat the AI answer as untrusted:
- Only a strict JSON shape is accepted. Severity and category are checked. Text is cut to length.
- Every issue must give a line number and a quote of that line. If the quote is on that line, the
  issue is kept. If it is in exactly one other place, the issue moves there. Otherwise it is dropped
  and counted ("unverified_line"). The code shown as "before" is read from the file, never from
  the answer.
- Severity "critical" is lowered to "high". A model cannot confirm that code can be exploited.
- An issue on the same line and category as an issue we already have is dropped ("duplicate").
- At most 15 issues per file are kept ("too_many" counts the rest).

The reviewed code is given to the model as data, with a rule never to follow instructions found in it.
This reduces prompt injection. It does not remove it.

Limits per review: 8 files, 30,000 characters per file, 150 seconds. Files with errors go first,
then files with the most known issues. Two service errors in a row stop the review.

What we record for each review (kept even when we drop issues): files reviewed, failed and skipped
with reasons, issues kept, issues dropped by reason, provider, model and prompt version.
The share of "unverified_line" drops is a simple, measurable sign of how often a model invents
line numbers.

What this does NOT measure: whether the issues kept are correct, useful or complete. That needs
human judgement (Experiment B, below). A verified line only means the code exists there.

Limits: one file at a time, no cross-file context. Output is not deterministic. Confidence is
reported by the model and is not calibrated. Uploaded code is sent to a third-party service.

## 11. Dataset construction (Phase 7a)

One review run = one record. Runs are never overwritten, so the history of a project is kept.
Data is saved in four tables (SQLite file):
- runs: run id, project name, time, versions (schema, metric rules, Python), smell thresholds,
  tool versions and status, duplicate-check settings, AI provider / model / prompt version / counts.
- file_features: one row per file per run, the 17 features of section 9.
- findings: one row per issue found: file, line, severity, category, source (validation, static,
  ruff, bandit, duplication, ai), rule, title, confidence.
- file_ai: whether the AI reviewed each file.

Not stored: source code, and the explanation or suggestion texts.
Stored: file paths and project names, because they identify the data. They can contain personal
information. Only own projects, or projects whose licence and owner allow it, are collected.

Quality rules: rows are checked against the schema before saving. Nothing is saved if one row is wrong.
A run cannot be saved twice. A database made with another schema version is refused.

Missing values: a missing number stays missing in the database (not 0). The AI columns (counts per
category and severity) are 0 when the AI reviewed a file and found nothing, and missing when the AI
did not review the file. AI columns are always named "ai_..." and are never merged into the static features.

Identity: a file is identified by its content hash. A project is identified only by its name for now,
which is weak. The same project collected twice is counted as two projects.

Collected data (fill in honestly: project, where it comes from, permission or licence, date, files, analysed files):
(none yet)

Not done: exploratory analysis, statistics, labels, models.


## 12. Exploratory analysis and statistics (Phase 7b)

Unit of analysis: one file. Only files that were analysed are used. Each file content (SHA-256)
is counted once, even if it was reviewed several times or appears in several projects. If the
same content has several rows, the row with the most measured features is kept.

Size control: counts (code smells, lint violations, security findings) grow with file size.
We also use "per 100 code lines" versions. Files with 0 or unknown code lines have no
per-100-lines value. loc is not used as a predictor for those columns because it is inside them.

Descriptive statistics: n, share missing, mean, sample standard deviation, quartiles, min, max,
skewness. Outliers: Tukey's rule (1.5 times the interquartile range). When most values are 0
the interquartile range is 0 and every non-zero value is flagged. This is reported.

Correlation: Spearman's rank correlation, because counts are skewed and have many ties.
The pairs are fixed in advance: 11 features against 3 counts, and 10 features against 3 densities
(63 pairs). Each pair gets a 95% interval: whole projects are resampled with replacement
(1000 times, fixed seed), the correlation is computed each time, and the 2.5th and 97.5th
percentiles are taken. Reason: files of one project are not independent. A normal interval
that ignores this would be too narrow. With fewer than 10 projects no interval is given.
Intervals are not corrected for the number of pairs. Results are exploratory.

Circular pairs: the smell rules read max function length, max cyclomatic complexity and max
nesting depth. A link between these features and the smell count is true by construction.
These pairs are marked "by_design" and are not read as findings.
This matters for RQ2: only the other features (for example documentation coverage, duplication,
function count, imports) can tell us something not already built into the rules.

Group comparison: Mann-Whitney U (2 groups) or Kruskal-Wallis H (3 or more), both rank-based.
Groups with fewer than 5 files are left out and listed. The p-value treats files as
independent, so it is too optimistic. The result carries this warning.
Only Python files are analysed, so there is nothing to compare between languages yet.

Output (python -m data_science.report): tables (CSV), figures (PNG) and report.md with numbers
and warnings, no interpretation. At least 30 files are needed for correlations and group tests.
Library versions and the seed are written into the report.

Limits: Spearman sees monotone links only. Many pairs are checked without correction. A
bootstrap over about 10 projects is rough. Results depend on our own metric definitions and
thresholds. A correlation is not a cause. Python only.

Findings: (none yet. Fill in only from report.md, after reading the code behind any result.)



## 13. API and privacy (Phase 1b)

The web interface (VEDIX) talks to the backend through a small HTTP API. A review is a background
job: the client sends the files, gets an id, and asks for the result until it is done.

Privacy: uploaded code is kept in memory only, for one hour. The API does not write code or results
to disk. It does not save anything in the research database. Research data is collected only by a
separate, deliberate command (data_science.collect).
AI review sends code to a third-party service. It runs only if the server has a provider set up and
the request asks for it (or the server owner turned it on by default for their own computer).

Limits: 30 MB per request, 500 accepted files, 2 MB per file, 4 analyses at the same time.
Other languages can be uploaded, but only Python is analysed by our own checks.

Not done: sign-in, per-user limits, HTTPS, fetching code from GitHub. The API is meant for use on
one computer. It must not be put on the internet before these exist.




## 14. Human judging of findings (Experiment B)

Question: how often are the findings of each source correct and useful?

Sources: our own rule checks (validator, smells, duplicates), Ruff, Bandit, and the AI review.

Sampling: all findings of the chosen projects are collected. For each source, up to 30 findings
are drawn at random with a fixed seed. The order is shuffled so it does not show the source.

Blinding: judges get a sheet with the code around each finding, title, explanation, suggestion,
severity and category. The source, rule and model are hidden (they are in a key file kept by the
researcher). Blinding is imperfect: AI text reads differently.

Questions per finding (see research/judging_guide.md):
- correct: yes / no / unsure. Is the described problem really there? (facts only)
- useful: yes / no. Would a developer act on it?
- severity_fit: right / too_high / too_low.
Two judges work alone. Rows with a changed file or line, unknown ids, duplicate ids, or invalid
answers are counted and left out.

Statistics, per source and per judge:
- correct rate = yes / judged. "Unsure" counts as not correct. Also given: yes / (yes + no).
- 95% Wilson interval for correct rate and useful rate. It assumes independent items, which is
  not true for findings in one file, so it is too narrow.
- Agreement of two judges on "correct": Cohen's kappa on the items both judged.

Results are written only from the output of the scoring command. Names of judges, number of
items, and number of projects are reported with them.

Limits: small samples (wide intervals); items not independent; imperfect blinding; "correct"
depends on the judge; no measure of missed problems; one model and prompt version; only own
projects, which are not a random sample of code.



## 15. History and recommendations (Step 7d)

Question (RQ4): can repeated reviews of the same projects show recurring problems and weak areas,
and support advice?

Project identity: the folder name. The same folder collected again counts as the same project.

Project-level numbers per run (analysed files only): code lines; smells per 100 code lines;
Ruff findings per 100 code lines; Bandit findings; share of non-blank lines that are duplicated
(weighted by file size); mean documentation coverage; highest function complexity. A number is
missing (not 0) when any analysed file lacks it, for example when a tool did not run.

Comparing runs: a metric is compared between two runs only if both measured it the same way:
same metric rules; same smell thresholds (smells); same tool, status "ok" and version (Ruff, Bandit);
same duplicate-check version and settings (duplication). Otherwise it is marked "not comparable"
and no change is given.

Change between two runs: files are unchanged, changed (same path, different content hash), added or
removed. For files that changed and were analysed in both runs, before and after values of smells,
code lines, complexity and nesting are listed. Findings are counted per file and rule (not per line)
and only for files present in both runs: persistent = smaller of the two counts, resolved = fewer now,
new = more now. Findings in added or removed files are counted separately. AI findings are never used
because they differ from run to run. Trends compare the first and last run of a project.

Recommendations: the latest run of each project is checked for patterns: five code smell rules,
duplication of 10% or more, documentation coverage under 30%, unused imports (F401), likely mistakes
found by Ruff (F821, F811, F632), Bandit findings, and files Python cannot read. A pattern gives advice
only if the profile has at least 3 projects, the pattern appears in at least 2 of them, and in at least
40% of the projects where it could be measured. A project where the check could not run does not
count for that pattern. These limits are our choices.

What this does NOT show: that a change in a number means better skill; that the advice helps; or
anything about a person, because the data has no developer identity.

Planned test of the advice (Experiment D, not done): review a project, give the advice, review again
after the developer worked on it, and compare with developers who got no advice.

Limits: folder-name identity; added or removed code changes densities; counts per file and rule can
hide a swap of one finding for another; thresholds are not standards; documentation mean is not weighted.