"""Make a synthetic copy of a confidential CSV on your own computer, with SDV.

The synthetic copy keeps the columns, data types and overall patterns of the source file,
but the rows are new. Only the synthetic file goes to the AI.

How to use:
1. Edit the SETTINGS block below.
2. Run it (see README.md for the exact command).
3. Read the column table it prints. If a type is wrong, fix it in TYPE_FIXES and run again.
4. Open the synthetic file and check every column before sharing it.

SDV is made by DataCebo and licensed under the Business Source License 1.1, which is not an
open source license. Its Additional Use Grant allows any use except offering a commercial
"Synthetic Data Service". Questions about your use: billing@datacebo.com.
"""
import os
import warnings

import pandas as pd
from sdv.metadata import Metadata
from sdv.single_table import GaussianCopulaSynthesizer
from sdv.cag import Inequality

# ---------------- SETTINGS ----------------
# The practice file. For your own data, put the file in the "private" folder (Git ignores it)
# and use e.g. REAL_FILE = "private/my_file.csv" and SYNTHETIC_FILE = "private/my_file_synthetic.csv".
REAL_FILE = "data/practice_expense_claims.csv"
SYNTHETIC_FILE = "data/practice_expense_claims_synthetic.csv"   # the only file you share
ROWS = 200                                            # how many synthetic rows to make

DROP_COLUMNS = []                            # columns your questions don't need, such as free-text notes
# Category columns keep their real values in the copy (SDV reuses them). List each one you are
# happy to share as it is. Any other category column stops the script until you list or drop it.
COPY_AS_IS = ["Department", "Category", "Status"]
TYPE_FIXES = {                               # correct any type SDV detected wrongly
    "Employee": {"sdtype": "name"},          # a person's name: replaced with generated names
    # IDs need a pattern. Without one, SDV can reuse the source IDs (the leak check below catches it).
    # E[0-9]{5} means "E followed by 5 digits".
    "Employee ID": {"sdtype": "id", "regex_format": "E[0-9]{5}"},
    "Claim ID": {"sdtype": "id", "regex_format": "CLM-[0-9]{5}"},
}
DATE_ORDER = [("Submitted", "Decided")]      # (earlier, later): keep dates in the right order
DATE_FORMAT = "%Y-%m-%d"                     # how those dates are written in your file. 31/12/2026 is "%d/%m/%Y"
SENSITIVE = ["Employee", "Employee ID", "Claim ID"]   # every name or ID column: must never hold a source value
# -------------------------------------------

warnings.filterwarnings("ignore", message=".*save_to_json.*")  # we don't save metadata: it holds source values
TABLE = "data"   # SDV works with named tables; this is just the internal name for the file's table


def read_csv_any(path):
    """Read a CSV saved by Excel or another tool: UTF-8 or Windows encoding, comma or semicolon.

    Returns the table plus the separator, decimal mark and encoding, so the synthetic copy can be written
    the same way. Semicolon files are read with a decimal comma (1086,03), as Excel writes them
    in many countries.
    """
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            with open(path, encoding=encoding, newline="") as fh:
                header = fh.readline()
            sep = ";" if header.count(";") > header.count(",") else ","
            decimal = "," if sep == ";" else "."
            # Name and ID columns are read as text, so 00123 keeps its zeros and an ID column with
            # a blank cell isn't turned into decimals (10045.0). The leak check compares exact text.
            present = [c.strip().strip('"') for c in header.strip().split(sep)]
            as_text = {c: str for c in SENSITIVE if c in present}
            table = pd.read_csv(path, sep=sep, decimal=decimal, encoding=encoding, dtype=as_text)
            if encoding == "utf-8-sig":   # keep a byte-order mark only if the source file has one
                with open(path, "rb") as fh:
                    encoding = "utf-8-sig" if fh.read(3) == b"\xef\xbb\xbf" else "utf-8"
            return table, sep, decimal, encoding
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"Couldn't read {path}. In Excel, save it as 'CSV UTF-8 (Comma delimited)' and try again.")


def same_file(a, b):
    """True if both paths point to one file (also catches case differences on Windows)."""
    if os.path.exists(a) and os.path.exists(b):
        return os.path.samefile(a, b)
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def as_text(values):
    """Values as trimmed text, so the leak check compares like with like."""
    return values.dropna().astype(str).str.strip()


def source_values(column):
    """The column's values in the source file, as trimmed text."""
    return set(as_text(real[column]))


if not os.path.isfile(REAL_FILE):
    raise SystemExit(f"Can't find {REAL_FILE}. Check REAL_FILE at the top of this script.")
if same_file(REAL_FILE, SYNTHETIC_FILE):
    raise SystemExit("REAL_FILE and SYNTHETIC_FILE are the same file. Pick a different name for the synthetic copy.")
PRACTICE_REAL = "data/practice_expense_claims.csv"
PRACTICE_SYNTHETIC = "data/practice_expense_claims_synthetic.csv"
if same_file(SYNTHETIC_FILE, PRACTICE_SYNTHETIC) and not same_file(REAL_FILE, PRACTICE_REAL):
    # data/ is shared in the public repo: a copy of your own data must not land there
    raise SystemExit("SYNTHETIC_FILE still points to the practice file in data/. "
                     'For your own data, set it to a path in "private", e.g. "private/my_file_synthetic.csv".')
os.makedirs(os.path.dirname(SYNTHETIC_FILE) or ".", exist_ok=True)   # e.g. creates "private" if it's missing
if os.path.exists(SYNTHETIC_FILE):
    os.remove(SYNTHETIC_FILE)   # an old copy must never be mistaken for this run's result
real, SEP, DECIMAL, ENCODING = read_csv_any(REAL_FILE)

# Check the settings against the file's columns before doing anything else
named = {"DROP_COLUMNS": DROP_COLUMNS, "COPY_AS_IS": COPY_AS_IS, "TYPE_FIXES": list(TYPE_FIXES),
         "DATE_ORDER": [c for pair in DATE_ORDER for c in pair], "SENSITIVE": SENSITIVE}
for setting, cols in named.items():
    missing = [c for c in cols if c not in real.columns]
    if missing:
        raise SystemExit(f"{setting} names columns that aren't in {REAL_FILE}: {missing}\n"
                         f"The file's columns are: {list(real.columns)}")
dropped_but_used = sorted({c for s in ("COPY_AS_IS", "TYPE_FIXES", "DATE_ORDER", "SENSITIVE") for c in named[s] if c in DROP_COLUMNS})
if dropped_but_used:
    raise SystemExit(f"These columns are in DROP_COLUMNS but also used in other settings: {dropped_but_used}")
real = real.drop(columns=DROP_COLUMNS)

# A number column with a few non-number cells ("TBC", "1,086.03") would be read as text and then
# copied with its real values. Stop and point at the cells so they can be fixed in the file.
for column in real.columns:
    if real[column].dtype == object and column not in SENSITIVE:
        values = real[column].dropna().astype(str).str.strip()
        as_number = pd.to_numeric(values.str.replace(",", "", regex=False), errors="coerce")
        if len(values) and as_number.notna().mean() >= 0.8:
            odd = values[pd.to_numeric(values, errors="coerce").isna()].unique()[:3]
            raise SystemExit(f"\nStopped: {column} is mostly numbers, but some cells aren't plain numbers, "
                             f"e.g. {list(odd)}.\nFix those cells in the file (no text, no thousands "
                             "separators) and run again, or drop the column. Nothing was saved.")

try:
    for earlier, later in DATE_ORDER:
        real[earlier] = pd.to_datetime(real[earlier], format=DATE_FORMAT)
        real[later] = pd.to_datetime(real[later], format=DATE_FORMAT)
except ValueError as error:
    raise SystemExit(f"A date in DATE_ORDER doesn't match DATE_FORMAT ({DATE_FORMAT}): {error}")

# 1. Let SDV guess each column's type, apply your fixes, and show the result
metadata = Metadata.detect_from_dataframes({TABLE: real})
try:
    for column, fix in TYPE_FIXES.items():
        metadata.update_column(column_name=column, table_name=TABLE, **fix)
    metadata.validate()
except Exception as error:   # SDV raises several error types here; all mean a setting needs fixing
    raise SystemExit(f"SDV couldn't use TYPE_FIXES. Check the sdtype names and ID patterns.\n{error}")

print("\nColumn types (check every line):")
columns = metadata.to_dict()["tables"][TABLE]["columns"]
for name, info in columns.items():
    print(f"  {name:<15} {info['sdtype']}")

# Every column SDV treats as an ID needs a pattern for new IDs. Without one, SDV can reuse the real IDs.
id_columns = [n for n, info in columns.items() if info["sdtype"] == "id"]
no_pattern = [n for n in id_columns if "regex_format" not in TYPE_FIXES.get(n, {})]
if no_pattern:
    raise SystemExit(f"\nStopped: these look like ID columns but have no pattern in TYPE_FIXES: {no_pattern}\n"
                     'Add e.g. "Cost Centre": {"sdtype": "id", "regex_format": "X[0-9]{5}"}, or drop them. '
                     "Nothing was saved.")

# Category columns (departments, merchants, approvers, notes...) keep their real values in the copy.
# Each one must be listed in COPY_AS_IS, or dropped. That way nothing is shared by accident.
kept_as_is = [n for n, info in columns.items() if info["sdtype"] == "categorical" and n not in COPY_AS_IS]
if kept_as_is:
    raise SystemExit(f"\nStopped: these columns would keep their real values: {kept_as_is}\n"
                     "If they hold names, notes or anything private, add them to DROP_COLUMNS.\n"
                     "If their values are fine to share, add them to COPY_AS_IS. Nothing was saved.")

# Whole-number columns can be codes, employee numbers or account/card numbers, and SDV can return
# real ones. Each must be listed in COPY_AS_IS (e.g. a quantity), given an ID pattern, or dropped.
whole_numbers = [n for n, info in columns.items()
                 if info["sdtype"] == "numerical" and n not in COPY_AS_IS and (real[n].dropna() % 1 == 0).all()]
if whole_numbers:
    raise SystemExit(f"\nStopped: these whole-number columns could be codes or ID numbers: {whole_numbers}\n"
                     "If they are IDs or account numbers, give them an ID pattern in TYPE_FIXES or drop them.\n"
                     "If they are plain counts (a quantity, say) that are fine to share, add them to COPY_AS_IS. "
                     "Nothing was saved.")

# Columns checked for real values after generating: the ones you listed, plus every ID column.
CHECKED = list(dict.fromkeys(SENSITIVE + id_columns))

# 2. Learn the patterns and make new rows, keeping dates in order
synthesizer = GaussianCopulaSynthesizer(metadata)
synthesizer.add_constraints([
    Inequality(low_column_name=a, high_column_name=b) for a, b in DATE_ORDER
])
synthesizer.fit({TABLE: real})
fake = synthesizer.sample(num_rows=ROWS)
if isinstance(fake, dict):          # SDV 2.x returns {table name: rows}
    fake = fake[TABLE]

# 3a. Number columns with many different values (card or account numbers, for example) should not
#     come back with their real values. Small-range numbers such as quantities are left alone.
for column, info in columns.items():
    if info["sdtype"] == "numerical" and column not in COPY_AS_IS and real[column].nunique() > 100:
        share = fake[column].isin(set(real[column].dropna())).mean()
        if share > 0.2:
            raise SystemExit(f"\nStopped: {column} repeats real values in {share:.0%} of rows. It may be an "
                             "identifier such as a card or account number.\nAdd it to DROP_COLUMNS, give it an "
                             "ID pattern in TYPE_FIXES, or list it in COPY_AS_IS if its values are fine to share. "
                             "Nothing was saved.")

# 3b. Leak check on the listed name/ID columns and every ID column.
#     A row that repeats a source value (a generated name that happens to exist in your file, say) is dropped.
print("\nLeak check:")
repeats = pd.Series(False, index=fake.index)
for column in CHECKED:
    hit = fake[column].astype(str).str.strip().isin(source_values(column))
    print(f"  {column:<15} rows repeating a source value: {int(hit.sum())}")
    repeats |= hit
if repeats.mean() > 0.05:
    raise SystemExit(
        "Stopped: more than 5% of rows repeat values from your file. Nothing was saved.\n"
        "Check that every name column is 'name' and every ID column is 'id' with a pattern in TYPE_FIXES,\n"
        "and that ID patterns can't produce your real IDs (use a different prefix, e.g. X[0-9]{5})."
    )
if repeats.any():
    fake = fake[~repeats]
    print(f"  Dropped {int(repeats.sum())} rows that repeated a source value.")
# Final check on exactly what will be saved
for column in CHECKED:
    left = int(fake[column].astype(str).str.strip().isin(source_values(column)).sum())
    if left:
        raise SystemExit(f"Stopped: {column} still repeats {left} source values. Nothing was saved.")

# Write the copy the way the source file is written (separator, decimal mark, date format, encoding),
# so code written for the copy also reads the real file.
for earlier, later in DATE_ORDER:
    fake[earlier] = fake[earlier].dt.strftime(DATE_FORMAT)
    fake[later] = fake[later].dt.strftime(DATE_FORMAT)
tmp = SYNTHETIC_FILE + ".tmp"
fake.to_csv(tmp, index=False, sep=SEP, decimal=DECIMAL, encoding=ENCODING)
os.replace(tmp, SYNTHETIC_FILE)   # the old copy is replaced only after every check passed
print(f"\nSaved {len(fake)} synthetic rows to {SYNTHETIC_FILE}.")
print("Open it and check every column before you share it. Category values are kept, numbers stay")
print("inside the source range, and a few values can equal source values. Delete columns you don't need.")
