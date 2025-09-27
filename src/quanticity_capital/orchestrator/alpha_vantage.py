"""Alpha Vantage ingestion orchestration helpers."""

from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Sequence

import structlog
from redis import Redis

from quanticity_capital.config import load_settings
from quanticity_capital.ingestion import (
    ALPHA_VANTAGE_ENDPOINT_SPECS,
    AlphaVantageClientProtocol,
    AlphaVantageConnector,
    AlphaVantageHttpClient,
    AlphaVantageThrottleError,
)
from quanticity_capital.runner import IngestionJob, Runner, RunnerResult


@dataclass(frozen=True)
class EndpointConfig:
    """Runtime orchestration configuration for a single endpoint."""

    contexts: Sequence[Mapping[str, Any]] = ()
    replace_defaults: bool = False


class AlphaVantageOrchestrator:
    """Coordinates Alpha Vantage ingestion jobs using the shared runner."""

    def __init__(
        self,
        *,
        runner: Runner | None = None,
        settings: Mapping[str, Any] | None = None,
        env: Mapping[str, str] | None = None,
        client: AlphaVantageClientProtocol | None = None,
        enabled_endpoints: Sequence[str] | None = None,
        redis_client: Redis | None = None,
        persist_results: bool = True,
        logger: structlog.BoundLogger | None = None,
    ) -> None:
        self._env: Mapping[str, str] = env or os.environ
        self._settings: Dict[str, Any] = dict(settings or load_settings())

        self._logger = (logger or structlog.get_logger("quanticity_capital.orchestrator.alpha_vantage")).bind(
            integration="alpha_vantage"
        )
        self._metrics: Counter[str] = Counter()
        self._dispatch_iterations = 0

        self._runner = runner or Runner()
        self._owns_client = client is None
        self._client = client or self._build_http_client()
        self._connector = AlphaVantageConnector(self._runner, self._client)

        self._persist_results = persist_results
        self._owns_redis = False
        self._redis: Redis | None = None
        self._redis_url_env: str = ""
        self._redis_ttl_default: int = 0
        self._redis_ttl_min: int = 0
        self._redis_ttl_max: int = 0
        self._init_redis_config()
        if self._persist_results:
            self._redis = redis_client or self._build_redis_client()
            self._owns_redis = redis_client is None

        ingestion_cfg = (
            self._settings.get("ingestion", {}).get("alpha_vantage", {})
        )
        configured_endpoints: Sequence[str] | None = ingestion_cfg.get(
            "enabled_endpoints"
        )
        self._endpoints = tuple(
            enabled_endpoints
            or configured_endpoints
            or self._connector.available_endpoints()
        )

        self._endpoint_configs: Dict[str, EndpointConfig] = self._load_endpoint_configs(ingestion_cfg)

    def _build_http_client(self) -> AlphaVantageHttpClient:
        services_cfg = self._settings.get("services", {}).get("alphavantage", {})
        api_key_env = services_cfg.get("api_key_env", "ALPHAVANTAGE_API_KEY")
        try:
            api_key = self._env[api_key_env]
        except KeyError as exc:  # pragma: no cover - defensive and environment dependent
            raise RuntimeError(
                f"Alpha Vantage API key not found in environment variable '{api_key_env}'"
            ) from exc

        base_url = services_cfg.get("base_url", "https://www.alphavantage.co")
        base_url = base_url.rstrip("/")
        if not base_url.endswith("/query"):
            base_url = f"{base_url}/query"

        timeout = services_cfg.get("timeout_seconds", 10.0)

        return AlphaVantageHttpClient(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )

    def _init_redis_config(self) -> None:
        services_cfg = self._settings.get("services", {}).get("redis", {})
        self._redis_url_env = services_cfg.get("url_env", "REDIS_URL")
        self._redis_ttl_default = int(services_cfg.get("default_ttl_seconds", 3600))
        self._redis_ttl_min = int(services_cfg.get("min_ttl_seconds", 60))
        self._redis_ttl_max = int(services_cfg.get("max_ttl_seconds", 86400))

        if self._redis_ttl_min <= 0:
            raise ValueError("services.redis.min_ttl_seconds must be positive")
        if self._redis_ttl_max < self._redis_ttl_min:
            raise ValueError("services.redis.max_ttl_seconds must be >= min_ttl_seconds")
        if self._redis_ttl_default < self._redis_ttl_min or self._redis_ttl_default > self._redis_ttl_max:
            self._logger.warning(
                "redis.ttl_default_out_of_bounds",
                default_ttl=self._redis_ttl_default,
                min_ttl=self._redis_ttl_min,
                max_ttl=self._redis_ttl_max,
            )
            self._redis_ttl_default = max(
                self._redis_ttl_min,
                min(self._redis_ttl_default, self._redis_ttl_max),
            )

    def _build_redis_client(self) -> Redis:
        redis_url = self._env.get(self._redis_url_env)
        if not redis_url:
            raise RuntimeError(
                f"Redis URL not found in environment variable '{self._redis_url_env}'"
            )

        client = Redis.from_url(redis_url, decode_responses=True)
        self._logger.info("redis.client_ready", url_env=self._redis_url_env)
        return client

    def _load_endpoint_configs(
        self, ingestion_cfg: Mapping[str, Any]
    ) -> Dict[str, EndpointConfig]:
        configs: Dict[str, EndpointConfig] = {}
        raw_configs = ingestion_cfg.get("endpoints", {})

        for endpoint, cfg in raw_configs.items():
            contexts = cfg.get("contexts", [])
            replace_defaults = bool(cfg.get("replace_defaults", False))
            configs[endpoint] = EndpointConfig(
                contexts=tuple(dict(context) for context in contexts),
                replace_defaults=replace_defaults,
            )
        return configs

    def close(self) -> None:
        if self._owns_client and isinstance(self._client, AlphaVantageHttpClient):
            self._client.close()
        if self._owns_redis and self._redis is not None:
            try:
                self._redis.close()
            except Exception:  # pragma: no cover - guard against client incompatibilities
                self._logger.warning("redis.close_failed", exc_info=True)

    def __enter__(self) -> "AlphaVantageOrchestrator":  # pragma: no cover - convenience
        return self

    def __exit__(self, *_: Any) -> None:  # pragma: no cover - convenience
        self.close()

    def build_job_plan(self) -> Dict[str, Sequence[IngestionJob]]:
        plan: Dict[str, Sequence[IngestionJob]] = {}
        for endpoint in self._endpoints:
            contexts = self._collect_contexts(endpoint)
            if not contexts:
                continue
            jobs = self._connector.build_jobs(endpoint, contexts)
            plan[endpoint] = jobs
        return plan

    def dispatch(
        self,
        plan: Mapping[str, Sequence[IngestionJob]] | None = None,
    ) -> Sequence[RunnerResult]:
        plan_to_use = plan or self.build_job_plan()
        results: list[RunnerResult] = []
        dispatch_metrics: Counter[str] = Counter()
        persistence_success = 0
        persistence_failure = 0

        for endpoint, jobs in plan_to_use.items():
            for job in jobs:
                result = self._runner.run(job)
                results.append(result)

                dispatch_metrics["total"] += 1
                if result.status == "ok":
                    dispatch_metrics["ok"] += 1
                    if self._persist_results:
                        try:
                            self._persist_result(result)
                            persistence_success += 1
                        except Exception as exc:  # noqa: BLE001
                            persistence_failure += 1
                            self._logger.error(
                                "result.persist_failed",
                                job_name=result.job_name,
                                error_type=type(exc).__name__,
                                message=str(exc),
                                exc_info=True,
                            )
                else:
                    dispatch_metrics["error"] += 1
                    if isinstance(result.error, AlphaVantageThrottleError):
                        dispatch_metrics["throttle"] += 1
                    else:
                        dispatch_metrics["failure"] += 1

        self._dispatch_iterations += 1
        self._metrics.update(dispatch_metrics)

        self._logger.info(
            "dispatch.completed",
            iteration=self._dispatch_iterations,
            total=dispatch_metrics.get("total", 0),
            ok=dispatch_metrics.get("ok", 0),
            errors=dispatch_metrics.get("error", 0),
            throttled=dispatch_metrics.get("throttle", 0),
            persistence_ok=persistence_success,
            persistence_failed=persistence_failure,
        )

        return results

    def metrics_snapshot(self) -> Dict[str, int]:
        """Return a copy of the aggregated dispatch counters."""

        return dict(self._metrics)

    def redis_client(self) -> Redis | None:
        """Expose the Redis client used for persistence when available."""

        return self._redis

    def _collect_contexts(self, endpoint: str) -> Sequence[Mapping[str, Any]]:
        if endpoint not in ALPHA_VANTAGE_ENDPOINT_SPECS:
            raise KeyError(f"Unknown Alpha Vantage endpoint '{endpoint}'")

        spec = self._connector.spec_for(endpoint)
        contexts: list[Mapping[str, Any]] = []

        if endpoint in self._endpoint_configs:
            cfg = self._endpoint_configs[endpoint]
        else:
            cfg = EndpointConfig()

        if not cfg.replace_defaults:
            contexts.extend(self._connector.default_contexts(endpoint))

        contexts.extend(cfg.contexts)

        deduped = self._deduplicate_contexts(contexts)
        self._validate_contexts(spec.context_keys, deduped, endpoint)
        if spec.context_keys and not deduped:
            raise ValueError(
                f"No contexts provided for endpoint '{endpoint}' requiring keys {spec.context_keys!r}"
            )
        return tuple(deduped)

    @staticmethod
    def _deduplicate_contexts(contexts: Iterable[Mapping[str, Any]]) -> list[Dict[str, Any]]:
        deduped: list[Dict[str, Any]] = []
        seen: set[tuple[tuple[str, Any], ...]] = set()
        for context in contexts:
            normalized = tuple(sorted(dict(context).items()))
            if normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(dict(context))
        return deduped

    @staticmethod
    def _validate_contexts(
        required_keys: Sequence[str],
        contexts: Sequence[Mapping[str, Any]],
        endpoint: str,
    ) -> None:
        for index, context in enumerate(contexts):
            missing = [key for key in required_keys if key not in context]
            if missing:
                raise ValueError(
                    f"Context {index} for endpoint '{endpoint}' is missing keys: {missing}"
                )

    def _persist_result(self, result: RunnerResult) -> None:
        if not self._redis:
            return

        payload = result.payload
        if not isinstance(payload, MutableMapping):
            raise TypeError(
                f"Runner result payload for job '{result.job_name}' must be a mapping to persist"
            )

        redis_key = (
            payload.get("redis_key")
            or result.metadata.get("redis_key")
        )
        if not isinstance(redis_key, str) or not redis_key:
            raise ValueError(
                f"Runner result for job '{result.job_name}' missing redis key"
            )
        if not redis_key.startswith("raw:alpha_vantage:"):
            raise ValueError(
                f"Unexpected redis key '{redis_key}' for job '{result.job_name}'"
            )

        ttl = self._resolve_ttl(result, payload)
        payload["ttl_applied"] = ttl

        serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        self._redis.set(redis_key, serialized, ex=ttl)
        self._logger.debug("result.persisted", redis_key=redis_key, ttl=ttl)

    def _resolve_ttl(
        self,
        result: RunnerResult,
        payload: Mapping[str, Any],
    ) -> int:
        ttl_candidate = (
            payload.get("ttl_applied")
            or result.metadata.get("ttl_seconds")
            or self._redis_ttl_default
        )
        try:
            ttl = int(ttl_candidate)
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
            raise ValueError(
                f"Invalid TTL '{ttl_candidate}' for job '{result.job_name}'"
            ) from exc

        if ttl < self._redis_ttl_min:
            self._metrics["ttl_clamped_low"] += 1
            self._logger.warning(
                "redis.ttl_clamped_low",
                job_name=result.job_name,
                ttl=ttl,
                min_ttl=self._redis_ttl_min,
            )
            ttl = self._redis_ttl_min
        elif ttl > self._redis_ttl_max:
            self._metrics["ttl_clamped_high"] += 1
            self._logger.warning(
                "redis.ttl_clamped_high",
                job_name=result.job_name,
                ttl=ttl,
                max_ttl=self._redis_ttl_max,
            )
            ttl = self._redis_ttl_max

        return ttl


__all__ = ["AlphaVantageOrchestrator"]
