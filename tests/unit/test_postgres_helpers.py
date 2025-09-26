import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from quanticity_capital.core.postgres import (
    dispose_postgres_engine,
    get_postgres_engine,
    get_sessionmaker,
    session_scope,
)
from quanticity_capital.config.models import (
    AlertingConfig,
    AnalyticsConfig,
    AppConfig,
    LoggingConfig,
    ObservabilityConfig,
    ObservabilityLoggingConfig,
    PostgresConfig,
    RedisConfig,
    RuntimeConfig,
    RuntimeModules,
    RuntimeWatchdogConfig,
    ScheduleConfig,
    SymbolsConfig,
    SymbolsIngestionAlphaVantage,
    SymbolsIngestionConfig,
    SymbolsIngestionIBKR,
    SymbolsSignalsConfig,
    IngestionModuleToggles,
    WatchdogConfig,
)


def build_minimal_app_config(dsn: str) -> AppConfig:
    runtime_modules = RuntimeModules.model_construct(
        scheduler=True,
        ingestion=IngestionModuleToggles.model_construct(alpha_vantage=True, ibkr=False),
        analytics=True,
        signals=True,
        execution=False,
        watchdog=True,
        social=True,
        dashboard_api=True,
        observability=True,
    )
    runtime_config = RuntimeConfig.model_construct(
        modules=runtime_modules,
        redis=RedisConfig.model_construct(url="redis://localhost", decode_responses=True),
        postgres=PostgresConfig.model_construct(dsn=dsn, pool_size=2, timeout_seconds=5),
        watchdog=RuntimeWatchdogConfig.model_construct(mode="manual"),
        logging=LoggingConfig.model_construct(level="INFO", config_file=None),
    )
    schedule_config = ScheduleConfig.model_construct(buckets={}, jobs={})
    symbols_config = SymbolsConfig.model_construct(
        universes={},
        ingestion=SymbolsIngestionConfig.model_construct(
            alpha_vantage=SymbolsIngestionAlphaVantage.model_construct(
                realtime_options=[], tech_indicators=[], news_sentiment=[]
            ),
            ibkr=SymbolsIngestionIBKR.model_construct(level2_groups=[], quotes=[]),
        ),
        signals=SymbolsSignalsConfig.model_construct(enabled_strategies=[]),
    )
    analytics_config = AnalyticsConfig.model_construct(metrics={})
    watchdog_config = WatchdogConfig.model_construct(
        mode="manual",
        confidence_thresholds={},
        rate_limits={},
        model="gpt-4o-mini",
        prompt_templates={},
        notifications=None,
    )
    observability_config = ObservabilityConfig.model_construct(
        heartbeats={},
        data_freshness={},
        alerting=AlertingConfig.model_construct(telegram=None, email=None),
        logging=ObservabilityLoggingConfig.model_construct(
            log_dir="/tmp", max_bytes=1024, backups=1
        ),
    )
    return AppConfig.model_construct(
        runtime=runtime_config,
        schedule=schedule_config,
        symbols=symbols_config,
        analytics=analytics_config,
        watchdog=watchdog_config,
        observability=observability_config,
    )


@pytest.mark.asyncio
async def test_get_postgres_engine_returns_cached_instance() -> None:
    settings = build_minimal_app_config("postgresql+asyncpg://user:pass@localhost:5432/testdb")
    engine = await get_postgres_engine(settings)
    assert isinstance(engine, AsyncEngine)

    same_engine = await get_postgres_engine(settings)
    assert same_engine is engine

    await dispose_postgres_engine()


@pytest.mark.asyncio
async def test_session_scope_yields_async_session() -> None:
    settings = build_minimal_app_config("postgresql+asyncpg://user:pass@localhost:5432/testdb")

    async with session_scope(settings) as session:
        assert isinstance(session, AsyncSession)

    await dispose_postgres_engine()


@pytest.mark.asyncio
async def test_sessionmaker_cached_across_calls() -> None:
    settings = build_minimal_app_config("postgresql+asyncpg://user:pass@localhost:5432/testdb")

    sessionmaker_a = await get_sessionmaker(settings)
    sessionmaker_b = await get_sessionmaker(settings)

    assert sessionmaker_a is sessionmaker_b

    await dispose_postgres_engine()
