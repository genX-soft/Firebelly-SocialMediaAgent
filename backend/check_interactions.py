from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")
engine = create_engine(db_url)

with engine.connect() as conn:
    print("--- Latest 10 Interactions for john@gmail.com ---")
    res = conn.execute(text("SELECT id, platform, external_id, content, type, created_at FROM interactions WHERE user_email = 'john@gmail.com' ORDER BY created_at DESC LIMIT 10"))
    for row in res:
        print(row)
