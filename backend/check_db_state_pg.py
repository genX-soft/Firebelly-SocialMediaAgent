from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")
engine = create_engine(db_url)

with engine.connect() as conn:
    print("--- Social Accounts ---")
    res = conn.execute(text("SELECT id, user_email, platform, external_id, page_name FROM social_accounts"))
    for row in res:
        print(row)

    print("\n--- Users ---")
    res = conn.execute(text("SELECT email, name FROM users"))
    for row in res:
        print(row)
