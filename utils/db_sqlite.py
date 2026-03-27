import aiosqlite
import os

DB_PATH = "grim5.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS calculations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                calc_type TEXT,
                input_data TEXT,
                output_data TEXT
            )
        ''')
        await db.commit()
