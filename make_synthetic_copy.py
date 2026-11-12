"""Make a synthetic copy of a confidential CSV on your own computer, with SDV.

The synthetic copy keeps the columns, data types and overall patterns of the source file,
but the rows are new. Only the synthetic file goes to the AI.

How to use:
1. Edit the SETTINGS block below. Every column name in it belongs to the practice file: replace each
   one with your own column, or remove it ([] for an empty list, {} for an empty TYPE_FIXES).
2. Run it (see README.md for the exact command). If it stops, the message says what to change.
3. Read the column table it prints. Every column with people's names must show "name", every email
   column "email", and every ID column "id" with a pattern. If not, fix it in TYPE_FIXES and run again.
4. Open the synthetic file and check every column before sharing it.

SDV is made by DataCebo and licensed under the Business Source License 1.1, which is not an
open source license. Its Additional Use Grant allows any use except offering a commercial
"Synthetic Data Service". Questions about your use: billing@datacebo.com.
"""
import csv
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
# Category columns keep their real values in the copy (SDV reuses them), and whole-number counts
# are generated within the real range, so some values match real ones. List each such column you
# are happy to share, such as departments or quantities. Never list names, emails or IDs here:
# their real values would be copied. Any other category or whole-number column stops the script.
COPY_AS_IS = ["Department", "Category", "Status"]
TYPE_FIXES = {                               # set the type of every name and ID column
    "Employee": {"sdtype": "name"},          # a person's name: replaced with generated names
    # An email column may already show "email" in the type table; if not, add {"sdtype": "email"}.
    # Every ID column needs "id" and a pattern, even if SDV already detects it as an ID. Without a
    # pattern, SDV can reuse the source IDs. X[0-9]{5} means "X followed by 5 digits". Use a prefix
    # your real IDs don't have (the practice IDs start with E and CLM-), so a new ID can't match a real one.
    "Employee ID": {"sdtype": "id", "regex_format": "X[0-9]{5}"},
    "Claim ID": {"sdtype": "id", "regex_format": "SYN-[0-9]{5}"},
}
DATE_COLUMNS = ["Submitted", "Decided"]      # every date column; [] if none
DATE_FORMAT = "%Y-%m-%d"                     # how those dates are written in your file. 31/12/2026 is "%d/%m/%Y"
DATE_ORDER = [("Submitted", "Decided")]      # (earlier, later) pairs from DATE_COLUMNS to keep in order; [] if none
# Other text columns whose real values must never appear in the copy. Name, email and ID columns
# are checked anyway; listing them here does no harm.
SENSITIVE = ["Employee", "Employee ID", "Claim ID"]
# -------------------------------------------

warnings.filterwarnings("ignore", message=".*save_to_json.*")  # we don't save metadata: it holds source values
# The new ID pattern is meant to differ from your real IDs, so SDV's "do not match the regex" warning is expected.
warnings.filterwarnings("ignore", message=".*do not match the specified regex format.*")
TABLE = "data"   # SDV works with named tables; this is just the internal name for the file's table
NOT_TEXT_TYPES = {"numerical", "datetime", "boolean"}   # TYPE_FIXES types that must not be read as text


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
            # Name, ID and SENSITIVE columns are read as text, so 00123 keeps its zeros and an ID column
            # with a blank cell isn't turned into decimals (10045.0). The leak check compares exact text.
            present = next(csv.reader([header.rstrip("\r\n")], delimiter=sep))   # exact names, as pandas reads them
            typed_as_text = [c for c, fix in TYPE_FIXES.items() if fix.get("sdtype") not in NOT_TEXT_TYPES]
            text_columns = {c: str for c in SENSITIVE + typed_as_text if c in present}
            table = pd.read_csv(path, sep=sep, decimal=decimal, encoding=encoding, dtype=text_columns)
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
         "DATE_COLUMNS": DATE_COLUMNS, "DATE_ORDER": [c for pair in DATE_ORDER for c in pair],
         "SENSITIVE": SENSITIVE}
for setting, cols in named.items():
    missing = [c for c in cols if c not in real.columns]
    if missing:
        raise SystemExit(f"{setting} names columns that aren't in {REAL_FILE}: {missing}\n"
                         f"The file's columns are: {list(real.columns)}")
dropped_but_used = sorted({c for s in ("COPY_AS_IS", "TYPE_FIXES", "DATE_COLUMNS", "DATE_ORDER", "SENSITIVE")
                           for c in named[s] if c in DROP_COLUMNS})
if dropped_but_used:
    raise SystemExit(f"These columns are in DROP_COLUMNS but also used in other settings: {dropped_but_used}")
unlisted_dates = sorted(set(named["DATE_ORDER"]) - set(DATE_COLUMNS))
if unlisted_dates:
    raise SystemExit(f"These DATE_ORDER columns aren't in DATE_COLUMNS: {unlisted_dates}. Add them to DATE_COLUMNS.")
both = sorted(set(COPY_AS_IS) & set(SENSITIVE))
if both:
    raise SystemExit(f"These columns are in COPY_AS_IS (keep real values) and in SENSITIVE (must never hold "
                     f"real values): {both}\nIf they hold names, emails or IDs, remove them from COPY_AS_IS "
                     "and set their type in TYPE_FIXES (or drop them). Remove them from SENSITIVE only if "
                     "their real values may be shared, which is never true for names, emails or IDs.")
real = real.drop(columns=DROP_COLUMNS)

# A number column with a few non-number cells ("TBC", "1,086.03") would be read as text and then
# copied with its real values. Stop and point at the cells so they can be fixed in the file.
for column in real.columns:
    if real[column].dtype == object:
        values = real[column].dropna().astype(str).str.strip()
        as_number = pd.to_numeric(values.str.replace(",", "", regex=False), errors="coerce")
        mostly_numbers = len(values) and as_number.notna().mean() >= 0.8
        if column in TYPE_FIXES and TYPE_FIXES[column].get("sdtype") not in NOT_TEXT_TYPES:
            continue   # names and IDs are read as text on purpose
        if column in SENSITIVE:
            # SENSITIVE columns are read as text. A number column (a salary, say) would lose its numbers.
            if mostly_numbers:
                raise SystemExit(f"\nStopped: {column} is in SENSITIVE but holds numbers. SENSITIVE is for text "
                                 "columns such as names or emails.\nIf it's an ID number, set it to id with a "
                                 "pattern in TYPE_FIXES. Otherwise remove it from SENSITIVE (or drop it). Nothing was saved.")
            continue
        if mostly_numbers:
            odd = values[pd.to_numeric(values, errors="coerce").isna()].unique()[:3]
            raise SystemExit(f"\nStopped: {column} is mostly numbers, but some cells aren't plain numbers, "
                             f"e.g. {list(odd)}.\nFix those cells in the file (no text, no thousands "
                             "separators) and run again, or drop the column. Nothing was saved.")

try:
    for column in DATE_COLUMNS:
        real[column] = pd.to_datetime(real[column], format=DATE_FORMAT)
except ValueError as error:
    raise SystemExit(f"A date in DATE_COLUMNS doesn't match DATE_FORMAT ({DATE_FORMAT}): {error}")

# 1. Let SDV guess each column's type, apply your fixes, and show the result
metadata = Metadata.detect_from_dataframes({TABLE: real})
try:
    for column, fix in TYPE_FIXES.items():
        metadata.update_column(column_name=column, table_name=TABLE, **fix)
    metadata.validate()
except Exception as error:   # SDV raises several error types here; all mean a setting needs fixing
    raise SystemExit(f"SDV couldn't use TYPE_FIXES. Check the sdtype names and ID patterns.\n{error}")

columns = metadata.to_dict()["tables"][TABLE]["columns"]
id_columns = [n for n, info in columns.items() if info["sdtype"] == "id"]
# Types such as name, email or phone_number are replaced with generated values. They are checked
# for source values after generating, like ID columns.
BASIC_TYPES = {"categorical", "numerical", "datetime", "boolean", "id", "unknown"}
generated_columns = [n for n, info in columns.items() if info["sdtype"] not in BASIC_TYPES]
# Columns checked for real values after generating: the ones you listed, plus every ID and name-type column.
CHECKED = list(dict.fromkeys(SENSITIVE + id_columns + generated_columns))

print("\nColumn types (check every line: names must show 'name', emails 'email', IDs 'id' with a pattern):")
for name, info in columns.items():
    pattern = TYPE_FIXES.get(name, {}).get("regex_format", "NO PATTERN") if info["sdtype"] == "id" else ""
    checked = "checked for real values" if name in CHECKED else ""
    print(f"  {name:<15} {info['sdtype']:<12} {pattern:<15} {checked}".rstrip())

# Every column SDV treats as an ID needs a pattern for new IDs. Without one, SDV can reuse the real IDs.
no_pattern = [n for n in id_columns if "regex_format" not in TYPE_FIXES.get(n, {})]
if no_pattern:
    raise SystemExit(f"\nStopped: these look like ID columns but have no pattern in TYPE_FIXES: {no_pattern}\n"
                     'Add e.g. "Staff No": {"sdtype": "id", "regex_format": "X[0-9]{5}"}, or drop them. '
                     "Nothing was saved.")

# Category columns (departments, merchants, approvers, notes...) keep their real values in the copy.
# Each one must be listed in COPY_AS_IS, or dropped. That way nothing is shared by accident.
kept_as_is = [n for n, info in columns.items() if info["sdtype"] == "categorical" and n not in COPY_AS_IS]
if kept_as_is:
    raise SystemExit(f"\nStopped: these columns would keep their real values: {kept_as_is}\n"
                     "If one holds people's names, set it to name in TYPE_FIXES, e.g. \"Approver\": {\"sdtype\": \"name\"}.\n"
                     "If one holds IDs that only identify a row or a person, set it to id with a pattern in TYPE_FIXES.\n"
                     "If one holds codes you group or filter by (cost centres, say), list it in COPY_AS_IS only if\n"
                     "the real codes may be shared, otherwise add it to DROP_COLUMNS.\n"
                     "If one holds emails or phone numbers, set it to email or phone_number in TYPE_FIXES.\n"
                     "If one holds dates, add it to DATE_COLUMNS and check DATE_FORMAT.\n"
                     "If one holds notes or anything else private, add it to DROP_COLUMNS.\n"
                     "Only if its values are fine to share as they are, add it to COPY_AS_IS. Nothing was saved.")

# Whole-number columns can be codes, employee numbers or account/card numbers, and SDV can return
# real ones. Each must be listed in COPY_AS_IS (e.g. a quantity), given an ID pattern, or dropped.
whole_numbers = [n for n, info in columns.items()
                 if info["sdtype"] == "numerical" and n not in COPY_AS_IS and (real[n].dropna() % 1 == 0).all()]
if whole_numbers:
    raise SystemExit(f"\nStopped: these whole-number columns could be codes or ID numbers: {whole_numbers}\n"
                     "If they are IDs or account numbers, give them an ID pattern in TYPE_FIXES or drop them.\n"
                     "If they are plain counts (a quantity, say) that are fine to share, add them to COPY_AS_IS. "
                     "Nothing was saved.")

# 2. Learn the patterns and make new rows, keeping dates in order
synthesizer = GaussianCopulaSynthesizer(metadata)
if DATE_ORDER:
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

# 3b. Leak check on every name-type and ID column, plus the columns in SENSITIVE.
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
for column in DATE_COLUMNS:
    fake[column] = fake[column].dt.strftime(DATE_FORMAT)
tmp = SYNTHETIC_FILE + ".tmp"
fake.to_csv(tmp, index=False, sep=SEP, decimal=DECIMAL, encoding=ENCODING)
os.replace(tmp, SYNTHETIC_FILE)   # the old copy is replaced only after every check passed
print(f"\nSaved {len(fake)} synthetic rows to {SYNTHETIC_FILE}.")
print("Open it and check every column before you share it. Category values are kept, numbers stay")
print("inside the source range, and a few values can equal source values. Delete columns you don't need.")
