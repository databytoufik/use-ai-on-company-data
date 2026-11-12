# Use AI on company data without uploading it

The AI writes your analysis from a synthetic copy of your file. You run that analysis on the real file on your own computer. The real file never goes to the AI.

The repo includes a practice file of 2,400 made-up expense claims, so you can try it before using your own data.

## Setup (once)

1. Install **Python 3.13** from [python.org](https://www.python.org/downloads/), not the newest version, which SDV doesn't support yet. On Windows, tick "Add python.exe to PATH".
2. On this page, click **Code > Download ZIP** and unzip it to a folder that isn't synced to OneDrive or iCloud.
3. Open PowerShell in the unzipped folder that contains `make_synthetic_copy.py` and run:

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

On a Mac, use Terminal, `python3` in the first line and `.venv/bin/python` instead of `.venv\Scripts\python` everywhere. The packages take about 1.3 GB.

## Step 1. Make the synthetic copy

```
.venv\Scripts\python make_synthetic_copy.py
```

This runs on the practice file. For your own file, save it from Excel as CSV UTF-8, create a folder called `private`, put it there, and edit the settings at the top of `make_synthetic_copy.py`: the file paths, then your own column names in place of the practice ones (name and ID columns, date columns, columns to keep as they are, columns to drop).

Then run it once and read the column types it prints. **This is the step that keeps real names and IDs out of the copy.** SDV guesses each column's type itself, and on the practice file it got two wrong: it read the name column as an ordinary category and had no pattern for new IDs, so every one of the 200 synthetic rows reused real names and IDs. Every name column should show `name`, and every ID column needs a pattern, such as `E[0-9]{5}`. If a type is wrong, set it in `TYPE_FIXES` and run again.

The script won't save anything until every column is accounted for. Columns that keep their real values (departments, notes, plain counts and so on) must each be listed in `COPY_AS_IS` as fine to share, or in `DROP_COLUMNS`. ID columns need a pattern for new IDs, and number columns with stray text are refused. After generating, it removes any row where a name or ID from your file shows up. Open the copy and look through it before sharing it: category values, how often they appear, and the spread of numbers and dates carry over from the real file.

## Step 2. Give the copy to the AI

Open a chat AI that accepts file uploads, attach **only the synthetic file**, and paste the prompt from [PROMPT.md](PROMPT.md) with your own questions. Download the notebook it writes into the `private` folder.

I tested this with Claude (Sonnet 5.5, Medium effort, paid plan): its notebook matched every expected figure on the practice file. ChatGPT also takes file uploads, but I didn't test it.

## Step 3. Run the notebook on the real file

```
.venv\Scripts\python -m jupyter lab
```

Open the notebook, change `FILE_PATH` in the first code cell to your real file's name (it's in the same folder; for the practice run, `../data/practice_expense_claims.csv`), and run all cells. `example_analysis.ipynb` is the notebook from my test, set to read the practice synthetic file and re-run locally.

## Before you trust it

- Check your company's rules. Some don't allow even a synthetic file or column names to leave.
- Read the notebook before running it, or have someone who can check code do it. It should only read your file and draw charts.
- After it has run on the real file, the notebook contains real rows. Don't upload it, or paste its errors, back into the AI.
- Ignore any figures the AI reports. They come from the synthetic file, and only the code is reused.
- Don't run an AI agent on the computer that has the real file for this. It could open the file.

## Notes

- Tested on Windows 11 with Python 3.13. Not tested on a Mac. SDV does not install on Intel Macs with Python 3.13.
- The synthetic copy is made with [SDV](https://github.com/sdv-dev/SDV), which DataCebo licenses under the Business Source License 1.1 (not open source; it excludes offering SDV as a commercial synthetic-data service). The files in this repo are MIT licensed.
