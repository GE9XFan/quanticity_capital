# Build Card Catalog

Each Build Card breaks a deliverable into a bounded unit of work with difficulty, duration, dependencies, and verification steps. Follow this index to identify the next executable task. Owner for all cards: Michael Merrick.

## How to Use Build Cards
1. Pick a card that aligns with the current phase roadmap in `timeline.yaml`.
2. Confirm prerequisites are satisfied (environment, contracts, upstream services).
3. Execute the Implementation steps and capture evidence in the indicated tests or dashboards.
4. Update the parent layer guide status block and tick the relevant tracker item.

## Status Legend
- 🔴 `Not Started`
- 🟡 `In Progress`
- 🟢 `Complete`
- ⚪ `Blocked`

## Card Listing
| Card ID   | Title                                          | Phase                 | Status | Links |
|-----------|------------------------------------------------|-----------------------|--------|-------|
| CARD_000  | Phase 0 Environment Baseline                   | Phase 0 – Foundations | 🔴     | [CARD_000.md](CARD_000.md) |
| CARD_001  | AlphaVantage Client Integration                | Phase 1 – Data        | 🔴     | [CARD_001.md](CARD_001.md) |
| CARD_002  | AlphaVantage Option Chain Normalizer           | Phase 1 – Data        | 🔴     | [CARD_002.md](CARD_002.md) |
| CARD_003  | Redis TimeSeries Schema Definition             | Phase 1 – Data        | 🔴     | [CARD_003.md](CARD_003.md) |
| CARD_004  | IBKR Tick Stream Harmonization                 | Phase 1 – Data        | 🔴     | [CARD_004.md](CARD_004.md) |
| CARD_005  | Indicator & Intraday Cache Service             | Phase 1 – Data        | 🔴     | [CARD_005.md](CARD_005.md) |
| CARD_006  | Ingestion Monitoring & Observability           | Phase 1 – Data        | 🔴     | [CARD_006.md](CARD_006.md) |
| CARD_007  | Redis Bootstrap Script                         | Phase 1 – Data        | 🔴     | [CARD_007.md](CARD_007.md) |
| CARD_008  | Redis Backup Automation                        | Phase 1 – Data        | 🔴     | [CARD_008.md](CARD_008.md) |
| CARD_009  | Query Helper API                               | Phase 1 – Data        | 🔴     | [CARD_009.md](CARD_009.md) |

Add new cards by copying the template below.

```
# BUILD CARD XXX: Title

**Difficulty:** ⭐☆☆☆☆
**Time:** 2 hours
**Prerequisites:**
- Item 1
- Item 2

## Objective
Describe what success looks like.

## Success Criteria
- [ ] Condition 1
- [ ] Condition 2

## Implementation
1. Step-by-step actions.
2. Reference relevant layer guide sections.

## Verification
- Command/test names and expected outputs.
- Monitoring checks to confirm.

## Links to Next Cards
- Related card IDs or layer guide anchors.
```
