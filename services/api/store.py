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

_BANKS_SCHEMA = """
CREATE TABLE IF NOT EXISTS bank_connections (
    user_id          TEXT NOT NULL,
    connection_id    TEXT NOT NULL,
    item_id          TEXT NOT NULL DEFAULT '',
    institution      TEXT NOT NULL DEFAULT '',
    access_token_enc TEXT NOT NULL,
    created_at       TEXT NOT NULL,
    PRIMARY KEY (user_id, connection_id)
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
            conn.execute(_BANKS_SCHEMA)

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

    def delete_user(self, user_id: str) -> int:
        """Permanently remove all data for a user. Returns rows deleted."""
        with self._db() as conn:
            conn.execute("DELETE FROM bank_connections WHERE user_id = ?", (user_id,))
            cur = conn.execute("DELETE FROM subscriptions WHERE user_id = ?", (user_id,))
            return cur.rowcount

    def add_bank(self, user_id: str, connection: dict) -> None:
        with self._db() as conn:
            conn.execute(
                """INSERT INTO bank_connections
                   (user_id, connection_id, item_id, institution, access_token_enc, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    user_id, connection["connectionId"], connection["itemId"],
                    connection["institution"], connection["accessTokenEnc"], connection["createdAt"],
                ),
            )

    def list_banks(self, user_id: str) -> list[dict]:
        """Public listing — never includes tokens."""
        with self._db() as conn:
            rows = conn.execute(
                "SELECT connection_id, institution, created_at FROM bank_connections WHERE user_id = ? ORDER BY created_at",
                (user_id,),
            ).fetchall()
            return [{"connectionId": r["connection_id"], "institution": r["institution"], "createdAt": r["created_at"]} for r in rows]

    def get_bank(self, user_id: str, connection_id: str) -> Optional[dict]:
        with self._db() as conn:
            r = conn.execute(
                "SELECT * FROM bank_connections WHERE user_id = ? AND connection_id = ?",
                (user_id, connection_id),
            ).fetchone()
            if not r:
                return None
            return {"connectionId": r["connection_id"], "institution": r["institution"], "accessTokenEnc": r["access_token_enc"]}

    def bank_tokens(self, user_id: str) -> list[dict]:
        with self._db() as conn:
            rows = conn.execute(
                "SELECT connection_id, access_token_enc FROM bank_connections WHERE user_id = ?", (user_id,)
            ).fetchall()
            return [{"connectionId": r["connection_id"], "accessTokenEnc": r["access_token_enc"]} for r in rows]

    def delete_bank(self, user_id: str, connection_id: str) -> bool:
        with self._db() as conn:
            cur = conn.execute(
                "DELETE FROM bank_connections WHERE user_id = ? AND connection_id = ?", (user_id, connection_id)
            )
            return cur.rowcount > 0

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
