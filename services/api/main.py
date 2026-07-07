"""SEVER API — REST endpoints backing the frontend.

Beta implementation: in-memory store seeded with sandbox data.
Swap the store for RDS/DynamoDB when infrastructure is provisioned.
"""

import time
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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

_store: dict[int, Subscription] = {s.id: s.model_copy() for s in SEED}


def monthly(sub: Subscription) -> float:
    price = sub.newPrice if sub.status == "negotiated" and sub.newPrice else sub.price
    return price / 12 if sub.cadence == "yr" else price


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "ts": int(time.time())}


@app.get("/subscriptions", response_model=list[Subscription])
def list_subscriptions() -> list[Subscription]:
    return list(_store.values())


@app.post("/subscriptions/{sub_id}/action", response_model=ActionResult)
def act_on_subscription(sub_id: int, req: ActionRequest) -> ActionResult:
    sub = _store.get(sub_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="subscription not found")
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

    return ActionResult(subscription=sub, reclaimedMonthly=round(reclaimed, 2), message=message)


@app.post("/reset")
def reset() -> dict:
    """Sandbox helper: restore the seed data."""
    _store.clear()
    _store.update({s.id: s.model_copy() for s in SEED})
    return {"status": "reset"}
