# Social & Watchdog Template Library

## Directory Structure
```
templates/
├── watchdog/
│   ├── prompt_core.j2
│   ├── summary_markdown.j2
│   ├── slack_incident.j2
│   └── expired_notice.j2
├── social/
│   ├── discord/
│   │   ├── premium_trade.j2
│   │   ├── basic_trade.j2
│   │   ├── free_digest.j2
│   │   ├── premium_market.j2
│   │   ├── basic_market.j2
│   │   └── free_market.j2
│   ├── telegram/
│   │   └── daily_digest.j2
│   ├── twitter/
│   │   └── trade_teaser.j2
│   ├── reddit/
│   │   └── daily_thread.j2
│   └── promotions/
│       └── upgrade_cta.j2
├── reporting/
│   └── daily_summary.j2
└── localization/
    ├── en_US.yml
    ├── es_ES.yml
    └── zh_CN.yml
```

## Status Vocabulary
- Standard enum across watchdog, social, reporting, and dashboard payloads: `ok`, `warning`, `error`, `stale`.
- Treat `stale` as the only non-OK state for aged data; include `is_stale=true` (and optional `stale_reason`) in payloads instead of inventing new statuses.
- Map vendor-specific states to this enum inside loaders before rendering templates to keep content predictable.

## Watchdog Templates

### `templates/watchdog/prompt_core.j2`
```jinja
You are the compliance reviewer for institutional-grade options trading signals.

SIGNAL DETAILS:
Symbol: {{ signal.symbol }}
Strategy: {{ signal.strategy }}
Direction: {{ signal.direction }}
Instrument: {{ signal.instrument_type }}
Contracts: {{ signal.contracts }}
Expected Entry: ${{ signal.expected_entry | round(2) }}

ANALYTICS CONTEXT:
Dealer Gamma: {{ analytics.dealer_exposure.gamma | round(4) }}
Dealer Delta: {{ analytics.dealer_exposure.delta | round(0) }}
Volatility Regime: {{ analytics.volatility_regime.regime }}
Liquidity Index: {{ analytics.liquidity.index }}/100
VPIN Score: {{ analytics.vpin.toxicity_score | round(2) }}
Risk Score: {{ analytics.risk_summary.score }}/100

ACCOUNT STATUS:
Net Liquidation: ${{ account.net_liquidation | format_currency }}
Daily P&L: ${{ account.daily_pnl | format_currency }} ({{ account.daily_pnl_pct | round(1) }}%)
Available Funds: ${{ account.available_funds | format_currency }}
Current Exposure: {{ account.delta_exposure | round(0) }} deltas

RISK CHECKS:
Position Sizing: {{ signal.kelly_fraction | round(2) }} Kelly ({{ signal.contracts }} contracts)
Daily Loss Limit: {{ account.daily_loss_remaining | format_currency }} remaining
Symbol Exposure: {{ exposure.symbol_contracts }}/{{ limits.max_contracts_per_symbol }} contracts
Cooldown Status: {{ 'CLEAR' if cooldown.expired else 'ACTIVE until ' + cooldown.expires_at }}

{% if violations %}
VIOLATIONS DETECTED:
{% for violation in violations %}
- {{ violation.type }}: {{ violation.message }}
{% endfor %}
{% endif %}

Rate this signal from 0.0 to 1.0 based on:
1. Analytics alignment (gamma flip confirmed, liquidity adequate)
2. Risk compliance (position sizing, exposure limits)
3. Market conditions (volatility regime appropriate, VPIN reasonable)
4. Account state (sufficient capital, within daily limits)

Never approve if violations exist or risk caps breached.
Respond with ONLY valid JSON:
{"score": <0.0-1.0>, "reason": "<one line explanation>", "flags": [<optional warning flags>]}
```

Allowed `flags`: `low_liquidity`, `elevated_vol`, `risk_review`. Expand the list via `config/template_validation.yml` when introducing new machine-readable hints.

### `templates/watchdog/summary_markdown.j2`
```jinja
🎯 **Signal Review Required** • {{ signal.strategy | upper }}

**{{ signal.symbol }}** {{ '📈' if signal.direction == 'LONG' else '📉' }} **{{ signal.direction }}**
{% if signal.instrument_type == 'spread' %}
{{ signal.legs[0].strike }}/{{ signal.legs[1].strike }} {{ signal.legs[0].right }} Spread
{% else %}
{{ signal.strike }} {{ signal.right }}
{% endif %}
Size: **{{ signal.contracts }}** contracts

📊 **Market Context**
• Gamma: `{{ analytics.dealer_exposure.gamma | round(4) }}` {{ '✅' if analytics.dealer_exposure.gamma_flip else '' }}
• Liquidity: `{{ analytics.liquidity.index }}/100` {{ '⚠️' if analytics.liquidity.index < 60 else '✅' }}
• Vol Regime: `{{ analytics.volatility_regime.regime }}`
• VPIN: `{{ analytics.vpin.toxicity_score | round(2) }}`

💰 **Risk & Sizing**
• Kelly: `{{ signal.kelly_fraction | round(2) }}` → {{ signal.contracts }} contracts
• Account: ${{ account.available_funds | format_currency }}
• Daily P&L: {{ '🟢' if account.daily_pnl >= 0 else '🔴' }} ${{ account.daily_pnl | round(0) }}

{% if signal.expected_edge %}
📈 **Expected Edge**: {{ signal.expected_edge | round(1) }}%
{% endif %}

⏱️ **SLA**: 60 seconds • Signal ID: `{{ signal.signal_id }}`
Environment: `{{ env }}`

Reply with:
✅ `/approve {{ signal.signal_id }}` 
❌ `/reject {{ signal.signal_id }} <reason>`
⏸️ `/snooze {{ signal.signal_id }} 5`
```

### `templates/watchdog/slack_incident.j2`
```jinja
:rotating_light: **Watchdog Escalation** :rotating_light:

**Issue**: {{ incident.type }}
**Severity**: {{ incident.severity | upper }}
**Module**: {{ incident.module }}
**Time**: {{ incident.timestamp | datetime }}

{% if incident.type == 'sla_breach' %}
**Pending Signals**: {{ incident.pending_count }}
**Oldest**: {{ incident.oldest_age }} seconds
**Auto-cancelled**: {{ incident.cancelled_count }}
{% elif incident.type == 'autopilot_failure' %}
**Error**: {{ incident.error_message }}
**Affected Signals**: {{ incident.signal_ids | join(', ') }}
**Fallback**: Manual review required
{% elif incident.type == 'risk_violation' %}
**Violation**: {{ incident.violation_type }}
**Details**: {{ incident.details }}
**Action Taken**: {{ incident.action }}
{% endif %}

**Environment**: `{{ env }}`
**Correlation ID**: `{{ incident.correlation_id }}`

{% if incident.requires_action %}
:point_right: **Action Required**: {{ incident.action_required }}
{% endif %}
```

### `templates/watchdog/expired_notice.j2`
```jinja
⏱️ **Signal Expired** (No Response)

Signal `{{ signal.signal_id }}` auto-cancelled after {{ sla_seconds }}s timeout.

Symbol: **{{ signal.symbol }}** • Strategy: **{{ signal.strategy }}**
Direction: **{{ signal.direction }}** • Size: **{{ signal.contracts }}** contracts

{% if reviewer_stats %}
📊 Recent SLA Performance:
• Avg Response Time: {{ reviewer_stats.avg_response_time }}s
• Expired Today: {{ reviewer_stats.expired_count }}
• Approval Rate: {{ reviewer_stats.approval_rate }}%
{% endif %}
```

## Social Templates

Each renderer must respect channel compliance limits—pair template rendering with queue caps defined in `config/template_validation.yml` (e.g., Discord premium capped at 500 pending messages) to avoid breaching rate agreements.

### `templates/social/discord/premium_trade.j2`
```jinja
{% set emoji_map = {'opened': '🟢', 'scale_in': '➕', 'scale_out': '➖', 'closed': '🔴'} %}
{{ emoji_map[event.type] }} **{{ event.type | title | replace('_', ' ') }}** • {{ signal.strategy | upper }}

**{{ signal.symbol }}** {{ signal.instrument_description }}
{% if event.type == 'opened' %}
Entry: **${{ trade.entry_price | round(2) }}** × {{ trade.contracts }} contracts
Stop: ${{ trade.stop_price | round(2) }} (-{{ trade.stop_pct }}%)
Targets: {{ trade.tp_levels | join(', ') }}

**Setup Quality**
• Gamma Flip: {{ '✅ Confirmed' if analytics.gamma_flip else '❌ Weak' }}
• Liquidity: {{ analytics.liquidity.index }}/100
• Edge: {{ signal.expected_edge | round(1) }}%

{% elif event.type == 'scale_out' %}
**Partial Exit** ({{ event.tier }})
Closed: {{ event.qty_closed }} contracts @ ${{ event.exit_price | round(2) }}
Remaining: {{ event.qty_remaining }} contracts
P&L This Scale: **+${{ event.scale_pnl | round(0) }}** (+{{ event.scale_pnl_pct | round(1) }}%)

{% elif event.type == 'closed' %}
Exit: **${{ trade.exit_price | round(2) }}**
Hold Time: {{ trade.hold_time_minutes }} minutes

**Performance**
P&L: **{{ '+' if trade.pnl >= 0 else '' }}${{ trade.pnl | round(0) }}** ({{ trade.pnl_pct | round(1) }}%)
MFE: {{ trade.mfe_pct | round(1) }}% • MAE: {{ trade.mae_pct | round(1) }}%
Risk Multiple: {{ trade.risk_multiple | round(1) }}R

{% if trade.execution_quality %}
Fill Quality: {{ trade.execution_quality.slippage_bps }} bps slippage
{% endif %}
{% endif %}

{% if analytics.macro_context %}
📊 **Market Context**: {{ analytics.macro_context }}
{% endif %}

{% if event.type == 'opened' %}
⚡ **Live Position** • Updates to follow
{% endif %}

Environment: `{{ env }}`
```

### `templates/social/discord/basic_trade.j2`
```jinja
{{ '🟢' if event.type == 'opened' else '🔴' }} **Trade {{ event.type | title }}**

**{{ signal.symbol }}** {{ signal.strategy | upper }}
{% if event.type == 'opened' %}
Direction: **{{ signal.direction }}**
Position Size: {{ trade.size_bucket }}

Market Conditions:
• Volatility: {{ analytics.volatility_regime.regime }}
• Trend: {{ analytics.trend_state }}

{% elif event.type == 'closed' %}
Result: **{{ 'WIN' if trade.pnl >= 0 else 'LOSS' }}** 
P&L Range: {{ trade.pnl_bucket }}
Hold Time: {{ trade.hold_time_bucket }}

Today's Win Rate: {{ daily_stats.win_rate }}%
{% endif %}

{% if promotional.show_cta and event.type == 'closed' %}
─────────────────
💎 **Unlock Premium Features**
• Real-time entries & exact fills
• Stop/target levels
• Position sizing details
• Advanced analytics

[Upgrade Now →]({{ promotional.upgrade_url }})
{% endif %}

Environment: `{{ env }}`
```

### `templates/social/discord/free_digest.j2`
```jinja
📊 **Daily Trading Summary**

**Trades Closed Today**: {{ daily_stats.trades_closed }}
**Win Rate**: {{ daily_stats.win_rate }}%
**Best Performing Strategy**: {{ daily_stats.best_strategy }}

**Market Observations**:
{{ market_commentary | truncate(280) }}

{% if daily_stats.highlight_trade %}
🏆 **Top Trade**: {{ daily_stats.highlight_trade.symbol }} • {{ daily_stats.highlight_trade.strategy }}
Result: {{ 'Profitable' if daily_stats.highlight_trade.profitable else 'Loss' }}
{% endif %}

─────────────────
🔓 **Get More Insights**
Premium members see:
• Live trade alerts
• Exact entry/exit prices  
• Risk management levels
• Market analysis reports

[Learn More →]({{ promotional.info_url }})

Environment: `{{ env }}`
```

### `templates/social/telegram/daily_digest.j2`
```jinja
📈 **Daily Performance Report**
{{ report_date | date }}

**Account Summary**
Net Liquidation: ${{ account.net_liquidation | format_currency }}
Daily P&L: {{ '+' if daily_pnl >= 0 else '' }}${{ daily_pnl | round(0) }} ({{ daily_pnl_pct | round(1) }}%)
Unrealized P&L: ${{ unrealized_pnl | round(0) }}

**Trading Activity**
Signals Generated: {{ signals.total }}
Signals Executed: {{ signals.executed }}
Win Rate: {{ performance.win_rate | round(1) }}%
Average Hold: {{ performance.avg_hold_minutes }} min

**Top Performers**
{% for trade in top_trades[:3] %}
{{ loop.index }}. {{ trade.symbol }} {{ trade.strategy }}: +${{ trade.pnl | round(0) }}
{% endfor %}

**Risk Metrics**
Max Drawdown: {{ risk.max_drawdown | round(1) }}%
Sharpe Ratio: {{ risk.sharpe | round(2) }}
Current Exposure: {{ risk.current_delta | round(0) }} deltas

**Open Positions**: {{ open_positions | length }}
{% for position in open_positions %}
• {{ position.symbol }}: {{ position.pnl_pct | round(1) }}%
{% endfor %}

Environment: {{ env }}
Generated: {{ timestamp | datetime }}
```

### `templates/social/twitter/trade_teaser.j2`
```jinja
{%- set result_emoji = '✅' if trade.profitable else '❌' -%}
{{ result_emoji }} {{ trade.symbol }} {{ trade.strategy | upper }}

{{ 'Profit' if trade.profitable else 'Loss' }}: {{ trade.pnl_bucket }}
Win Rate Today: {{ daily_stats.win_rate }}%

{{ market_hook | truncate(160) }}

${{ trade.symbol }} $OPTIONS #TradingStrategy

Env: {{ env }}
```

### `templates/social/reddit/daily_thread.j2`
```jinja
# Daily Trading Report - {{ report_date | date }}

## Performance Summary

| Metric | Value |
|--------|--------|
| Trades Closed | {{ daily_stats.trades_closed }} |
| Win Rate | {{ daily_stats.win_rate }}% |
| Best Strategy | {{ daily_stats.best_strategy }} |
| Market Regime | {{ market.volatility_regime }} |

## Market Analysis

{{ market_commentary }}

### Key Levels Monitored
{% for symbol in ['SPY', 'QQQ', 'IWM'] %}
- **{{ symbol }}**: Support ${{ levels[symbol].support | round(0) }} / Resistance ${{ levels[symbol].resistance | round(0) }}
{% endfor %}

## Strategy Performance

{% for strategy, stats in strategy_performance.items() %}
**{{ strategy }}**
- Signals: {{ stats.count }}
- Success Rate: {{ stats.win_rate }}%
- Average Hold: {{ stats.avg_hold }} minutes
{% endfor %}

## Looking Ahead

{{ next_session_outlook | truncate(500) }}

---

*This report is generated from live trading data. Past performance does not guarantee future results.*

{% if promotional.reddit_footer %}
*Detailed analysis and real-time alerts available for premium subscribers.*
{% endif %}

Environment: `{{ env }}`
```

### `templates/social/promotions/upgrade_cta.j2`
```jinja
{% set cta_variants = {
    'A': 'See what premium traders see',
    'B': 'Join ' + subscriber_count | string + '+ profitable traders',
    'C': 'Get the exact trades, not just hints'
} %}

─────────────────
💎 **{{ cta_variants[variant] }}**

✓ Real-time trade alerts
✓ Exact entry & exit prices
✓ Risk management levels
✓ Advanced market analysis
✓ Priority support

**Limited Time**: {{ promotional.offer_text }}

[{{ promotional.button_text }} →]({{ promotional.tracked_url }}?source={{ channel }}&tier={{ tier }}&variant={{ variant }})

Environment: `{{ env }}`
```

## Localization Configuration

### `templates/localization/en_US.yml`
```yaml
common:
  trade_opened: "Trade Opened"
  trade_closed: "Trade Closed"
  profit: "Profit"
  loss: "Loss"
  win_rate: "Win Rate"
  hold_time: "Hold Time"
  
strategies:
  0dte: "Zero-Day Expiry"
  1dte: "One-Day Expiry"
  14dte: "14-Day Swing"
  moc: "Market-on-Close"

market_regimes:
  calm: "Low Volatility"
  elevated: "Elevated Volatility"
  stressed: "High Stress"

directions:
  long: "Bullish"
  short: "Bearish"
  neutral: "Neutral"

errors:
  sla_breach: "Response timeout - signal auto-cancelled"
  risk_violation: "Risk limits exceeded"
  
cta:
  upgrade_now: "Upgrade Now"
  learn_more: "Learn More"
  get_access: "Get Full Access"
```

### `templates/localization/es_ES.yml`
```yaml
common:
  trade_opened: "Operación Abierta"
  trade_closed: "Operación Cerrada"
  profit: "Ganancia"
  loss: "Pérdida"
  win_rate: "Tasa de Éxito"
  hold_time: "Tiempo de Retención"

strategies:
  0dte: "Vencimiento Mismo Día"
  1dte: "Vencimiento Un Día"
  14dte: "Swing 14 Días"
  moc: "Cierre de Mercado"

# ... continue for all keys
```

## Tone & Style Guidelines

### Platform-Specific Tone

#### Discord Premium
- **Tone**: Professional, detailed, educational
- **Emoji Usage**: Selective, professional (✅❌📊⚡)
- **Technical Depth**: High - include Greeks, exact prices, ratios
- **CTA**: Minimal, focus on value delivery

#### Discord Basic/Free
- **Tone**: Informative but simplified
- **Emoji Usage**: Moderate, friendly
- **Technical Depth**: Medium - general directions, bucketed values
- **CTA**: Regular but not aggressive

#### Telegram
- **Tone**: Concise, actionable, urgent for approvals
- **Emoji Usage**: Functional (🟢🔴⚠️)
- **Technical Depth**: High for internal, medium for broadcasts
- **CTA**: None for internal, subtle for public

#### Twitter/X
- **Tone**: Engaging, punchy, hashtag-optimized
- **Emoji Usage**: Attention-grabbing
- **Technical Depth**: Low - focus on results
- **CTA**: Indirect through performance showcasing

#### Reddit
- **Tone**: Educational, community-focused, analytical
- **Emoji Usage**: None (markdown formatting instead)
- **Technical Depth**: Medium-high with explanations
- **CTA**: Footer only, value-focused

### Content Guidelines

1. **Sensitive Data Handling**
   - Never include: Account numbers, order IDs, personal identifiers
   - Premium only: Exact position sizes, specific P&L amounts
   - Public tiers: Use buckets (Small/Medium/Large, <$100/$100-500/>$500)

2. **Time Sensitivity**
   - Immediate: Trade opens, risk alerts, approval requests
   - Delayed 1min: Basic tier trade notifications
   - Delayed 5min: Free tier summaries
   - End-of-day: Reddit posts, email reports

3. **Compliance Language**
   - Always include: "Past performance does not guarantee future results"
   - For promotions: "Trading involves risk of loss"
   - For analysis: "This is not financial advice"

## Template Testing Framework

### Unit Tests
```python
# tests/test_templates.py
def test_watchdog_summary_render():
    """Verify all required fields render without errors"""
    template = env.get_template('watchdog/summary_markdown.j2')
    context = load_fixture('watchdog_context.json')
    output = template.render(**context)
    
    assert '{{ signal.signal_id }}' not in output
    assert context['signal']['symbol'] in output
    assert len(output) <= 4096  # Telegram limit

def test_tier_redaction():
    """Ensure sensitive data removed for public tiers"""
    premium = render_template('discord/premium_trade.j2', context)
    basic = render_template('discord/basic_trade.j2', context)
    
    assert 'exact_price' in premium
    assert 'exact_price' not in basic
    assert 'size_bucket' in basic

def test_dead_letter_preview():
    """Render failing payloads for quick inspection in CI"""
    payload = load_fixture('dead_letter_payload.json')
    template = env.get_template(payload['template'])
    output = template.render(**payload['context'])

    assert output.strip()
    assert payload['context']['env'] in output
```

Dead-letter fixtures mirror the payloads stored in Redis, keeping CI failures as actionable as production incidents.

### Validation Rules
```yaml
# config/template_validation.yml
templates:
  watchdog/summary_markdown:
    max_length: 4096
    required_vars: [signal, analytics, account]
    allowed_flags: [low_liquidity, elevated_vol, risk_review]

  discord/premium_trade:
    max_length: 2000
    required_vars: [event, signal, trade]
    forbidden_patterns: [account_id, api_key]
    queue_cap: 500

  twitter/trade_teaser:
    max_length: 280
    required_hashtags: 2
    url_shortener: true

  reddit/daily_thread:
    schema_hash: sha256:reddit_daily_v1
    max_length: 20000
    required_vars: [daily_stats, market, strategy_performance]

outputs:
  csv:
    enforce_schema_hash: true
    schema_registry_key: reporting.exec_overview
```

Schema drift is blocked by comparing rendered output to the registered schema hash; any column/order change requires updating the registry entry so downstream consumers are never surprised.

## Deployment Checklist

- [ ] All templates pass Jinja2 syntax validation
- [ ] Unit tests cover all template paths and edge cases
- [ ] Sensitive data redaction verified for each tier
- [ ] Character limits enforced (Twitter 280, Telegram 4096, Discord 2000/embed)
- [ ] Localization keys defined for all user-facing strings
- [ ] A/B test variants configured with tracking URLs
- [ ] Template versioning strategy documented (`templates/watchdog/...:v1` suffixes or release tag `templates-vYYYY.MM`)
- [ ] Rollback procedure defined for template updates
- [ ] Performance impact measured (rendering <10ms per template)
- [ ] Style guide reviewed with stakeholders
- [ ] Env tag rendered in every outbound template to prevent cross-environment leakage

We can further flesh out the exact content but this provides a comprehensive starter guide.
