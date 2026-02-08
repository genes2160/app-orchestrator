from typing import List, Optional
from manager.db import get_connection
from manager.models import AppModel


class AppRepository:
    def list(self) -> List[AppModel]:
        conn = get_connection()
        rows = conn.execute("SELECT * FROM apps ORDER BY name").fetchall()
        conn.close()
        return [self._row_to_model(r) for r in rows]

    def get(self, app_id: int) -> Optional[AppModel]:
        conn = get_connection()
        row = conn.execute("SELECT * FROM apps WHERE id = ?", (app_id,)).fetchone()
        conn.close()
        return self._row_to_model(row) if row else None

    def get_by_name(self, name: str) -> Optional[AppModel]:
        conn = get_connection()
        row = conn.execute("SELECT * FROM apps WHERE name = ?", (name,)).fetchone()
        conn.close()
        return self._row_to_model(row) if row else None

    def exists_by_name_other_id(self, name: str, app_id: int) -> bool:
        conn = get_connection()
        row = conn.execute(
            "SELECT 1 FROM apps WHERE name = ? AND id != ? LIMIT 1",
            (name, app_id),
        ).fetchone()
        conn.close()
        return bool(row)

    def create(
        self,
        *,
        name: str,
        path: str,
        entry: str,
        port: int,
        host: str = "127.0.0.1",
        args: Optional[str] = None,
        enabled: bool = True,
    ) -> AppModel:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO apps (name, path, entry, host, port, args, enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (name, path, entry, host, port, args, int(enabled)),
        )
        conn.commit()
        app_id = cur.lastrowid
        conn.close()
        return self.get(app_id)

    def upsert_by_name(
        self,
        *,
        name: str,
        path: str,
        entry: str,
        port: int,
        host: str = "127.0.0.1",
        args: Optional[str] = None,
        enabled: bool = True,
    ) -> AppModel:
        """
        Insert if missing; otherwise update by name.
        Used for one-time apps.yaml import.
        """
        existing = self.get_by_name(name)
        if not existing:
            return self.create(
                name=name,
                path=path,
                entry=entry,
                port=port,
                host=host,
                args=args,
                enabled=enabled,
            )

        return self.update(
            existing.id,
            name=name,
            path=path,
            entry=entry,
            port=port,
            host=host,
            args=args,
            enabled=enabled,
        )

    def update(
        self,
        app_id: int,
        *,
        name: str,
        path: str,
        entry: str,
        port: int,
        host: str,
        args: Optional[str],
        enabled: bool,
    ) -> Optional[AppModel]:
        conn = get_connection()
        conn.execute(
            """
            UPDATE apps
            SET name = ?, path = ?, entry = ?, host = ?, port = ?, args = ?, enabled = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (name, path, entry, host, port, args, int(enabled), app_id),
        )
        conn.commit()
        conn.close()
        return self.get(app_id)

    def delete(self, app_id: int) -> bool:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM apps WHERE id = ?", (app_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    def _row_to_model(self, r) -> AppModel:
        return AppModel(
            id=r["id"],
            name=r["name"],
            path=r["path"],
            entry=r["entry"],
            host=r["host"],
            port=r["port"],
            args=r["args"],
            enabled=bool(r["enabled"]),
        )
