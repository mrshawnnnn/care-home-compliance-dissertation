"""
FINAL DATASET ASSEMBLY
======================
Merges seeds + VALIDATED paraphrases, runs the methodology's quality gates,
and produces the stratified 80/10/10 split.

Refuses to include unvalidated paraphrases — that check is what keeps the
dataset consistent with the annotation protocol.

Split is stratified by control AND label so every control appears in every
partition with its balance preserved. Seed/paraphrase families are kept
together in the same partition: a paraphrase of a training sentence must
never appear in test, or the comparison leaks.

Usage:
    python build_final.py
    python build_final.py --allow-unvalidated   # NOT for the real run

Output: data/final_dataset.csv  (+ train/val/test)
"""

import argparse
import os
import sys

import pandas as pd
from sklearn.model_selection import train_test_split

SEEDS = "data/seed_dataset.csv"
PARAS = "data/paraphrases_validated.csv"
OUT = "data/final_dataset.csv"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-unvalidated", action="store_true")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    if not os.path.exists(SEEDS):
        sys.exit(f"Not found: {SEEDS}. Run build_seeds.py first.")

    seeds = pd.read_csv(SEEDS)
    seeds["seed_id"] = seeds["id"]        # a seed is its own family head
    seeds["validated"] = True             # written directly against the rubric

    print("=" * 62)
    print("FINAL DATASET ASSEMBLY")
    print("=" * 62)
    print(f"\nSeeds: {len(seeds)}")

    frames = [seeds[["id", "sentence_text", "label", "label_text", "control",
                     "framework", "criterion", "source", "seed_id"]]]

    if os.path.exists(PARAS):
        p = pd.read_csv(PARAS)
        total = len(p)
        p = p[~p.get("excluded", False).fillna(False).astype(bool)]
        excluded = total - len(p)

        if not args.allow_unvalidated:
            before = len(p)
            p = p[p["validated"].fillna(False).astype(bool)]
            dropped = before - len(p)
            if dropped:
                print(f"⚠  Dropped {dropped} UNVALIDATED paraphrases.")
                print("   Run validate_paraphrases.py to review them.")
        else:
            print("⚠  --allow-unvalidated set. Do NOT use this for the")
            print("   real dataset — it breaks the annotation protocol.")

        print(f"Paraphrases: {len(p)} usable "
              f"({excluded} excluded during validation)")
        if len(p):
            frames.append(p[["id", "sentence_text", "label", "label_text",
                             "control", "framework", "criterion", "source",
                             "seed_id"]])
    else:
        print("Paraphrases: none yet (run expand_dataset.py "
              "then validate_paraphrases.py)")

    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["sentence_text"]).reset_index(drop=True)

    # ── Quality gates ─────────────────────────────────────────
    print(f"\n── Quality gates ─────────────────────────────")
    print(f"Total sentences: {len(df)}")
    ok = True

    counts = df["label_text"].value_counts()
    ratio = counts.min() / counts.max()
    gate = ratio >= 0.8
    ok &= gate
    print(f"  Class balance      {ratio:.2f}  "
          f"[{'PASS' if gate else 'FAIL'} — need >= 0.80]")

    gate = df["control"].nunique() == 15
    ok &= gate
    print(f"  Controls covered   {df['control'].nunique()}/15  "
          f"[{'PASS' if gate else 'FAIL'}]")

    thin = df.groupby("control").size()
    thin = thin[thin < 10]
    gate = thin.empty
    ok &= gate
    print(f"  Min 10 per control       "
          f"[{'PASS' if gate else 'FAIL'}]")
    if not thin.empty:
        for c, n in thin.items():
            print(f"      thin: {c} ({n})")

    gate = len(df) >= 3000
    print(f"  Target ~3000       {len(df)}  "
          f"[{'PASS' if gate else 'BELOW TARGET'}]")
    if not gate:
        need = 3000 - len(df)
        print(f"      need ~{need} more — increase --n in expand_dataset.py")

    # ── Stratified split, family-aware ────────────────────────
    # Split at the FAMILY level (seed + its paraphrases move together)
    fam = (df.groupby("seed_id")
             .agg(control=("control", "first"),
                  label=("label", "first"),
                  n=("id", "count"))
             .reset_index())
    fam["strat"] = fam["control"] + "_" + fam["label"].astype(str)

    def strat_or_none(frame, need):
        """Only stratify if every stratum has enough members for the split."""
        vc = frame["strat"].value_counts()
        return frame["strat"] if vc.min() >= need else None

    # Split 1: train vs (val+test). Each stratum needs >=2 to appear in both.
    s1 = strat_or_none(fam, 2)
    if s1 is None:
        print("\n⚠  Some control/label strata too small to stratify "
              "at the family level — falling back to a random split.")
        print("   Balance is reported per split below; verify it is acceptable.")
    tr_f, tmp_f = train_test_split(
        fam, test_size=0.2, random_state=args.seed, stratify=s1)

    # Split 2: val vs test, re-checked on the remaining families
    s2 = strat_or_none(tmp_f, 2)
    va_f, te_f = train_test_split(
        tmp_f, test_size=0.5, random_state=args.seed, stratify=s2)

    def part(fams, name):
        sub = df[df["seed_id"].isin(fams["seed_id"])].copy()
        sub["split"] = name
        return sub

    train, val, test = (part(tr_f, "train"),
                        part(va_f, "val"),
                        part(te_f, "test"))
    final = pd.concat([train, val, test], ignore_index=True)

    print(f"\n── Split (family-aware, stratified) ──────────")
    for name, part_df in (("train", train), ("val", val), ("test", test)):
        pct = len(part_df) / len(final) * 100
        b = part_df["label"].mean()
        print(f"  {name:5s} {len(part_df):5d}  ({pct:4.1f}%)  "
              f"compliant={b:.2f}")

    # Leakage check
    overlap = set(train["seed_id"]) & set(test["seed_id"])
    print(f"\n  Train/test family overlap: {len(overlap)}  "
          f"[{'PASS' if not overlap else 'FAIL — LEAKAGE'}]")

    final.to_csv(OUT, index=False)
    for name, part_df in (("train", train), ("val", val), ("test", test)):
        part_df.to_csv(f"data/{name}.csv", index=False)

    print(f"\nSaved -> {OUT}")
    print(f"         data/train.csv  data/val.csv  data/test.csv")

    if not ok:
        print("\n⚠  Some gates failed. Address before modelling.")
    print("\nNEXT: lock the dataset, then `python kappa_check.py sample`")


if __name__ == "__main__":
    main()
