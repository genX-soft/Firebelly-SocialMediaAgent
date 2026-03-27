from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")
engine = create_engine(db_url)

with engine.connect() as conn:
    print("--- 20 Most Recent Interactions ---")
    res = conn.execute(text("SELECT platform, type, content, is_outgoing, created_at, external_id FROM interactions ORDER BY created_at DESC LIMIT 20"))
    for row in res:
        print(row)
