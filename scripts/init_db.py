"""Creates tables and converts time-series tables into TimescaleDB hypertables.

Run once after `docker compose up -d timescaledb` (or whenever the schema changes):
    uv run python scripts/init_db.py
"""

import asyncio

from alphadesk.config import get_settings
from alphadesk.db.base import Database
from alphadesk.db.models import HYPERTABLES


async def main() -> None:
    settings = get_settings()
    db = Database(settings.database_url)
    await db.create_all()

    async with db._engine.begin() as conn:  # noqa: SLF001 - one-off DDL, not app traffic
        for table in HYPERTABLES:
            await conn.exec_driver_sql(
                f"SELECT create_hypertable('{table}', 'ts', if_not_exists => TRUE, "
                f"migrate_data => TRUE);"
            )
    await db.dispose()
    print(f"Initialized tables and hypertables: {', '.join(HYPERTABLES)}")


if __name__ == "__main__":
    asyncio.run(main())
