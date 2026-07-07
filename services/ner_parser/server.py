"""SEVER NER Parser — HTTP service wrapper.

Exposes the parser as a microservice for the ingestion pipeline:
POST /parse {"descriptors": [...]} -> per-descriptor merchant matches.
"""

from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from main import parse_descriptor

app = FastAPI(title="SEVER NER Parser", version="0.1.0")


class ParseRequest(BaseModel):
    descriptors: list[str]


class ParseResult(BaseModel):
    raw: str
    merchant: Optional[str] = None
    category: Optional[str] = None
    confidence: float = 0.0


class ParseResponse(BaseModel):
    results: list[ParseResult]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/parse", response_model=ParseResponse)
def parse(req: ParseRequest) -> ParseResponse:
    results = []
    for d in req.descriptors:
        entity = parse_descriptor(d)
        if entity is None:
            results.append(ParseResult(raw=d))
        else:
            results.append(
                ParseResult(
                    raw=d,
                    merchant=entity.merchant,
                    category=entity.category,
                    confidence=entity.confidence,
                )
            )
    return ParseResponse(results=results)
