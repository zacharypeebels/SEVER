"""SEVER API — PostgreSQL persistence (the ACID system of record).

Same interface as store.SubscriptionStore. Selected at startup via
SEVER_STORE=postgres; the DSN arrives in DATABASE_URL (injected from
Secrets Manager on ECS). Every method runs in a single transaction —
commit on success, rollback on any error.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Optional

import psycopg
from psycopg.rows import dict_row

_SCHEMA = """
CREATE TABLE IF NOT EXISTS subscriptions (
    user_id   TEXT           NOT NULL,
    id        INTEGER        NOT NULL,
    name      TEXT           NOT NULL,
    category  TEXT           NOT NULL,
    price     NUMERIC(10,2)  NOT NULL,
    cadence   TEXT           NOT NULL,
    last_used INTEGER        NOT NULL DEFAULT 0,
    status    TEXT           NOT NULL DEFAULT 'active',
    new_price NUMERIC(10,2),
    PRIMARY KEY (user_id, id)
)
"""


def _row_to_dict(row: dict) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "category": row["category"],
        "price": float(row["price"]),
        "cadence": row["cadence"],
        "lastUsed": row["last_used"],
        "status": row["status"],
        "newPrice": float(row["new_price"]) if row["new_price"] is not None else None,
    }


class PostgresSubscriptionStore:
    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn or os.environ["DATABASE_URL"]
        with self._db() as conn:
            conn.execute(_SCHEMA)

    @contextmanager
    def _db(self):
        # One connection = one transaction: commits on clean exit,
        # rolls back automatically if anything raises.
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            yield conn

    def seed_user(self, user_id: str, seed: list[dict]) -> bool:
        with self._db() as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM subscriptions WHERE user_id = %s", (user_id,)
            ).fetchone()["n"]
            if count:
                return False
            self._insert_many(conn, user_id, seed)
            return True

    def list(self, user_id: str) -> list[dict]:
        with self._db() as conn:
            rows = conn.execute(
                "SELECT * FROM subscriptions WHERE user_id = %s ORDER BY id", (user_id,)
            ).fetchall()
            return [_row_to_dict(r) for r in rows]

    def get(self, user_id: str, sub_id: int) -> Optional[dict]:
        with self._db() as conn:
            row = conn.execute(
                "SELECT * FROM subscriptions WHERE user_id = %s AND id = %s", (user_id, sub_id)
            ).fetchone()
            return _row_to_dict(row) if row else None

    def save(self, user_id: str, sub: dict) -> None:
        with self._db() as conn:
            conn.execute(
                """UPDATE subscriptions
                   SET name=%s, category=%s, price=%s, cadence=%s, last_used=%s, status=%s, new_price=%s
                   WHERE user_id=%s AND id=%s""",
                (
                    sub["name"], sub["category"], sub["price"], sub["cadence"],
                    sub["lastUsed"], sub["status"], sub.get("newPrice"),
                    user_id, sub["id"],
                ),
            )

    def upsert_by_name(self, user_id: str, item: dict) -> str:
        with self._db() as conn:
            row = conn.execute(
                "SELECT id FROM subscriptions WHERE user_id = %s AND name = %s FOR UPDATE",
                (user_id, item["merchant"]),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE subscriptions SET price=%s, cadence=%s, last_used=%s WHERE user_id=%s AND id=%s",
                    (item["price"], item["cadence"], item["lastUsed"], user_id, row["id"]),
                )
                return "updated"
            next_id = conn.execute(
                "SELECT COALESCE(MAX(id), 0) + 1 AS next FROM subscriptions WHERE user_id = %s",
                (user_id,),
            ).fetchone()["next"]
            conn.execute(
                """INSERT INTO subscriptions (user_id, id, name, category, price, cadence, last_used)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (
                    user_id, next_id, item["merchant"], item["category"],
                    item["price"], item["cadence"], item["lastUsed"],
                ),
            )
            return "created"

    def reset(self, user_id: str, seed: list[dict]) -> None:
        with self._db() as conn:
            conn.execute("DELETE FROM subscriptions WHERE user_id = %s", (user_id,))
            self._insert_many(conn, user_id, seed)

    def delete_user(self, user_id: str) -> int:
        """Permanently remove all data for a user. Returns rows deleted."""
        with self._db() as conn:
            cur = conn.execute("DELETE FROM subscriptions WHERE user_id = %s", (user_id,))
            return cur.rowcount

    @staticmethod
    def _insert_many(conn, user_id: str, subs: list[dict]) -> None:
        conn.cursor().executemany(
            """INSERT INTO subscriptions
               (user_id, id, name, category, price, cadence, last_used, status, new_price)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            [
                (
                    user_id, s["id"], s["name"], s["category"], s["price"], s["cadence"],
                    s["lastUsed"], s.get("status", "active"), s.get("newPrice"),
                )
                for s in subs
            ],
        )
