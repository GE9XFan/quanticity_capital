"""SQLAlchemy table metadata for the Postgres trade store."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

SCHEMAS = ("reference", "trading", "analytics", "audit")

metadata = sa.MetaData()

reference_symbols = sa.Table(
    "symbols",
    metadata,
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
    sa.Column("groups", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
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

reference_strategy_config = sa.Table(
    "strategy_config",
    metadata,
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

trading_trades = sa.Table(
    "trades",
    metadata,
    sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    ),
    sa.Column("signal_id", sa.String(length=64), nullable=False, index=True),
    sa.Column("symbol", sa.String(length=32), nullable=False, index=True),
    sa.Column("strategy", sa.String(length=64), nullable=False),
    sa.Column("side", sa.String(length=8), nullable=False),
    sa.Column("status", sa.String(length=32), nullable=False),
    sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
    sa.Column("entry_price", sa.Numeric(18, 6), nullable=True),
    sa.Column("exit_price", sa.Numeric(18, 6), nullable=True),
    sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
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

trading_fills = sa.Table(
    "fills",
    metadata,
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
        index=True,
    ),
    sa.Column("external_fill_id", sa.String(length=64), nullable=True),
    sa.Column("filled_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("price", sa.Numeric(18, 6), nullable=False),
    sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
    sa.Column("liquidity", sa.String(length=16), nullable=True),
    sa.Column("venue", sa.String(length=32), nullable=True),
    sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    schema="trading",
)

trading_stop_adjustments = sa.Table(
    "stop_adjustments",
    metadata,
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
        index=True,
    ),
    sa.Column("previous_stop", sa.Numeric(18, 6), nullable=False),
    sa.Column("new_stop", sa.Numeric(18, 6), nullable=False),
    sa.Column("adjusted_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("reason", sa.String(length=255), nullable=True),
    sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    schema="trading",
)

analytics_metric_snapshots = sa.Table(
    "metric_snapshots",
    metadata,
    sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    ),
    sa.Column("symbol", sa.String(length=32), nullable=False, index=True),
    sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
    sa.Column("metrics", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
    sa.UniqueConstraint("symbol", "as_of", name="uq_metric_snapshot_symbol_asof"),
    schema="analytics",
)

analytics_correlation_matrices = sa.Table(
    "correlation_matrices",
    metadata,
    sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    ),
    sa.Column("group_name", sa.String(length=64), nullable=False),
    sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
    sa.Column("matrix", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
    sa.UniqueConstraint("group_name", "as_of", name="uq_correlation_group_asof"),
    schema="analytics",
)

analytics_macro_series = sa.Table(
    "macro_series",
    metadata,
    sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    ),
    sa.Column("series_name", sa.String(length=64), nullable=False),
    sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
    sa.Column("value", sa.Numeric(18, 6), nullable=True),
    sa.Column("payload", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
    sa.UniqueConstraint("series_name", "as_of", name="uq_macro_series_asof"),
    schema="analytics",
)

audit_social_posts = sa.Table(
    "social_posts",
    metadata,
    sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    ),
    sa.Column("platform", sa.String(length=32), nullable=False),
    sa.Column("tier", sa.String(length=16), nullable=False),
    sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")),
    sa.Column("content", sa.Text, nullable=False),
    sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
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

audit_watchdog_reviews = sa.Table(
    "watchdog_reviews",
    metadata,
    sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    ),
    sa.Column("signal_id", sa.String(length=64), nullable=False, index=True),
    sa.Column("status", sa.String(length=32), nullable=False),
    sa.Column("model", sa.String(length=64), nullable=False),
    sa.Column("review", sa.Text, nullable=False),
    sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
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

audit_integration_runs = sa.Table(
    "integration_runs",
    metadata,
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
    sa.Column("details", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    schema="audit",
)

__all__ = [
    "SCHEMAS",
    "analytics_correlation_matrices",
    "analytics_macro_series",
    "analytics_metric_snapshots",
    "audit_integration_runs",
    "audit_social_posts",
    "audit_watchdog_reviews",
    "metadata",
    "reference_strategy_config",
    "reference_symbols",
    "trading_fills",
    "trading_stop_adjustments",
    "trading_trades",
]
