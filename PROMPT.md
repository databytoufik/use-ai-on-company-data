# The prompt

Attach only the synthetic file, then paste this. Change the file name, the questions and the limits to yours.

```text
Context
The attached practice_expense_claims_synthetic.csv is a synthetic stand-in for a
confidential file. Column names and types match the real file. The values are generated,
so don't draw conclusions from them or build logic around patterns you see in them.

Questions
1. Total approved spend per department.
2. Rejection rate per category = rejected / (approved + rejected).
3. Number of claims above their category's policy limit
   (Travel 1500, Meals 75, Software 500, Equipment 1200, Office Supplies 200).

How to build it
- Write a Jupyter notebook. First code cell: FILE_PATH, the only line I should need
  to change for the real file.
- Validate before analysing: report missing values, values of the wrong type, unexpected
  categories and decisions dated before submission, with a row count for each problem.
  Keep every row. Mark problem rows instead of removing them.
- Under each answer, state in one line how it is calculated and how many rows it used.
- Use only pandas and Plotly, with short comments for a non-programmer.
- The notebook must only read FILE_PATH: no other files, no writing files, no internet.

Deliverable
- The notebook as a downloadable .ipynb file.
```

`example_analysis.ipynb` came from this prompt before its last rule ("must only read FILE_PATH") was added. That notebook already met it.

If you know the allowed values for a column (your list of departments, for example), add them under Questions. The notebook can only warn about values it knows are wrong.
