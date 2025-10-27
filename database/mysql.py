import mysql.connector
from mysql.connector import Error
from datetime import datetime
from schema import ClipboardLog, Shared

class MySQLOps:
    def __init__(self, host: str, user: str, password: str, database: str, port: int = 3306) -> None:
        self.conn = mysql.connector.connect(
            host=host, user=user, password=password, database=database, port=port
        )
        self.cursor = self.conn.cursor(buffered=True)

    def close(self) -> None:
        try:
            if self.cursor:
                self.cursor.close()
            if self.conn:
                self.conn.close()
        except Exception:
            pass

    def insert_clipboard_log(self, payload: dict | ClipboardLog) -> None:
        """
        Validate payload with ClipboardLog model and insert into clipboard_log table.
        Expects table columns: itemId, deviceId, userId, mime, metadata, creation, ttl, status
        """
        # validate / coerce with pydantic
        model = payload if isinstance(payload, ClipboardLog) else ClipboardLog(**payload)

        sql = """
            INSERT INTO clipboard_log
            (itemId, deviceId, userId, mime, metadata, creation, ttl, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            model.itemId,
            model.deviceId,
            model.userId,
            model.mime,
            model.metadata,
            model.creation,
            model.ttl,
            model.status,
        )

        try:
            self.cursor.execute(sql, params)
            self.conn.commit()
        except Error as e:
            self.conn.rollback()
            raise

    def insert_share_log(self, payload: dict | Shared) -> None:
        """
        Validate payload with Shared model and insert into share_log table.
        Ensures referenced (itemId, userId) exists in clipboard_log before inserting
        (to respect the FK constraint).
        Expects table columns: itemId, userId, targetId, shared_at
        """
        model = payload if isinstance(payload, Shared) else Shared(**payload)

        # ensure referenced clipboard row exists
        check_sql = "SELECT 1 FROM clipboard_log WHERE itemId = %s AND userId = %s LIMIT 1"
        self.cursor.execute(check_sql, (model.itemId, model.userId))
        if not self.cursor.fetchone():
            raise ValueError(f"Referenced clipboard_log (itemId={model.itemId}, userId={model.userId}) not found")

        insert_sql = """
            INSERT INTO share_log
            (itemId, userId, targetId, shared_at)
            VALUES (%s, %s, %s, %s)
        """
        params = (model.itemId, model.userId, model.targetId, datetime.now())

        try:
            self.cursor.execute(insert_sql, params)
            self.conn.commit()
        except Error as e:
            self.conn.rollback()
            raise

            