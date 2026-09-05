# Automated Cybersecurity Compliance Assessment for UK Care Homes

MSc Cybersecurity dissertation project comparing supervised machine learning and large language model for sentence-level cybersecurity compliance classification, evaluated against UK care home cybersecurity frameworks (Cyber Essentials and DSPT), and deployed in a working web prototype.

## Headline Result

Zero-shot prompting of a locally-hosted LLM (Mistral 7B) achieved a macro F1 of **0.926** on a held-out test set of 597 sentences, outperforming the best supervised classifier (Random Forest, TF-IDF features), which achieved **0.873** — without requiring any labelled training data.

| Model / Condition | Type | Macro F1 |
|---|---|---|
| Zero-shot | LLM | **0.926** |
| Few-shot (3 examples) | LLM | 0.923 |
| Few-shot (5 examples) | LLM | 0.920 |
| Random Forest | Supervised ML | 0.873 |
| XGBoost | Supervised ML | 0.853 |
| Logistic Regression | Supervised ML | 0.839 |

## Repository Structure

```
├── dataset/            Annotation rubric, dataset construction pipeline, and final labelled data
├── notebooks/          Supervised ML training and LLM evaluation (Google Colab notebooks)
├── webapp/             Working prototype — FastAPI backend + React frontend
```

### `dataset/`
- `annotation_rubric.md` — the 15-control (5 Cyber Essentials + 10 DSPT) rubric grounding every label (in actual dissertation report)
- `expand_dataset.py` — expands seeds via local LLM paraphrasing (Ollama)
- `validate_paraphrases.py` — manual validation tool for reviewing paraphrases against the rubric
- `merge_paraphrases.py` — merges multiple paraphrase generation runs
- `build_final.py` — assembles the final dataset with a family-aware stratified train/val/test split
- `kappa_check.py` — intra-annotator agreement (Cohen's kappa) tooling
- `seed_dataset.csv`, `final_dataset.csv`, `train.csv`, `val.csv`, `test.csv` — the data itself

### `notebooks/`
- `Msc. Cybersecurity Supervised_Learning.ipynb` — TF-IDF feature extraction, training and tuning of Logistic Regression, Random Forest, and XGBoost
- `Msc. Cybersecurity LLM.ipynb` — zero-shot and few-shot evaluation of a locally-hosted LLM via Ollama

### `webapp/`
- `backend/` — FastAPI application: document parsing, sentence filtering, and classification via the winning model
- `frontend/` — React (Vite) single-page application

See `webapp/README.md` for setup and run instructions.

## Method Summary

1. Dataset construction** — 3,428 sentences built from three sources (Cyber Essentials definitions, DSPT definitions, CQC-style phrasing), expanded via LLM paraphrasing, and manually validated against the rubric. Intra-annotator agreement: Cohen's κ = 1.00.
2. Supervised ML — TF-IDF (unigrams + bigrams) feeding three classifiers, tuned via grid search on a validation set.
3. LLM evaluation — a locally-hosted Mistral model evaluated zero-shot and few-shot (3 and 5 examples) on an identical held-out test set.
4. Comparison — all six conditions scored on the same 597 test sentences with no data leakage between partitions.
5. Prototype — the best-performing approach (zero-shot LLM) deployed in a document-upload web application.

## Requirements

- Python 3.10+
- Node.js 18+
- [Ollama](https://ollama.com) with the `mistral` model pulled, for both the LLM notebook and the web prototype

## Author

Shawn Takunda Matyanga: MSc Cybersecurity, Leeds Beckett University
