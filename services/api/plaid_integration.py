"""SEVER API — Plaid integration.

Thin wrappers over the Plaid SDK so endpoints stay testable (tests
monkeypatch these functions). Credentials arrive via PLAID_CLIENT_ID /
PLAID_SECRET (Secrets Manager on ECS); PLAID_ENV selects sandbox (default)
or production so the same code ships unchanged when Plaid approves
production access.
"""

import os


def configured() -> bool:
    return bool(os.environ.get("PLAID_CLIENT_ID") and os.environ.get("PLAID_SECRET"))


def _client():
    import plaid
    from plaid.api import plaid_api

    env = os.environ.get("PLAID_ENV", "sandbox")
    host = plaid.Environment.Production if env == "production" else plaid.Environment.Sandbox
    configuration = plaid.Configuration(
        host=host,
        api_key={
            "clientId": os.environ["PLAID_CLIENT_ID"],
            "secret": os.environ["PLAID_SECRET"],
        },
    )
    return plaid_api.PlaidApi(plaid.ApiClient(configuration))


def create_link_token(user_id: str) -> str:
    from plaid.model.country_code import CountryCode
    from plaid.model.link_token_create_request import LinkTokenCreateRequest
    from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
    from plaid.model.products import Products

    request = LinkTokenCreateRequest(
        user=LinkTokenCreateRequestUser(client_user_id=user_id),
        client_name="SEVER",
        products=[Products("transactions")],
        country_codes=[CountryCode("US")],
        language="en",
    )
    return _client().link_token_create(request)["link_token"]


def exchange_public_token(public_token: str) -> tuple[str, str]:
    """Returns (access_token, item_id)."""
    from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest

    response = _client().item_public_token_exchange(
        ItemPublicTokenExchangeRequest(public_token=public_token)
    )
    return response["access_token"], response["item_id"]


_YEARLY = {"ANNUALLY", "SEMI_ANNUALLY"}


def fetch_recurring(access_token: str) -> list[dict]:
    """Recurring outflow streams for one bank connection, as ledger items."""
    from plaid.model.transactions_recurring_get_request import TransactionsRecurringGetRequest

    response = _client().transactions_recurring_get(
        TransactionsRecurringGetRequest(access_token=access_token)
    )
    items = []
    for stream in response.outflow_streams:
        if not getattr(stream, "is_active", True):
            continue
        from datetime import date

        cadence = "yr" if str(stream.frequency).upper() in _YEARLY else "mo"
        items.append(
            {
                "merchant": stream.merchant_name or stream.description,
                "category": "Uncategorized",
                "price": round(abs(float(stream.average_amount.amount)), 2),
                "cadence": cadence,
                "lastUsed": max(0, (date.today() - stream.last_date).days),
            }
        )
    return items


def remove_item(access_token: str) -> None:
    """Revokes a bank connection at Plaid (best effort on disconnect)."""
    from plaid.model.item_remove_request import ItemRemoveRequest

    _client().item_remove(ItemRemoveRequest(access_token=access_token))
