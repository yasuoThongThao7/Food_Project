"""Add image and result columns to search_histories."""

import sqlalchemy as sa
from alembic import op

revision = "0002_history_prediction"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _existing() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("search_histories")}


def upgrade() -> None:
    existing = _existing()
    with op.batch_alter_table("search_histories") as batch:
        if "image_path" not in existing:
            batch.add_column(sa.Column("image_path", sa.String(300), nullable=True))
        if "result_json" not in existing:
            batch.add_column(sa.Column("result_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    existing = _existing()
    with op.batch_alter_table("search_histories") as batch:
        if "result_json" in existing:
            batch.drop_column("result_json")
        if "image_path" in existing:
            batch.drop_column("image_path")