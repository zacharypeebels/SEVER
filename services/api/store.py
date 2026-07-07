"""SEVER API — persistence layer.

SQLite-backed, per-user subscription store. The database path comes from
SEVER_DB_PATH (default: sever.db beside the service). The interface is
deliberately narrow so it can be reimplemented over DynamoDB/RDS without
touching the API layer.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS subscriptions (
    user_id   TEXT    NOT NULL,
    id        INTEGER NOT NULL,
    name      TEXT    NOT NULL,
    category  TEXT    NOT NULL,
    price     REAL    NOT NULL,
    cadence   TEXT    NOT NULL,
    last_used INTEGER NOT NULL DEFAULT 0,
    status    TEXT    NOT NULL DEFAULT 'active',
    new_price REAL,
    PRIMARY KEY (user_id, id)
)
"""


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "category": row["category"],
        "price": row["price"],
        "cadence": row["cadence"],
        "lastUsed": row["last_used"],
        "status": row["status"],
        "newPrice": row["new_price"],
    }


class SubscriptionStore:
    def __init__(self, path: Optional[str] = None):
        default = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sever.db")
        self.path = path or os.environ.get("SEVER_DB_PATH", default)
        with self._db() as conn:
            conn.execute(_SCHEMA)

    @contextmanager
    def _db(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def seed_user(self, user_id: str, seed: list[dict]) -> bool:
        """Populate a first-time user's ledger. Returns True if seeded."""
        with self._db() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM subscriptions WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
            if count:
                return False
            self._insert_many(conn, user_id, seed)
            return True

    def list(self, user_id: str) -> list[dict]:
        with self._db() as conn:
            rows = conn.execute(
                "SELECT * FROM subscriptions WHERE user_id = ? ORDER BY id", (user_id,)
            ).fetchall()
            return [_row_to_dict(r) for r in rows]

    def get(self, user_id: str, sub_id: int) -> Optional[dict]:
        with self._db() as conn:
            row = conn.execute(
                "SELECT * FROM subscriptions WHERE user_id = ? AND id = ?", (user_id, sub_id)
            ).fetchone()
            return _row_to_dict(row) if row else None

    def save(self, user_id: str, sub: dict) -> None:
        with self._db() as conn:
            conn.execute(
                """UPDATE subscriptions
                   SET name=?, category=?, price=?, cadence=?, last_used=?, status=?, new_price=?
                   WHERE user_id=? AND id=?""",
                (
                    sub["name"], sub["category"], sub["price"], sub["cadence"],
                    sub["lastUsed"], sub["status"], sub.get("newPrice"),
                    user_id, sub["id"],
                ),
            )

    def upsert_by_name(self, user_id: str, item: dict) -> str:
        """Insert or update a charge keyed on merchant name. Returns 'created' or 'updated'."""
        with self._db() as conn:
            row = conn.execute(
                "SELECT id FROM subscriptions WHERE user_id = ? AND name = ?",
                (user_id, item["merchant"]),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE subscriptions SET price=?, cadence=?, last_used=? WHERE user_id=? AND id=?",
                    (item["price"], item["cadence"], item["lastUsed"], user_id, row["id"]),
                )
                return "updated"
            next_id = conn.execute(
                "SELECT COALESCE(MAX(id), 0) + 1 FROM subscriptions WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
            conn.execute(
                """INSERT INTO subscriptions (user_id, id, name, category, price, cadence, last_used)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id, next_id, item["merchant"], item["category"],
                    item["price"], item["cadence"], item["lastUsed"],
                ),
            )
            return "created"

    def reset(self, user_id: str, seed: list[dict]) -> None:
        with self._db() as conn:
            conn.execute("DELETE FROM subscriptions WHERE user_id = ?", (user_id,))
            self._insert_many(conn, user_id, seed)

    @staticmethod
    def _insert_many(conn: sqlite3.Connection, user_id: str, subs: list[dict]) -> None:
        conn.executemany(
            """INSERT INTO subscriptions
               (user_id, id, name, category, price, cadence, last_used, status, new_price)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    user_id, s["id"], s["name"], s["category"], s["price"], s["cadence"],
                    s["lastUsed"], s.get("status", "active"), s.get("newPrice"),
                )
                for s in subs
            ],
        )
