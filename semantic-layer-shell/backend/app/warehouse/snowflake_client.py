from __future__ import annotations

from typing import Any

from app.config.settings import get_settings


class SnowflakeClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._last_error: str | None = None

    def _missing_config(self) -> list[str]:
        required = {
            "SNOWFLAKE_ACCOUNT": self.settings.snowflake_account,
            "SNOWFLAKE_USER": self.settings.snowflake_user,
            "SNOWFLAKE_PASSWORD": self.settings.snowflake_password,
            "SNOWFLAKE_WAREHOUSE": self.settings.snowflake_warehouse,
            "SNOWFLAKE_DATABASE": self.settings.snowflake_database,
            "SNOWFLAKE_SCHEMA": self.settings.snowflake_schema,
        }
        return [k for k, v in required.items() if not v]

    def connect(self) -> bool:
        missing = self._missing_config()
        if missing:
            self._last_error = f"Missing env vars: {', '.join(missing)}"
            return False
        try:
            import snowflake.connector

            conn_kwargs: dict[str, Any] = {
                "account": self.settings.snowflake_account,
                "user": self.settings.snowflake_user,
                "password": self.settings.snowflake_password,
                "warehouse": self.settings.snowflake_warehouse,
                "database": self.settings.snowflake_database,
                "schema": self.settings.snowflake_schema,
            }
            if self.settings.snowflake_role:
                conn_kwargs["role"] = self.settings.snowflake_role

            conn = snowflake.connector.connect(**conn_kwargs)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
            finally:
                conn.close()
            self._last_error = None
            return True
        except Exception as exc:
            self._last_error = str(exc)
            return False

    @property
    def is_configured(self) -> bool:
        return not self._missing_config()

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def execute(self, sql: str) -> tuple[list[dict[str, Any]], list[str]]:
        missing = self._missing_config()
        if missing:
            raise RuntimeError(
                f"Snowflake not configured. Set env vars: {', '.join(missing)}"
            )

        import snowflake.connector

        conn_kwargs: dict[str, Any] = {
            "account": self.settings.snowflake_account,
            "user": self.settings.snowflake_user,
            "password": self.settings.snowflake_password,
            "warehouse": self.settings.snowflake_warehouse,
            "database": self.settings.snowflake_database,
            "schema": self.settings.snowflake_schema,
        }
        if self.settings.snowflake_role:
            conn_kwargs["role"] = self.settings.snowflake_role

        conn = snowflake.connector.connect(**conn_kwargs)
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return rows, columns
        finally:
            conn.close()
