"""SEVER API — REST endpoints backing the frontend.

Subscriptions are stored per-user in SQLite (see store.py); the user key
is the auth 'sub' claim — the dev user in disabled mode, the Cognito
subject once AUTH_MODE=cognito.
"""

import os
import time
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth import get_current_user
from store import SubscriptionStore

app = FastAPI(title="SEVER API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://zacharypeebels.github.io",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Subscription(BaseModel):
    id: int
    name: str
    category: str
    price: float
    cadence: Literal["mo", "yr"]
    lastUsed: int
    status: Literal["active", "paused", "canceled", "negotiated"] = "active"
    newPrice: Optional[float] = None


class ActionRequest(BaseModel):
    mode: Literal["cancel", "pause", "haggle"]


class ActionResult(BaseModel):
    subscription: Subscription
    reclaimedMonthly: float
    message: str


SEED = [
    Subscription(id=1, name="Netflix", category="Streaming", price=15.49, cadence="mo", lastUsed=2),
    Subscription(id=2, name="iCloud+ 200GB", category="Storage", price=2.99, cadence="mo", lastUsed=0),
    Subscription(id=3, name="Peak Fitness Gym", category="Health", price=44.0, cadence="mo", lastUsed=67),
    Subscription(id=4, name="Adobe Creative Cloud", category="Software", price=59.99, cadence="mo", lastUsed=41),
    Subscription(id=5, name="Duolingo Super", category="Education", price=6.99, cadence="mo", lastUsed=88),
    Subscription(id=6, name="DashPass", category="Delivery", price=9.99, cadence="mo", lastUsed=34),
    Subscription(id=7, name="Spotify Premium", category="Streaming", price=11.99, cadence="mo", lastUsed=1),
    Subscription(id=8, name="Calm", category="Wellness", price=69.99, cadence="yr", lastUsed=122),
    Subscription(id=9, name="NYT Digital", category="News", price=17.0, cadence="mo", lastUsed=12),
    Subscription(id=10, name="Dropbox Plus", category="Storage", price=11.99, cadence="mo", lastUsed=55),
]

SEED_DICTS = [s.model_dump() for s in SEED]

store = SubscriptionStore()


def monthly(sub: Subscription) -> float:
    price = sub.newPrice if sub.status == "negotiated" and sub.newPrice else sub.price
    return price / 12 if sub.cadence == "yr" else price


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "ts": int(time.time())}


@app.get("/subscriptions", response_model=list[Subscription])
def list_subscriptions(user: dict = Depends(get_current_user)) -> list[Subscription]:
    store.seed_user(user["sub"], SEED_DICTS)
    return [Subscription(**s) for s in store.list(user["sub"])]


@app.post("/subscriptions/{sub_id}/action", response_model=ActionResult)
def act_on_subscription(
    sub_id: int, req: ActionRequest, user: dict = Depends(get_current_user)
) -> ActionResult:
    raw = store.get(user["sub"], sub_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="subscription not found")
    sub = Subscription(**raw)
    if sub.status in ("canceled",):
        raise HTTPException(status_code=409, detail="subscription already canceled")

    before = monthly(sub)
    if req.mode == "cancel":
        sub.status = "canceled"
        reclaimed = before
        message = f"{sub.name} canceled. Undo window: 72h."
    elif req.mode == "pause":
        sub.status = "paused"
        reclaimed = before
        message = f"{sub.name} paused. Card frozen, merchant notified."
    else:  # haggle
        sub.status = "negotiated"
        sub.newPrice = round(sub.price * 0.62, 2)
        reclaimed = before - monthly(sub)
        message = f"{sub.name} countered with a retention deal. New rate locked in."

    store.save(user["sub"], sub.model_dump())
    return ActionResult(subscription=sub, reclaimedMonthly=round(reclaimed, 2), message=message)


@app.post("/subscriptions/{sub_id}/undo", response_model=ActionResult)
def undo_subscription(sub_id: int, user: dict = Depends(get_current_user)) -> ActionResult:
    """Reverse a sever/pause/haggle within the undo window."""
    raw = store.get(user["sub"], sub_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="subscription not found")
    sub = Subscription(**raw)
    if sub.status == "active":
        raise HTTPException(status_code=409, detail="nothing to undo")

    base = monthly(Subscription(**{**raw, "status": "active", "newPrice": None}))
    returned = base - monthly(sub) if sub.status == "negotiated" else base

    sub.status = "active"
    sub.newPrice = None
    store.save(user["sub"], sub.model_dump())
    return ActionResult(
        subscription=sub,
        reclaimedMonthly=round(-returned, 2),
        message=f"{sub.name} restored. Card unfrozen.",
    )


@app.post("/reset")
def reset(user: dict = Depends(get_current_user)) -> dict:
    """Sandbox helper: restore the seed data."""
    store.reset(user["sub"], SEED_DICTS)
    return {"status": "reset"}


class IngestItem(BaseModel):
    merchant: str
    category: str = "Uncategorized"
    price: float
    cadence: Literal["mo", "yr"]
    lastUsed: int = 0


@app.post("/internal/ingest")
def ingest(items: list[IngestItem], request: Request, user_id: str = "dev-user") -> dict:
    """Pipeline endpoint: upsert recurring charges detected by ingestion.
    Guarded by a shared token; on ECS this arrives via Secrets Manager."""
    token = os.environ.get("SEVER_INTERNAL_TOKEN")
    if token and request.headers.get("X-Internal-Token") != token:
        raise HTTPException(status_code=403, detail="invalid internal token")

    created = updated = 0
    for item in items:
        outcome = store.upsert_by_name(user_id, item.model_dump())
        if outcome == "created":
            created += 1
        else:
            updated += 1
    return {"created": created, "updated": updated}
