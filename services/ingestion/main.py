"""SEVER Ingestion — pulls transactions and detects recurring charges.

Runs in one of two modes controlled by SEVER_INGEST_MODE:
- "sandbox" (default): generates deterministic sample transactions locally,
  no network or Plaid credentials required.
- "plaid": pulls from the Plaid sandbox environment. Requires
  PLAID_CLIENT_ID, PLAID_SECRET, and PLAID_ACCESS_TOKEN env vars.
"""

import os
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class Transaction:
    merchant: str
    amount: float
    posted: date
    account: str


@dataclass(frozen=True)
class RecurringCharge:
    merchant: str
    amount: float
    cadence: str  # "mo" | "yr"
    occurrences: int
    last_seen: date


def sample_transactions(today: date | None = None) -> list[Transaction]:
    """Deterministic sandbox feed: three months of recurring + noise."""
    today = today or date.today()
    txns: list[Transaction] = []
    recurring = [
        ("Netflix", 15.49, "4296"),
        ("Spotify Premium", 11.99, "4148"),
        ("Peak Fitness Gym", 44.00, "4111"),
        ("Adobe Creative Cloud", 59.99, "4148"),
    ]
    for months_ago in (0, 1, 2):
        posted = today - timedelta(days=30 * months_ago)
        for merchant, amount, account in recurring:
            txns.append(Transaction(merchant, amount, posted, account))
    # one-off noise that must NOT be flagged as recurring
    txns.append(Transaction("Corner Deli", 12.40, today, "4296"))
    txns.append(Transaction("Hardware Store", 84.99, today - timedelta(days=3), "4111"))
    return txns


def detect_recurring(txns: list[Transaction], min_occurrences: int = 3) -> list[RecurringCharge]:
    """Group by (merchant, amount); recurring = appears in >= min_occurrences distinct months."""
    groups: dict[tuple[str, float], list[Transaction]] = defaultdict(list)
    for t in txns:
        groups[(t.merchant, t.amount)].append(t)

    charges: list[RecurringCharge] = []
    for (merchant, amount), items in groups.items():
        months = {(t.posted.year, t.posted.month) for t in items}
        if len(months) >= min_occurrences:
            gaps = sorted(t.posted for t in items)
            span_days = (gaps[-1] - gaps[0]).days / max(1, len(gaps) - 1)
            cadence = "yr" if span_days > 180 else "mo"
            charges.append(
                RecurringCharge(
                    merchant=merchant,
                    amount=amount,
                    cadence=cadence,
                    occurrences=len(items),
                    last_seen=max(t.posted for t in items),
                )
            )
    return sorted(charges, key=lambda c: c.merchant)


def fetch_transactions() -> list[Transaction]:
    mode = os.environ.get("SEVER_INGEST_MODE", "sandbox")
    if mode == "sandbox":
        return sample_transactions()
    if mode == "plaid":
        return _fetch_from_plaid()
    raise ValueError(f"unknown SEVER_INGEST_MODE: {mode}")


def _fetch_from_plaid() -> list[Transaction]:
    """Pull transactions from the Plaid sandbox. Imported lazily so the
    sandbox mode has no Plaid dependency at runtime."""
    import plaid
    from plaid.api import plaid_api
    from plaid.model.transactions_get_request import TransactionsGetRequest

    configuration = plaid.Configuration(
        host=plaid.Environment.Sandbox,
        api_key={
            "clientId": os.environ["PLAID_CLIENT_ID"],
            "secret": os.environ["PLAID_SECRET"],
        },
    )
    client = plaid_api.PlaidApi(plaid.ApiClient(configuration))
    request = TransactionsGetRequest(
        access_token=os.environ["PLAID_ACCESS_TOKEN"],
        start_date=date.today() - timedelta(days=90),
        end_date=date.today(),
    )
    response = client.transactions_get(request)
    return [
        Transaction(
            merchant=t.merchant_name or t.name,
            amount=float(t.amount),
            posted=t.date,
            account=t.account_id[-4:],
        )
        for t in response.transactions
    ]


def main() -> None:
    interval = int(os.environ.get("SEVER_SYNC_INTERVAL", "0"))
    while True:
        run_pipeline()
        if interval <= 0:
            break
        time.sleep(interval)


def charges_to_items(charges: list[RecurringCharge], ner_results: list[dict] | None = None) -> list[dict]:
    """Convert detected charges to API ingest items, using NER matches
    (keyed by raw descriptor) to canonicalize merchant names/categories."""
    ner_map = {r["raw"]: r for r in (ner_results or []) if r.get("merchant")}
    items = []
    for c in charges:
        match = ner_map.get(c.merchant)
        items.append(
            {
                "merchant": match["merchant"] if match else c.merchant,
                "category": match["category"] if match else "Uncategorized",
                "price": c.amount,
                "cadence": c.cadence,
                "lastUsed": max(0, (date.today() - c.last_seen).days),
            }
        )
    return items


def run_pipeline() -> int:
    """One sync: fetch -> detect -> enrich via NER service -> push to API.
    NER_PARSER_URL and SEVER_API_URL are optional; missing pieces degrade
    to local printing so the service works standalone."""
    txns = fetch_transactions()
    charges = detect_recurring(txns)

    ner_results = None
    ner_url = os.environ.get("NER_PARSER_URL")
    if ner_url and charges:
        import httpx

        resp = httpx.post(
            f"{ner_url.rstrip('/')}/parse",
            json={"descriptors": [c.merchant for c in charges]},
            timeout=10,
        )
        resp.raise_for_status()
        ner_results = resp.json()["results"]

    items = charges_to_items(charges, ner_results)

    api_url = os.environ.get("SEVER_API_URL")
    if api_url and items:
        import httpx

        headers = {}
        token = os.environ.get("SEVER_INTERNAL_TOKEN")
        if token:
            headers["X-Internal-Token"] = token
        resp = httpx.post(f"{api_url.rstrip('/')}/internal/ingest", json=items, headers=headers, timeout=10)
        resp.raise_for_status()
        print(f"Synced {len(items)} recurring charges to API: {resp.json()}")
    else:
        print(f"Ingested {len(txns)} transactions; {len(items)} recurring charges detected:")
        for item in items:
            print(f"  {item['merchant']}: ${item['price']:.2f}/{item['cadence']} ({item['category']})")
    return len(items)


if __name__ == "__main__":
    main()
