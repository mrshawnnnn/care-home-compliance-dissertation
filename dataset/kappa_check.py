"""
INTRA-ANNOTATOR AGREEMENT — COHEN'S KAPPA
==========================================
Implements the consistency check from the annotation rubric, which is what
the methodology commits to in place of inter-annotator agreement.

Workflow:

  STEP 1 (after first pass, dataset locked)
      python kappa_check.py sample
      -> draws a random 20% and writes a BLIND worksheet with labels stripped

  STEP 2 (WAIT >= 2 WEEKS, then re-label the worksheet)
      Fill the 'pass2_label' column with 1 / 0 / A (ambiguous).
      Do NOT look at the original dataset while doing this.

  STEP 3
      python kappa_check.py score
      -> computes Cohen's kappa, per-control breakdown, disagreement list

The two-week gap is not optional. Without it you are testing your memory,
not the rubric.
"""

import argparse
import os
import sys

import pandas as pd

DATASET = "data/final_dataset.csv"
WORKSHEET = "data/kappa_worksheet.csv"
ANSWERS = "data/kappa_answers.csv"    # hidden pass-1 labels
REPORT = "data/kappa_report.txt"


def cohens_kappa(a, b):
    """Cohen's kappa for two label sequences (no sklearn dependency)."""
    assert len(a) == len(b) and len(a) > 0
    n = len(a)
    cats = sorted(set(a) | set(b))

    po = sum(1 for x, y in zip(a, b) if x == y) / n

    pe = 0.0
    for c in cats:
        pa = sum(1 for x in a if x == c) / n
        pb = sum(1 for y in b if y == c) / n
        pe += pa * pb

    if pe == 1.0:
        return 1.0, po, pe
    return (po - pe) / (1 - pe), po, pe


def interpret(k):
    if k >= 0.81: return "almost perfect"
    if k >= 0.61: return "substantial"
    if k >= 0.41: return "moderate"
    if k >= 0.21: return "fair"
    if k >= 0.00: return "slight"
    return "poor (worse than chance)"


def cmd_sample(args):
    if not os.path.exists(DATASET):
        sys.exit(f"Not found: {DATASET}. Build the final dataset first.")

    df = pd.read_csv(DATASET)
    n = max(1, round(len(df) * args.frac))
    sample = df.sample(n=n, random_state=args.seed).reset_index(drop=True)

    # Hidden answer key (pass 1)
    sample[["id", "label", "control"]].to_csv(ANSWERS, index=False)

    # Blind worksheet — no label, no control, no criterion.
    # Control is hidden too: mapping consistency is part of what we measure.
    ws = sample[["id", "sentence_text"]].copy()
    ws["pass2_control"] = ""
    ws["pass2_label"] = ""
    ws["note"] = ""
    ws.to_csv(WORKSHEET, index=False)

    print("=" * 62)
    print("KAPPA SAMPLE DRAWN")
    print("=" * 62)
    print(f"Dataset size   : {len(df)}")
    print(f"Sample ({args.frac:.0%})    : {n}")
    print(f"\nWorksheet -> {WORKSHEET}")
    print(f"Answer key -> {ANSWERS}  (do not open)")
    print("""
NEXT:
  1. WAIT AT LEAST TWO WEEKS.
  2. Open the worksheet and fill in:
       pass2_control  - the control code you'd assign
       pass2_label    - 1 (compliant) / 0 (non-compliant) / A (ambiguous)
     Work only from the rubric. Do not open the original dataset.
  3. Run: python kappa_check.py score
""")


def cmd_score(args):
    for f in (WORKSHEET, ANSWERS):
        if not os.path.exists(f):
            sys.exit(f"Not found: {f}. Run `kappa_check.py sample` first.")

    ws = pd.read_csv(WORKSHEET)
    key = pd.read_csv(ANSWERS)

    filled = ws[ws["pass2_label"].notna() &
                (ws["pass2_label"].astype(str).str.strip() != "")]
    if filled.empty:
        sys.exit("Worksheet has no pass2_label values yet.")
    if len(filled) < len(ws):
        print(f"⚠  Only {len(filled)}/{len(ws)} rows completed.\n")

    m = filled.merge(key, on="id", suffixes=("_p2", "_p1"))
    m["pass2_label"] = m["pass2_label"].astype(str).str.strip().str.upper()

    amb = m[m["pass2_label"] == "A"]
    scored = m[m["pass2_label"].isin(["0", "1"])].copy()
    if scored.empty:
        sys.exit("No comparable labels (all ambiguous?).")
    scored["p2"] = scored["pass2_label"].astype(int)
    scored["p1"] = scored["label"].astype(int)

    k, po, pe = cohens_kappa(scored["p1"].tolist(), scored["p2"].tolist())

    lines = []
    def out(s=""):
        print(s)
        lines.append(s)

    out("=" * 62)
    out("INTRA-ANNOTATOR AGREEMENT — COHEN'S KAPPA")
    out("=" * 62)
    out(f"\nSample size        : {len(m)}")
    out(f"Scored (0/1)       : {len(scored)}")
    out(f"Marked ambiguous   : {len(amb)}")
    out(f"\nObserved agreement : {po:.4f}")
    out(f"Expected by chance : {pe:.4f}")
    out(f"Cohen's kappa      : {k:.4f}   ({interpret(k)})")

    out("\n── Interpretation ────────────────────────────")
    if k >= 0.81:
        out("Almost perfect agreement. The rubric is applied consistently.")
        out("Reportable as strong evidence of annotation reliability.")
    elif k >= 0.61:
        out("Substantial agreement — acceptable for reporting.")
        out("Review the disagreements below for any rubric ambiguity.")
    else:
        out("Below the substantial threshold. Before proceeding:")
        out("  - Examine disagreements for the pattern")
        out("  - Tighten the rubric criteria involved")
        out("  - Re-label affected sentences and re-run")

    # Control mapping consistency (secondary measure)
    if "pass2_control" in m.columns:
        cm = m[m["pass2_control"].notna() &
               (m["pass2_control"].astype(str).str.strip() != "")]
        if len(cm):
            agree = (cm["pass2_control"].str.strip() ==
                     cm["control"].str.strip()).mean()
            out(f"\n── Control mapping consistency ───────────────")
            out(f"Same control assigned: {agree:.1%} of {len(cm)}")
            if agree < 0.85:
                out("⚠  Mapping inconsistency — check the CE3/DSPT8 and")
                out("   CE/DSPT9 overlap notes in the rubric.")

    # Per-control kappa
    out("\n── Per-control agreement ─────────────────────")
    for ctrl, grp in scored.groupby("control"):
        if len(grp) < 2:
            out(f"  {ctrl:32s} n={len(grp):3d}  (too few)")
            continue
        ck, cpo, _ = cohens_kappa(grp["p1"].tolist(), grp["p2"].tolist())
        out(f"  {ctrl:32s} n={len(grp):3d}  agree={cpo:.2f}  k={ck:.3f}")

    # Disagreements
    dis = scored[scored["p1"] != scored["p2"]]
    out(f"\n── Disagreements ({len(dis)}) ──────────────────────")
    if dis.empty:
        out("  None.")
    else:
        for r in dis.itertuples():
            out(f"\n  [{r.id}] {r.control}")
            out(f"    {r.sentence_text}")
            out(f"    pass1={r.p1}  pass2={r.p2}")
        out("\n  Resolve each against the rubric.")
        out("  If the rubric does not decide it, EXCLUDE the sentence")
        out("  and record the rubric gap.")

    if len(amb):
        out(f"\n── Marked ambiguous on pass 2 ({len(amb)}) ─────────")
        for r in amb.itertuples():
            out(f"  [{r.id}] {r.sentence_text}")

    out(f"\n── For the dissertation ──────────────────────")
    out(f"Report: kappa = {k:.2f} ({interpret(k)}) on a "
        f"{len(scored)}-sentence sample re-labelled after a two-week interval.")

    with open(REPORT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nSaved -> {REPORT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    s1 = sub.add_parser("sample", help="draw the blind 20% sample")
    s1.add_argument("--frac", type=float, default=0.20)
    s1.add_argument("--seed", type=int, default=42)
    s1.set_defaults(func=cmd_sample)

    s2 = sub.add_parser("score", help="compute kappa after re-labelling")
    s2.set_defaults(func=cmd_score)

    a = ap.parse_args()
    a.func(a)
