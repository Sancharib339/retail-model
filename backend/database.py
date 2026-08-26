"""
Thread-safe SQLite persistence layer for entry/exit events, raw position
samples (for offline heatmap analysis), and periodic occupancy snapshots.
"""
import os
import sqlite3
import threading
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._create_tables()
        logger.info(f"SQLite database ready at {db_path}")

    def _create_tables(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    x REAL, y REAL,
                    timestamp TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_id INTEGER NOT NULL,
                    x REAL, y REAL,
                    timestamp TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS occupancy_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    occupancy INTEGER NOT NULL,
                    total_entries INTEGER NOT NULL,
                    total_exits INTEGER NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            self._conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def log_event(self, track_id: int, event_type: str, x: float, y: float) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO events (track_id, event_type, x, y, timestamp) VALUES (?, ?, ?, ?, ?)",
                (track_id, event_type, x, y, self._now()),
            )
            self._conn.commit()
        logger.debug(f"DB: logged {event_type} for track {track_id}")

    def log_position(self, track_id: int, x: float, y: float) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO positions (track_id, x, y, timestamp) VALUES (?, ?, ?, ?)",
                (track_id, x, y, self._now()),
            )
            self._conn.commit()

    def log_occupancy(self, occupancy: int, total_entries: int, total_exits: int) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO occupancy_log (occupancy, total_entries, total_exits, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (occupancy, total_entries, total_exits, self._now()),
            )
            self._conn.commit()

    def get_event_counts(self) -> dict:
        with self._lock:
            rows = self._conn.execute(
                "SELECT event_type, COUNT(*) FROM events GROUP BY event_type"
            ).fetchall()
        result = {"entry": 0, "exit": 0}
        for event_type, count in rows:
            result[event_type] = count
        return result

    def close(self) -> None:
        with self._lock:
            self._conn.close()
        logger.info("Database connection closed.")
