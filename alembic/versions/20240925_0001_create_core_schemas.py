"""Create baseline schemas and tables for the trade store."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20240925_0001"
down_revision = None
branch_labels = None
depends_on = None

SCHEMAS = ("reference", "trading", "analytics", "audit")


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
    for schema in SCHEMAS:
        op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))

    op.create_table(
        "symbols",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("symbol", sa.String(length=32), nullable=False, unique=True),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("description", sa.String(length=128), nullable=True),
        sa.Column("exchange", sa.String(length=32), nullable=True),
        sa.Column("base_currency", sa.String(length=8), nullable=True),
        sa.Column(
            "groups", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        schema="reference",
    )

    op.create_table(
        "strategy_config",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("strategy_name", sa.String(length=64), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "parameters", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        schema="reference",
    )

    op.create_table(
        "trades",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("signal_id", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("strategy", sa.String(length=64), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("entry_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("exit_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        schema="trading",
    )
    op.create_index("ix_trading_trades_signal_id", "trades", ["signal_id"], schema="trading")
    op.create_index("ix_trading_trades_symbol", "trades", ["symbol"], schema="trading")

    op.create_table(
        "fills",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "trade_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trading.trades.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_fill_id", sa.String(length=64), nullable=True),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price", sa.Numeric(18, 6), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("liquidity", sa.String(length=16), nullable=True),
        sa.Column("venue", sa.String(length=32), nullable=True),
        sa.Column(
            "metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        schema="trading",
    )
    op.create_index("ix_trading_fills_trade_id", "fills", ["trade_id"], schema="trading")

    op.create_table(
        "stop_adjustments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "trade_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trading.trades.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("previous_stop", sa.Numeric(18, 6), nullable=False),
        sa.Column("new_stop", sa.Numeric(18, 6), nullable=False),
        sa.Column("adjusted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column(
            "metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        schema="trading",
    )
    op.create_index(
        "ix_trading_stop_adjustments_trade_id", "stop_adjustments", ["trade_id"], schema="trading"
    )

    op.create_table(
        "metric_snapshots",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "metrics", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("symbol", "as_of", name="uq_metric_snapshot_symbol_asof"),
        schema="analytics",
    )
    op.create_index(
        "ix_analytics_metric_snapshots_symbol", "metric_snapshots", ["symbol"], schema="analytics"
    )

    op.create_table(
        "correlation_matrices",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("group_name", sa.String(length=64), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "matrix", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("group_name", "as_of", name="uq_correlation_group_asof"),
        schema="analytics",
    )

    op.create_table(
        "macro_series",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("series_name", sa.String(length=64), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value", sa.Numeric(18, 6), nullable=True),
        sa.Column(
            "payload", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("series_name", "as_of", name="uq_macro_series_asof"),
        schema="analytics",
    )

    op.create_table(
        "social_posts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("tier", sa.String(length=16), nullable=False),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        schema="audit",
    )

    op.create_table(
        "watchdog_reviews",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("signal_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("review", sa.Text, nullable=False),
        sa.Column(
            "metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        schema="audit",
    )
    op.create_index(
        "ix_audit_watchdog_reviews_signal_id", "watchdog_reviews", ["signal_id"], schema="audit"
    )

    op.create_table(
        "integration_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("suite", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "details", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        schema="audit",
    )


def downgrade() -> None:
    op.drop_table("integration_runs", schema="audit")
    op.drop_index(
        "ix_audit_watchdog_reviews_signal_id", table_name="watchdog_reviews", schema="audit"
    )
    op.drop_table("watchdog_reviews", schema="audit")
    op.drop_table("social_posts", schema="audit")

    op.drop_table("macro_series", schema="analytics")
    op.drop_table("correlation_matrices", schema="analytics")
    op.drop_index(
        "ix_analytics_metric_snapshots_symbol", table_name="metric_snapshots", schema="analytics"
    )
    op.drop_table("metric_snapshots", schema="analytics")

    op.drop_index(
        "ix_trading_stop_adjustments_trade_id", table_name="stop_adjustments", schema="trading"
    )
    op.drop_table("stop_adjustments", schema="trading")
    op.drop_index("ix_trading_fills_trade_id", table_name="fills", schema="trading")
    op.drop_table("fills", schema="trading")
    op.drop_index("ix_trading_trades_symbol", table_name="trades", schema="trading")
    op.drop_index("ix_trading_trades_signal_id", table_name="trades", schema="trading")
    op.drop_table("trades", schema="trading")

    op.drop_table("strategy_config", schema="reference")
    op.drop_table("symbols", schema="reference")

    for schema in reversed(SCHEMAS):
        op.execute(sa.text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
