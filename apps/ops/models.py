"""What the tool did, one row per action; the remote cleanup task removes old rows."""

from __future__ import annotations

import datetime as dt

from oldman.db.models import DatabaseModel
from oldman.utils.date import naive_utcnow
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class OperationLog(DatabaseModel):
    """One action the tool carried out."""

    __tablename__ = "ops_operation_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=naive_utcnow, nullable=False, index=True)
