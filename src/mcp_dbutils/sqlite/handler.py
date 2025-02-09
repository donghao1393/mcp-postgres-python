"""SQLite database handler implementation"""

import sqlite3
from pathlib import Path
from contextlib import closing
import mcp.types as types

from ..base import DatabaseHandler
from .config import SqliteConfig

class SqliteHandler(DatabaseHandler):
    def __init__(self, config_path: str, database: str, debug: bool = False):
        """Initialize SQLite handler

        Args:
            config_path: Path to configuration file
            database: Database configuration name
            debug: Enable debug mode
        """
        super().__init__(config_path, database, debug)
        self.config = SqliteConfig.from_yaml(config_path, database)

        # Ensure database directory exists
        db_file = Path(self.config.absolute_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)

        # No connection test during initialization
        self.log("debug", f"Configuring database: {self.config.get_masked_connection_info()}")

    def _get_connection(self):
        """Get database connection"""
        connection_params = self.config.get_connection_params()
        conn = sqlite3.connect(**connection_params)
        conn.row_factory = sqlite3.Row
        return conn

    async def get_tables(self) -> list[types.Resource]:
        """Get all table resources"""
        try:
            with closing(self._get_connection()) as conn:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                tables = cursor.fetchall()

                return [
                    types.Resource(
                        uri=f"sqlite://{self.database}/{table[0]}/schema",
                        name=f"{table[0]} schema",
                        mimeType="application/json"
                    ) for table in tables
                ]
        except sqlite3.Error as e:
            error_msg = f"Failed to get table list: {str(e)}"
            self.log("error", error_msg)
            raise

    async def get_schema(self, table_name: str) -> str:
        """Get table schema information"""
        try:
            with closing(self._get_connection()) as conn:
                # Get table structure
                cursor = conn.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()

                # Get index information
                cursor = conn.execute(f"PRAGMA index_list({table_name})")
                indexes = cursor.fetchall()

                schema_info = {
                    'columns': [{
                        'name': col['name'],
                        'type': col['type'],
                        'nullable': not col['notnull'],
                        'primary_key': bool(col['pk'])
                    } for col in columns],
                    'indexes': [{
                        'name': idx['name'],
                        'unique': bool(idx['unique'])
                    } for idx in indexes]
                }

                return str(schema_info)
        except sqlite3.Error as e:
            error_msg = f"Failed to read table schema: {str(e)}"
            self.log("error", error_msg)
            raise

    async def execute_query(self, sql: str) -> str:
        """Execute SQL query"""
        try:
            with closing(self._get_connection()) as conn:
                self.log("info", f"Executing query: {sql}")
                cursor = conn.execute(sql)
                results = cursor.fetchall()

                columns = [desc[0] for desc in cursor.description]
                formatted_results = [dict(zip(columns, row)) for row in results]

                result_text = str({
                    'columns': columns,
                    'rows': formatted_results,
                    'row_count': len(results)
                })

                self.log("info", f"Query completed, returned {len(results)} rows")
                return result_text

        except sqlite3.Error as e:
            error_msg = f"Query execution failed: {str(e)}"
            self.log("error", error_msg)
            raise

    async def cleanup(self):
        """Cleanup resources"""
        # No special cleanup needed for SQLite
        pass
