from __future__ import annotations

from typing import Any

from app.config.settings import get_settings


class SnowflakeClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._connected = False

    def connect(self) -> bool:
        if not self.settings.snowflake_account:
            return False
        try:
            import snowflake.connector  # noqa: F401

            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def execute(self, sql: str) -> tuple[list[dict[str, Any]], list[str]]:
        if not self.connect():
            # Dev mock: return empty result set with SQL echoed in logs
            return [], []

        import snowflake.connector

        conn = snowflake.connector.connect(
            account=self.settings.snowflake_account,
            user=self.settings.snowflake_user,
            password=self.settings.snowflake_password,
            warehouse=self.settings.snowflake_warehouse,
            database=self.settings.snowflake_database,
            schema=self.settings.snowflake_schema,
        )
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return rows, columns
        finally:
            conn.close()
