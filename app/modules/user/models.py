import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.config.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="USER")

    # Profile (flat columns instead of nested doc)
    profile_name: Mapped[str] = mapped_column(String(100), default="")
    profile_avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_website: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Stats
    followers_count: Mapped[int] = mapped_column(Integer, default=0)
    following_count: Mapped[int] = mapped_column(Integer, default=0)
    reels_count: Mapped[int] = mapped_column(Integer, default=0)

    # Wallet
    wallet_balance: Mapped[float] = mapped_column(Float, default=0.0)
    wallet_total_earnings: Mapped[float] = mapped_column(Float, default=0.0)

    # Bank account (JSONB for flexibility)
    bank_account: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Store info
    store_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    store_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    store_logo: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
