"""
Compliance Check — Backend API
================================
FastAPI application exposing three endpoints:

    GET  /api/health    — checks Ollama connectivity
    POST /api/analyze   — accepts a document, streams NDJSON events as
                           each sentence is checked, ends with a summary

Run with:
    uvicorn main:app --reload --port 8000

Requires Ollama running locally with the mistral model pulled
(see README.md for setup).
"""

import json

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

import document_processor as docproc
import llm_classifier as llm

app = FastAPI(title="Compliance Check API")

# Local prototype — frontend runs on Vite's default dev port.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_SENTENCES = 400  # safety cap so a huge document can't run for hours


@app.get("/api/health")
def health():
    ok, message = llm.check_ollama_available()
    return {"ok": ok, "message": message}


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)):
    ok, message = llm.check_ollama_available()
    if not ok:
        raise HTTPException(status_code=503, detail=message)

    file_bytes = await file.read()

    try:
        result = docproc.process_document(file.filename, file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    sentences = result["relevant_sentences"][:MAX_SENTENCES]
    truncated = result["relevant_count"] > MAX_SENTENCES

    def event_stream():
        # Tell the frontend what was found before classification starts
        yield json.dumps({
            "event": "extracted",
            "total_document_sentences": result["total_sentences"],
            "relevant_count": len(sentences),
            "truncated": truncated,
        }) + "\n"

        findings = []
        for i, sentence in enumerate(sentences, 1):
            try:
                outcome = llm.classify_sentence(sentence)
            except llm.OllamaUnavailableError as e:
                yield json.dumps({"event": "error", "message": str(e)}) + "\n"
                return

            finding = {
                "index": i,
                "sentence": sentence,
                "label": outcome["label"],
                "control": outcome["control"],
                "reason": outcome["reason"],
                "parse_failed": outcome["parse_failed"],
            }
            findings.append(finding)

            yield json.dumps({
                "event": "progress",
                "index": i,
                "total": len(sentences),
                "finding": finding,
            }) + "\n"

        # Summary
        valid = [f for f in findings if f["label"] is not None]
        compliant = [f for f in valid if f["label"] == "COMPLIANT"]
        non_compliant = [f for f in valid if f["label"] == "NON_COMPLIANT"]

        controls_flagged = {}
        for f in non_compliant:
            key = f["control"] or "Unspecified"
            controls_flagged[key] = controls_flagged.get(key, 0) + 1

        summary = {
            "total_checked": len(valid),
            "compliant_count": len(compliant),
            "non_compliant_count": len(non_compliant),
            "compliant_rate": round(len(compliant) / len(valid), 3) if valid else 0,
            "controls_flagged": controls_flagged,
            "parse_failures": len(findings) - len(valid),
        }

        yield json.dumps({"event": "done", "summary": summary}) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
