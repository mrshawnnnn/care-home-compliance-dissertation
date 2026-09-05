"""
PARAPHRASE VALIDATION
=====================
Paraphrases inherit their seed's label. That inheritance is an ASSUMPTION,
not an annotation. This tool makes you confirm each one against the rubric,
which is what the methodology commits to.

Reviews in batches grouped by control, so you stay in one rubric section
at a time — this is what keeps labelling consistent.

Keys:
    [Enter] / y   label is correct, keep
    n             label is WRONG, flip it and keep
    x             ambiguous or bad paraphrase, exclude
    s             skip for now (stays unvalidated)
    q             save and quit

Usage:
    python validate_paraphrases.py
    python validate_paraphrases.py --control CE1_Firewalls
    python validate_paraphrases.py --batch 50

Progress saves after every decision — safe to quit any time.
Output: data/paraphrases_validated.csv
"""

import argparse
import os
import sys

import pandas as pd

IN_FILE = "data/paraphrases_raw.csv"
OUT_FILE = "data/paraphrases_validated.csv"


def load():
    """Resume from validated file if it exists, else start from raw."""
    if os.path.exists(OUT_FILE):
        df = pd.read_csv(OUT_FILE)
        print(f"Resuming from {OUT_FILE}")
    else:
        if not os.path.exists(IN_FILE):
            sys.exit(f"Not found: {IN_FILE}. Run expand_dataset.py first.")
        df = pd.read_csv(IN_FILE)
        df["validated"] = False
        df["excluded"] = False
        df["label_changed"] = False
        print(f"Starting fresh from {IN_FILE}")
    for col in ("validated", "excluded", "label_changed"):
        if col not in df.columns:
            df[col] = False
    return df


def progress(df):
    total = len(df)
    done = int(df["validated"].sum())
    exc = int(df["excluded"].sum())
    chg = int(df["label_changed"].sum())
    pct = done / total * 100 if total else 0
    bar = "█" * int(pct / 2.5) + "░" * (40 - int(pct / 2.5))
    print(f"\n[{bar}] {done}/{total} ({pct:.1f}%)  "
          f"excluded={exc}  flipped={chg}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--control", default=None,
                    help="only review one control (e.g. CE1_Firewalls)")
    ap.add_argument("--batch", type=int, default=25,
                    help="how many to review this session")
    args = ap.parse_args()

    df = load()

    todo = df[(~df["validated"]) & (~df["excluded"])]
    if args.control:
        todo = todo[todo["control"] == args.control]
    if todo.empty:
        print("\nNothing left to validate.")
        progress(df)
        return

    # Group by control so you stay in one rubric section
    todo = todo.sort_values(["control", "seed_id"])
    batch = todo.head(args.batch)

    print("=" * 62)
    print("PARAPHRASE VALIDATION")
    print("=" * 62)
    progress(df)
    print(f"\nReviewing {len(batch)} items this session.")
    print("Keep the rubric open. Check against the CRITERION shown.\n")
    print("[Enter]=correct  n=flip label  x=exclude  s=skip  q=quit")

    current_control = None
    reviewed = 0

    for idx, row in batch.iterrows():
        if row["control"] != current_control:
            current_control = row["control"]
            print("\n" + "─" * 62)
            print(f"CONTROL: {current_control}   ({row['framework']})")
            print("─" * 62)

        print(f"\n  Criterion : {row['criterion']}")
        print(f"  Seed      : {row['seed_text']}")
        print(f"  Paraphrase: {row['sentence_text']}")
        print(f"  Label     : {row['label_text']}")

        try:
            ans = input("  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nInterrupted.")
            break

        if ans == "q":
            break
        elif ans == "s":
            continue
        elif ans == "x":
            df.at[idx, "excluded"] = True
            df.at[idx, "validated"] = True
            print("  → excluded")
        elif ans == "n":
            new = 0 if row["label"] == 1 else 1
            df.at[idx, "label"] = new
            df.at[idx, "label_text"] = "COMPLIANT" if new else "NON_COMPLIANT"
            df.at[idx, "label_changed"] = True
            df.at[idx, "validated"] = True
            print(f"  → flipped to {df.at[idx, 'label_text']}")
        else:
            df.at[idx, "validated"] = True
            print("  → confirmed")

        reviewed += 1
        df.to_csv(OUT_FILE, index=False)   # save after every decision

    df.to_csv(OUT_FILE, index=False)
    print("\n" + "=" * 62)
    print(f"Session complete — {reviewed} reviewed")
    progress(df)

    kept = df[(df["validated"]) & (~df["excluded"])]
    if len(kept):
        print(f"\n── Validated pool ({len(kept)}) ──────────────")
        print(kept["label_text"].value_counts().to_string())
        flip_rate = df["label_changed"].sum() / max(df["validated"].sum(), 1)
        print(f"\nLabel flip rate: {flip_rate:.1%}")
        if flip_rate > 0.10:
            print("⚠  >10% flipped — the generation prompt may be drifting "
                  "the compliance position. Worth investigating.")

    print(f"\nSaved -> {OUT_FILE}")


if __name__ == "__main__":
    main()
