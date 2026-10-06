"""Add optional queue assignment to staff

Revision ID: c834ee646974
Revises: eda56c463588
Create Date: 2026-10-06 20:05:36.096147
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c834ee646974"
down_revision: Union[str, Sequence[str], None] = "eda56c463588"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add optional queue assignment."""
    op.add_column(
        "staff",
        sa.Column("queue_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        None,
        "staff",
        "queues",
        ["queue_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Remove optional queue assignment."""
    inspector = sa.inspect(op.get_bind())

    for foreign_key in inspector.get_foreign_keys("staff"):
        if (
            foreign_key["constrained_columns"] == ["queue_id"]
            and foreign_key["referred_table"] == "queues"
        ):
            constraint_name = foreign_key["name"]

            if not constraint_name:
                raise RuntimeError(
                    "Cannot remove the queue assignment: "
                    "its foreign key has no discoverable name."
                )

            op.drop_constraint(
                constraint_name,
                "staff",
                type_="foreignkey",
            )
            break

    op.drop_column("staff", "queue_id")