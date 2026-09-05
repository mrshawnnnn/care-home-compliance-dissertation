"""
MERGE PARAPHRASE FILES
======================
Combines two (or more) paraphrase CSVs from separate expansion runs into
one clean file, removing duplicates and re-numbering IDs.

Usage:
    python merge_paraphrases.py file1.csv file2.csv
    python merge_paraphrases.py *.csv --out data/paraphrases_raw.csv

Default output: data/paraphrases_raw.csv  (what validate_paraphrases.py reads)
"""

import argparse
import sys
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("files", nargs="+", help="paraphrase CSVs to merge")
ap.add_argument("--out", default="data/paraphrases_raw.csv")
args = ap.parse_args()

frames = []
for f in args.files:
    try:
        d = pd.read_csv(f)
        print(f"  {f}: {len(d)} rows")
        frames.append(d)
    except Exception as e:
        sys.exit(f"Could not read {f}: {e}")

df = pd.concat(frames, ignore_index=True)
before = len(df)

# Drop exact duplicate sentences (case-insensitive)
df["_key"] = df["sentence_text"].str.lower().str.strip()
df = df.drop_duplicates(subset=["_key"]).drop(columns=["_key"])

# Re-number IDs so they're unique and sequential
df = df.reset_index(drop=True)
df["id"] = [f"P{i:05d}" for i in range(1, len(df) + 1)]

df.to_csv(args.out, index=False)

print(f"\nMerged {before} -> {len(df)} unique paraphrases "
      f"({before - len(df)} duplicates removed)")
print(f"Saved -> {args.out}")
print(f"\nPer-control:")
print(df['control'].value_counts().to_string())
print(f"\nLabel balance: {df['label_text'].value_counts().to_dict()}")
print(f"\nNow run: python validate_paraphrases.py")
