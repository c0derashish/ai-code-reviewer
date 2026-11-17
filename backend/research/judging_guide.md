# Judging guide

You will see a table of findings from a code review tool. Some were made by people-written
rules, some by tools, some by an AI. You are not told which. Please do not try to find out.

For each row:
1. Read the code under "code_context". The line marked with > is the place of the finding.
2. Fill three columns:
   - correct: yes, no or unsure.
     yes = the problem described is really in the code at or right next to that line.
     no = it is not there, or the description is wrong.
     unsure = you cannot tell. Say why in "notes".
     Judge facts only. Do not judge whether you like the advice.
   - useful: yes or no.
     yes = a developer would want to know about this and would act on it.
     no = trivial, noise, or not worth a change. A finding can be correct and still not useful.
   - severity_fit: right, too_high or too_low.
     Compare the "severity" column with how serious this really is.
3. Write your name or initials in "judge". Add short remarks in "notes" if useful.

Rules:
- Work alone. Do not discuss rows with the other judge until both of you are done.
- Do not open the key file.
- If you cannot answer "useful" or "severity_fit", leave it empty. Do not guess.
- Do not change item_id, file_path or line. Rows that were changed are left out.
- Do not add or remove rows.
- Expect 1 to 2 minutes per row (an estimate, not measured).

Keep the sheet private. It contains pieces of source code.