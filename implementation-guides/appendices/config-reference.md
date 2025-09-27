# Config Reference

Central index for runtime configuration files referenced across implementation guides.

| Config File                 | Owner                  | Purpose                                        | Key Sections |
|----------------------------|-----------------------|------------------------------------------------|--------------|
| `config/credentials.yaml`  | Security Engineering   | API keys, Redis auth, broker credentials       | `alpha_vantage`, `ibkr`, `redis` |
| `config/trading_params.yaml` | Quant Engineering    | Strategy, rate limits, indicator settings      | `alpha_vantage`, `greeks`, `liquidity` |
| `config/storage.yaml`      | Data Platform          | Redis retention, compaction, backup endpoints  | `redis_timeseries`, `backups` |
| `config/ai_config.yaml`    | AI Governance          | AI models, prompts, oversight thresholds       | `claude`, `openai`, `mlfinlab`, `anomaly` |
| `config/reporting.yaml`    | Reporting Lead         | Report templates, schedules, narrative tone    | `pdf`, `visual`, `narratives` |
| `config/social.yaml`       | Communications Lead    | Channel tokens, routing, throttles             | `discord`, `telegram`, `broadcast` |
| `config/backtest.yaml`     | Quant Research         | Backtesting parameters and analytics settings | `zipline`, `alphalens`, `pyfolio` |
| `config/risk_limits.yaml`  | Risk Officer           | Position sizes, VaR thresholds, stop policies  | `positions`, `portfolio`, `alerts` |
| `config/risk_model.yaml`   | Quant Risk             | PCA, MOC predictor, stress model config        | `pca`, `moc`, `var` |

## Change Control
- All configuration updates must include a link to the relevant Build Card or layer guide section.
- Validate new configurations with `scripts/validate_contract.py` where contracts exist.
- Record material changes in the associated layer guide revision history.

## Secret Management
- Secrets referenced here must reside in the approved vault (HashiCorp Vault or equivalent).
- Never commit raw credentials; use placeholders and document retrieval procedure in the appropriate runbook.
