"""Certificates and awards sent by students (IELTS, SAT, CEFR, olympiads…)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

CERT_TYPES = ("ielts", "toefl", "sat", "duolingo", "cefr", "national", "olympiad", "other")
CERT_STATUSES = ("pending", "approved", "rejected")


def upgrade() -> None:
    op.create_table(
        "certificates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.Enum(*CERT_TYPES, name="certtype", native_enum=False, length=16), nullable=False),
        sa.Column("result", sa.String(length=100), nullable=False),
        sa.Column("files", sa.JSON(), nullable=False),
        sa.Column("status", sa.Enum(*CERT_STATUSES, name="certstatus", native_enum=False, length=16), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.String(length=64), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_certificates_student_id", "certificates", ["student_id"])
    op.create_index("ix_certificates_status", "certificates", ["status"])


def downgrade() -> None:
    op.drop_index("ix_certificates_status", "certificates")
    op.drop_index("ix_certificates_student_id", "certificates")
    op.drop_table("certificates")
