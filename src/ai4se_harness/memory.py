"""基于 SQLite 的跨会话记忆存储."""
import json
import sqlite3


class MemoryStore:
    def __init__(self, db_path: str = "memory.db"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_table()

    def _init_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def store(self, key: str, value: dict) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO memories (key, value) VALUES (?, ?)",
            (key, json.dumps(value))
        )
        self.conn.commit()

    def retrieve(self, query: str, top_k: int = 3) -> list[dict]:
        cursor = self.conn.execute(
            "SELECT key, value FROM memories WHERE key LIKE ? LIMIT ?",
            (f"%{query}%", top_k)
        )
        results = []
        for row in cursor:
            item = json.loads(row["value"])
            item["key"] = row["key"]
            results.append(item)
        return results

    def forget(self, key: str) -> None:
        self.conn.execute("DELETE FROM memories WHERE key = ?", (key,))
        self.conn.commit()

    def list_keys(self) -> list[str]:
        return [row[0] for row in self.conn.execute("SELECT key FROM memories")]

    def close(self):
        self.conn.close()