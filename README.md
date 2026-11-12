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

This runs on the practice file. To use your own file:

1. Save it from Excel as CSV UTF-8, create a folder called `private`, and put it there.
2. Edit the settings at the top of `make_synthetic_copy.py`. The column names in them belong to the practice file, so replace each one with yours or remove it (`[]` for an empty list, `{}` for an empty `TYPE_FIXES`):
   - `REAL_FILE` and `SYNTHETIC_FILE`: your file and the copy, both in `private`.
   - `DROP_COLUMNS`: columns your questions don't need, such as free-text notes. Drop any other personal column too, like addresses or birth dates, unless your questions need it.
   - `TYPE_FIXES`: every column with people's names set to `name`, and every ID column set to `id` with a pattern, such as `X[0-9]{5}` (an X and five digits). Pick a prefix your real IDs don't use.
   - `COPY_AS_IS`: category columns and whole-number counts whose values are fine to share, such as departments or quantities. Never names, emails or IDs: their real values would be copied.
   - `SENSITIVE`: any other text column whose real values must not appear in the copy. Name, email and ID columns are checked anyway, once the type table shows them as `name`, `email` or `id`.
   - `DATE_COLUMNS` and `DATE_FORMAT`: every date column, and how the dates are written, such as `"%d/%m/%Y"` for 31/12/2026. `DATE_ORDER`: pairs that must stay in order, such as submitted before decided (`DATE_ORDER = []` if there are none).
   - `ROWS`: how many synthetic rows to make (200 by default).
3. Run it. If it stops, the message says what to change.
4. Read the column table it prints. Names must show `name`, emails `email`, and IDs `id` with a pattern. If a line is wrong, fix it in `TYPE_FIXES` and run again.
5. Open the copy and look through it before sharing it.

Don't skip step 4. SDV guesses each column's type itself. In a test with SDV alone and no fixes, it read the practice file's names as an ordinary category and gave the employee IDs no pattern, so all 200 synthetic rows contained real names and employee IDs. The script stops in both of those cases, but it can't tell whether a category column holds names: if you list it in `COPY_AS_IS`, it copies them. The type table is where you catch that.

The script also stops on category and whole-number columns until you decide each one, on ID columns without a pattern, and on number columns with stray text. After generating, it removes rows where a value from your file shows up in a column typed as a name, email or ID, or listed in `SENSITIVE`, and saves nothing if more than 5% of rows do. It doesn't check whether generated dates match real ones, and number columns get only a rough check. Category values, roughly how often each appears, and the spread of numbers and dates carry over from the real file, so share the copy only if that's allowed.

## Step 2. Give the copy to the AI

Open a chat AI that accepts file uploads, attach **only the synthetic file**, and paste the prompt from [PROMPT.md](PROMPT.md). Change its file name, questions, limits and checks to fit your file. Download the notebook it writes into the `private` folder.

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
