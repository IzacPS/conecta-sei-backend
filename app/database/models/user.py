"""User model - synced with Firebase Authentication."""

from typing import Optional

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.model_base import SqlAlchemyModel


class User(SqlAlchemyModel):
    __tablename__ = "users"

    firebase_uid: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        index=True,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    display_name: Mapped[Optional[str]] = mapped_column(String(255))

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="user",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    avatar_url: Mapped[Optional[str]] = mapped_column(Text)

    def __repr__(self) -> str:
        return f"<User uid={self.firebase_uid} email={self.email}>"
