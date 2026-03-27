"""
tools/memory_tools.py
----------------------
Customer memory system — two layers:
  1. Conversation memory: last N messages per customer per platform
  2. Customer profile: long-term profile built over time

Storage: PostgreSQL (same DB as the rest of the app)
"""

import json
import secrets
from datetime import datetime
from sqlalchemy import text
from langchain_core.tools import tool
from config.cms_client import TENANT_ID

# Import the existing DB session from main app
try:
    from db import SessionLocal
except ImportError:
    from db import SessionLocal


MAX_CONVERSATION_TURNS = 10  # keep last 10 messages per thread


# ── Database schema (run once on startup) ─────────────────────────────────────

MEMORY_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS conversation_memory (
    id              VARCHAR(32) PRIMARY KEY,
    restaurant_id   VARCHAR(128) NOT NULL,
    platform        VARCHAR(32) NOT NULL,
    customer_id     VARCHAR(255) NOT NULL,
    role            VARCHAR(16) NOT NULL,   -- 'user' or 'assistant'
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS customer_profiles (
    id                  VARCHAR(32) PRIMARY KEY,
    restaurant_id       VARCHAR(128) NOT NULL,
    platform            VARCHAR(32) NOT NULL,
    customer_id         VARCHAR(255) NOT NULL,
    customer_name       VARCHAR(120),
    visit_count         INTEGER DEFAULT 0,
    message_count       INTEGER DEFAULT 0,
    sentiment_trend     VARCHAR(32) DEFAULT 'neutral',
    topics_of_interest  TEXT DEFAULT '[]',
    escalation_count    INTEGER DEFAULT 0,
    last_interaction    TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(restaurant_id, platform, customer_id)
);
"""


def ensure_memory_schema():
    """Create memory tables if they don't exist. Call on app startup."""
    try:
        with SessionLocal() as db:
            for statement in MEMORY_SCHEMA_SQL.strip().split(";"):
                stmt = statement.strip()
                if stmt:
                    db.execute(text(stmt))
            db.commit()
        print("INFO [Memory]: Schema verified.")
    except Exception as e:
        print(f"WARNING [Memory]: Could not create schema: {e}")


# ── Core memory functions ─────────────────────────────────────────────────────

def save_message(
    platform: str,
    customer_id: str,
    role: str,
    content: str,
    restaurant_id: str = TENANT_ID,
):
    """Save a single message to conversation memory."""
    try:
        with SessionLocal() as db:
            db.execute(text("""
                INSERT INTO conversation_memory
                    (id, restaurant_id, platform, customer_id, role, content, created_at)
                VALUES
                    (:id, :restaurant_id, :platform, :customer_id, :role, :content, NOW())
            """), {
                "id": secrets.token_hex(16),
                "restaurant_id": restaurant_id,
                "platform": platform,
                "customer_id": customer_id,
                "role": role,
                "content": content,
            })
            db.commit()
    except Exception as e:
        print(f"WARNING [Memory]: Could not save message: {e}")


def get_conversation_history(
    platform: str,
    customer_id: str,
    restaurant_id: str = TENANT_ID,
    limit: int = MAX_CONVERSATION_TURNS,
) -> list[dict]:
    """
    Retrieve the last N messages for a customer.
    Returns list of {role, content} dicts ready for LangChain.
    """
    try:
        with SessionLocal() as db:
            rows = db.execute(text("""
                SELECT role, content FROM conversation_memory
                WHERE restaurant_id = :restaurant_id
                  AND platform = :platform
                  AND customer_id = :customer_id
                ORDER BY created_at DESC
                LIMIT :limit
            """), {
                "restaurant_id": restaurant_id,
                "platform": platform,
                "customer_id": customer_id,
                "limit": limit,
            }).fetchall()

            # Reverse so oldest is first (LLM expects chronological order)
            return [{"role": row[0], "content": row[1]} for row in reversed(rows)]
    except Exception as e:
        print(f"WARNING [Memory]: Could not fetch history: {e}")
        return []


def update_customer_profile(
    platform: str,
    customer_id: str,
    customer_name: str | None = None,
    sentiment: str = "neutral",
    topics: list[str] | None = None,
    escalated: bool = False,
    restaurant_id: str = TENANT_ID,
):
    """Upsert customer profile — called after every interaction."""
    try:
        with SessionLocal() as db:
            existing = db.execute(text("""
                SELECT id, visit_count, message_count, topics_of_interest, escalation_count
                FROM customer_profiles
                WHERE restaurant_id = :restaurant_id
                  AND platform = :platform
                  AND customer_id = :customer_id
            """), {
                "restaurant_id": restaurant_id,
                "platform": platform,
                "customer_id": customer_id,
            }).fetchone()

            if existing:
                existing_topics = json.loads(existing[3] or "[]")
                if topics:
                    merged = list(set(existing_topics + topics))[:20]
                else:
                    merged = existing_topics

                db.execute(text("""
                    UPDATE customer_profiles SET
                        customer_name       = COALESCE(:name, customer_name),
                        message_count       = message_count + 1,
                        sentiment_trend     = :sentiment,
                        topics_of_interest  = :topics,
                        escalation_count    = escalation_count + :escalated,
                        last_interaction    = NOW(),
                        updated_at          = NOW()
                    WHERE restaurant_id = :restaurant_id
                      AND platform = :platform
                      AND customer_id = :customer_id
                """), {
                    "name": customer_name,
                    "sentiment": sentiment,
                    "topics": json.dumps(merged),
                    "escalated": 1 if escalated else 0,
                    "restaurant_id": restaurant_id,
                    "platform": platform,
                    "customer_id": customer_id,
                })
            else:
                db.execute(text("""
                    INSERT INTO customer_profiles
                        (id, restaurant_id, platform, customer_id, customer_name,
                         visit_count, message_count, sentiment_trend,
                         topics_of_interest, escalation_count, last_interaction)
                    VALUES
                        (:id, :restaurant_id, :platform, :customer_id, :name,
                         1, 1, :sentiment,
                         :topics, :escalated, NOW())
                """), {
                    "id": secrets.token_hex(16),
                    "restaurant_id": restaurant_id,
                    "platform": platform,
                    "customer_id": customer_id,
                    "name": customer_name,
                    "sentiment": sentiment,
                    "topics": json.dumps(topics or []),
                    "escalated": 1 if escalated else 0,
                })
            db.commit()
    except Exception as e:
        print(f"WARNING [Memory]: Could not update profile: {e}")


def get_customer_profile(
    platform: str,
    customer_id: str,
    restaurant_id: str = TENANT_ID,
) -> dict:
    """Get customer profile for context injection into prompts."""
    try:
        with SessionLocal() as db:
            row = db.execute(text("""
                SELECT customer_name, visit_count, message_count,
                       sentiment_trend, topics_of_interest, escalation_count,
                       last_interaction
                FROM customer_profiles
                WHERE restaurant_id = :restaurant_id
                  AND platform = :platform
                  AND customer_id = :customer_id
            """), {
                "restaurant_id": restaurant_id,
                "platform": platform,
                "customer_id": customer_id,
            }).fetchone()

            if not row:
                return {}

            return {
                "name": row[0],
                "visit_count": row[1],
                "message_count": row[2],
                "sentiment_trend": row[3],
                "topics_of_interest": json.loads(row[4] or "[]"),
                "escalation_count": row[5],
                "last_interaction": str(row[6]),
                "is_returning": (row[2] or 0) > 1,
            }
    except Exception as e:
        print(f"WARNING [Memory]: Could not get profile: {e}")
        return {}


def format_customer_context(profile: dict) -> str:
    """Format customer profile as a short context string for prompts."""
    if not profile:
        return "New customer — no prior interaction history."

    parts = []
    if profile.get("name"):
        parts.append(f"Customer name: {profile['name']}")
    if profile.get("is_returning"):
        parts.append(f"Returning customer ({profile['message_count']} prior messages)")
    if profile.get("sentiment_trend") and profile["sentiment_trend"] != "neutral":
        parts.append(f"Sentiment history: {profile['sentiment_trend']}")
    if profile.get("topics_of_interest"):
        topics = ", ".join(profile["topics_of_interest"][:5])
        parts.append(f"Previously asked about: {topics}")
    if profile.get("escalation_count", 0) > 0:
        parts.append(f"Has had {profile['escalation_count']} escalation(s) in the past — handle with care")

    return "\n".join(parts) if parts else "First-time customer."


# ── LangChain tools (for agent use) ──────────────────────────────────────────

@tool
def recall_customer_history(platform: str, customer_id: str) -> str:
    """
    Retrieve conversation history and profile for a customer.
    Always call this at the start of handling a DM to get context.
    Args:
        platform: 'facebook' or 'instagram'
        customer_id: The customer's platform user ID
    """
    profile = get_customer_profile(platform, customer_id)
    history = get_conversation_history(platform, customer_id)

    profile_text = format_customer_context(profile)
    history_text = "\n".join([
        f"{msg['role'].upper()}: {msg['content']}"
        for msg in history[-6:]
    ]) if history else "No prior messages."

    return f"CUSTOMER CONTEXT:\n{profile_text}\n\nRECENT CONVERSATION:\n{history_text}"


MEMORY_TOOLS = [recall_customer_history]