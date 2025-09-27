from __future__ import annotations

import pytest

from src.analytics.config import AnalyticsJobConfig, load_analytics_config


def test_load_analytics_config_defaults(tmp_path, monkeypatch):
    config_path = tmp_path / "analytics.yml"
    config_path.write_text(
        """
        defaults:
          cadence_seconds: 15
        jobs:
          - name: job_a
            type: analytics.test
            symbols: [SPY]
            metrics: [dealer_greeks]
        """
    )

    jobs = load_analytics_config(config_path)

    assert len(tuple(jobs)) == 1
    job = tuple(jobs)[0]
    assert job.cadence_seconds == 15
    assert job.enabled is True
    assert job.symbols == ("SPY",)
    assert job.metrics == ("dealer_greeks",)


def test_load_analytics_config_validation(tmp_path):
    config_path = tmp_path / "analytics.yml"
    config_path.write_text(
        """
        jobs:
          - name: bad_job
            type: analytics.test
            cadence_seconds: 0
            symbols: [SPY]
            metrics: [dealer_greeks]
        """
    )

    with pytest.raises(ValueError, match="cadence"):
        load_analytics_config(config_path)


def test_enabled_filter(tmp_path):
    config_path = tmp_path / "analytics.yml"
    config_path.write_text(
        """
        jobs:
          - name: enabled_job
            type: analytics.test
            symbols: [SPY]
            metrics: [dealer_greeks]
          - name: disabled_job
            type: analytics.test
            enabled: false
            symbols: [QQQ]
            metrics: [vol]
        """
    )

    jobs = load_analytics_config(config_path)
    enabled_jobs = jobs.enabled()

    assert len(enabled_jobs) == 1
    assert enabled_jobs[0].name == "enabled_job"
