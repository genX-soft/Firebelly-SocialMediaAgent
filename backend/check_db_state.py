from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
import os

# Assuming sqlite for simplicity based on previous context, but will use the real DB from db.py if possible
try:
    from db import SQLALCHEMY_DATABASE_URL
except ImportError:
    SQLALCHEMY_DATABASE_URL = "sqlite:///./autosocial.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)

try:
    from models import SocialAccount, User
except ImportError:
    # If models can't be imported, this script might fail, so let's try direct SQL
    pass

with engine.connect() as conn:
    from sqlalchemy import text
    result = conn.execute(text("SELECT user_email, platform, external_id, page_name, instagram_username FROM social_accounts"))
    print("--- Social Accounts in DB ---")
    for row in result:
        print(row)

    result_users = conn.execute(text("SELECT email, name FROM users"))
    print("\n--- Users in DB ---")
    for row in result_users:
        print(row)
