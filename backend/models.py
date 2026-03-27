from datetime import datetime
from sqlalchemy import DateTime, String, Boolean, func, Text
from sqlalchemy.orm import Mapped, mapped_column

try:
  from .db import Base
except ImportError:
  from db import Base


class User(Base):
  __tablename__ = "users"

  id: Mapped[str] = mapped_column(String(32), primary_key=True)
  name: Mapped[str] = mapped_column(String(80))
  email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
  company: Mapped[str | None] = mapped_column(String(120), nullable=True)
  salt: Mapped[str] = mapped_column(String(64))
  password_hash: Mapped[str] = mapped_column(String(64))
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SocialAccount(Base):
  __tablename__ = "social_accounts"

  id: Mapped[str] = mapped_column(String(32), primary_key=True)
  user_email: Mapped[str] = mapped_column(String(255), index=True)
  platform: Mapped[str] = mapped_column(String(32))
  external_id: Mapped[str] = mapped_column(String(128))
  page_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
  instagram_username: Mapped[str | None] = mapped_column(String(120), nullable=True)
  profile_picture_url: Mapped[str | None] = mapped_column(Text, nullable=True)
  access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
  token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  linked_page_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
  is_connected: Mapped[bool] = mapped_column(Boolean, default=True)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Post(Base):
  __tablename__ = "posts"

  id: Mapped[str] = mapped_column(String(32), primary_key=True)
  user_email: Mapped[str] = mapped_column(String(255), index=True)
  caption: Mapped[str] = mapped_column(String(2000))
  media_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
  media_type: Mapped[str] = mapped_column(String(16), default="image")
  hashtags: Mapped[str | None] = mapped_column(String(500), nullable=True)
  emojis: Mapped[str | None] = mapped_column(String(200), nullable=True)
  targets: Mapped[str | None] = mapped_column(String(200), nullable=True)
  fb_post_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
  ig_media_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
  status: Mapped[str] = mapped_column(String(24), default="draft")
  error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
  scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Interaction(Base):
  __tablename__ = "interactions"

  id: Mapped[str] = mapped_column(String(32), primary_key=True)
  user_email: Mapped[str] = mapped_column(String(255), index=True)
  platform: Mapped[str] = mapped_column(String(32))
  external_id: Mapped[str] = mapped_column(String(255), index=True)
  content: Mapped[str] = mapped_column(Text)
  sender_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
  type: Mapped[str] = mapped_column(String(32))  # 'comment' or 'message'
  is_outgoing: Mapped[bool] = mapped_column(Boolean, default=False)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
