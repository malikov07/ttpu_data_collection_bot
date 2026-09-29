"""Login/password accounts, passport data, Google Drive/Sheets removed

- staff are now login accounts (``accounts``) with role rows (``staff``).
  Old e-mail based staff rows cannot be converted (no passwords) and are
  dropped; admins re-create staff accounts.
- students get separate name fields and identity-document fields; existing
  rows are backfilled from ``full_name``.
- every Google Drive/Sheets column and the Telegram invites table go away.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- staff: e-mail based rows -> accounts + roles ---------------------------
    op.drop_table("invites")
    op.drop_table("web_sessions")
    op.drop_table("staff")

    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=32), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=True),
        sa.Column("telegram_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_accounts_username", "accounts", ["username"], unique=True)
    op.create_index("ix_accounts_telegram_id", "accounts", ["telegram_id"], unique=True)

    op.create_table(
        "staff",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Enum("admin", "tutor", "leader", name="staffrole", native_enum=False, length=16), nullable=False),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("account_id", "role", "group_id", name="uq_staff_account_role_group"),
    )
    op.create_index("ix_staff_account_id", "staff", ["account_id"])

    op.create_table(
        "web_sessions",
        sa.Column("token_hash", sa.String(length=64), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_agent", sa.String(length=256), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_web_sessions_account_id", "web_sessions", ["account_id"])

    # --- students: name parts + identity document -------------------------------
    with op.batch_alter_table("students") as batch:
        batch.add_column(sa.Column("last_name", sa.String(length=64), nullable=False, server_default=""))
        batch.add_column(sa.Column("first_name", sa.String(length=64), nullable=False, server_default=""))
        batch.add_column(sa.Column("middle_name", sa.String(length=64), nullable=True))
        batch.add_column(
            sa.Column("doc_type", sa.Enum("passport", "id_card", name="doctype", native_enum=False, length=16), nullable=True)
        )
        batch.add_column(sa.Column("doc_number", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("doc_expiry", sa.Date(), nullable=True))
        batch.add_column(sa.Column("pinfl", sa.String(length=14), nullable=True))
        batch.add_column(sa.Column("nationality", sa.String(length=3), nullable=True))
        batch.alter_column("full_name", existing_type=sa.String(length=128), type_=sa.String(length=200), existing_nullable=False)
        batch.drop_column("drive_folder_id")
        batch.drop_column("folder_synced")
    op.create_index("ix_students_full_name", "students", ["full_name"])
    op.create_index("ix_students_doc_number", "students", ["doc_number"])
    op.create_index("ix_students_pinfl", "students", ["pinfl"])

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, full_name FROM students")).all()
    for student_id, full_name in rows:
        parts = (full_name or "").split()
        conn.execute(
            sa.text("UPDATE students SET last_name = :l, first_name = :f, middle_name = :m WHERE id = :id"),
            {"l": parts[0] if parts else "", "f": parts[1] if len(parts) > 1 else "", "m": " ".join(parts[2:]) or None, "id": student_id},
        )

    # --- Google Drive/Sheets bookkeeping ----------------------------------------
    with op.batch_alter_table("documents") as batch:
        batch.drop_index("ix_documents_next_attempt_at")
        for col in ("drive_file_id", "drive_url", "stale_drive_file_id", "upload_error", "upload_attempts", "next_attempt_at"):
            batch.drop_column(col)
    with op.batch_alter_table("groups") as batch:
        for col in ("drive_folder_id", "docs_folder_id", "spreadsheet_id", "sheet_dirty", "name_synced"):
            batch.drop_column(col)
    op.execute("DELETE FROM kv WHERE key LIKE 'drive.%' OR key LIKE 'sheets.%'")


def downgrade() -> None:
    raise NotImplementedError("0002 is not reversible: staff accounts and Google data cannot be restored")
