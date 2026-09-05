"""
PARAPHRASE EXPANSION
====================
Scales the seed dataset toward the ~3,000-sentence target using the
locally-hosted LLM (Ollama). Runs on YOUR machine — nothing leaves it.

IMPORTANT — this is generation, NOT annotation.
Every paraphrase INHERITS its seed's label provisionally and is written
to the CSV with validated=False. You must then validate each one against
the rubric (validate_paraphrases.py) before it enters the final dataset.
This preserves the annotation protocol promised in the methodology.

Prereqs:
    ollama pull mistral        (or: llama3)
    ollama serve

Usage:
    python expand_dataset.py                 # default 10 per seed -> ~2,900
    python expand_dataset.py --n 12          # more variations per seed
    python expand_dataset.py --model llama3
    python expand_dataset.py --limit 5       # smoke test on 5 seeds

Output: data/paraphrases_raw.csv
"""

import argparse
import json
import re
import sys
import time

import pandas as pd
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"

PROMPT = """You are helping build a research dataset of UK care home compliance statements.

Rewrite the statement below in {n} different ways. Each rewrite must:
- Keep the EXACT same meaning and the same compliance position
- Sound like a real sentence from a care home's own IT policy, staff handbook, training record, audit note, or incident log
- Vary the wording, sentence structure, and formality — do not just swap synonyms
- Use British English
- Be one sentence, 8 to 30 words
- NOT add any new facts, controls, dates, or details that are not in the original
- NOT flip, soften, or hedge the compliance position

CRITICAL: if the original describes a FAILING, every rewrite must still describe that same failing. If the original describes something DONE PROPERLY, every rewrite must still describe it as done properly.

Original statement: "{sentence}"

Return ONLY a JSON array of {n} strings. No preamble, no markdown, no code fences.
Example format: ["first rewrite here", "second rewrite here"]"""


def call_ollama(model, prompt, timeout=180):
    r = requests.post(
        OLLAMA_URL,
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.85, "top_p": 0.9},
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json().get("response", "")


def parse_variants(raw):
    """Pull a JSON array of strings out of the model's response."""
    txt = raw.strip()
    txt = re.sub(r"^```(?:json)?|```$", "", txt, flags=re.MULTILINE).strip()

    m = re.search(r"\[.*\]", txt, re.DOTALL)
    if m:
        try:
            arr = json.loads(m.group(0))
            return [str(s).strip() for s in arr if isinstance(s, (str,))]
        except json.JSONDecodeError:
            pass

    # Fallback: quoted strings, or bulleted/numbered lines
    quoted = re.findall(r'"([^"]{15,300})"', txt)
    if quoted:
        return [q.strip() for q in quoted]

    lines = []
    for line in txt.split("\n"):
        line = re.sub(r'^\s*(?:[-*•]|\d+[.)])\s*', '', line).strip().strip('"')
        if 15 < len(line) < 300:
            lines.append(line)
    return lines


def sanity_ok(text, seed_text):
    """Cheap structural filters before human validation."""
    if not (15 < len(text) < 300):
        return False
    if text.strip().lower() == seed_text.strip().lower():
        return False
    if text.count(".") > 2:            # should be one sentence
        return False
    if re.search(r'\b(rewrite|variation|here (is|are)|json)\b', text, re.I):
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="mistral")
    ap.add_argument("--n", type=int, default=10,
                    help="variations requested per seed")
    ap.add_argument("--limit", type=int, default=None,
                    help="only process first N seeds (smoke test)")
    ap.add_argument("--seeds", default="data/seed_dataset.csv")
    ap.add_argument("--out", default="data/paraphrases_raw.csv")
    args = ap.parse_args()

    try:
        seeds = pd.read_csv(args.seeds)
    except FileNotFoundError:
        sys.exit(f"Seed file not found: {args.seeds}. Run build_seeds.py first.")

    if args.limit:
        seeds = seeds.head(args.limit)

    # Check Ollama is up
    try:
        requests.get("http://localhost:11434/api/tags", timeout=5)
    except requests.exceptions.RequestException:
        sys.exit("Cannot reach Ollama at localhost:11434. Run: ollama serve")

    print("=" * 62)
    print(f"PARAPHRASE EXPANSION  |  model={args.model}  n={args.n}/seed")
    print("=" * 62)
    print(f"Seeds to process: {len(seeds)}")
    print(f"Projected output: ~{len(seeds) * args.n} paraphrases\n")

    rows, failed = [], 0
    t0 = time.time()

    for i, seed in enumerate(seeds.itertuples(), 1):
        prompt = PROMPT.format(n=args.n, sentence=seed.sentence_text)
        try:
            raw = call_ollama(args.model, prompt)
            variants = parse_variants(raw)
        except Exception as e:
            print(f"  [{i}/{len(seeds)}] {seed.id}  ERROR: {e}")
            failed += 1
            continue

        kept = 0
        seen = set()
        for v in variants:
            if not sanity_ok(v, seed.sentence_text):
                continue
            key = v.lower().strip()
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "sentence_text": v,
                "label":         seed.label,          # PROVISIONAL
                "label_text":    seed.label_text,     # PROVISIONAL
                "control":       seed.control,
                "framework":     seed.framework,
                "criterion":     seed.criterion,
                "source":        "llm_paraphrase",
                "seed_id":       seed.id,
                "seed_text":     seed.sentence_text,
                "validated":     False,               # <- must be checked
            })
            kept += 1

        elapsed = time.time() - t0
        rate = i / elapsed if elapsed else 0
        eta = (len(seeds) - i) / rate / 60 if rate else 0
        print(f"  [{i}/{len(seeds)}] {seed.id}  kept {kept:2d}  "
              f"| total {len(rows):5d}  | ETA {eta:.1f}m")

    df = pd.DataFrame(rows)
    if df.empty:
        sys.exit("No paraphrases generated.")

    # Drop dupes across the whole run, and any that collide with a seed
    df = df.drop_duplicates(subset=["sentence_text"])
    seed_texts = set(seeds["sentence_text"].str.lower().str.strip())
    df = df[~df["sentence_text"].str.lower().str.strip().isin(seed_texts)]
    df = df.reset_index(drop=True)
    df.insert(0, "id", [f"P{i:05d}" for i in range(1, len(df) + 1)])

    print("\n" + "=" * 62)
    print(f"Generated:        {len(df)} unique paraphrases")
    print(f"Failed seeds:     {failed}")
    print(f"Seeds + paras:    {len(seeds) + len(df)}  (target ~3000)")
    print(f"\n── Provisional label balance ─────────────────")
    print(df["label_text"].value_counts().to_string())
    print(f"\n── Per-control ───────────────────────────────")
    print(df["control"].value_counts().to_string())

    df.to_csv(args.out, index=False)
    print(f"\nSaved -> {args.out}")
    print("\nNEXT STEP: validate_paraphrases.py")
    print("Every row has validated=False. Labels are INHERITED, not annotated.")
    print("You must confirm each against the rubric before use.")


if __name__ == "__main__":
    main()
