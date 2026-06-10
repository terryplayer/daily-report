# Daily Report & Stock Briefing System

## Overview
Automated A-share stock briefing system. Generates daily premarket/midday/closing reports + weekly reviews. Deploys to Cloudflare Pages, syncs to Obsidian.

## Persona
- Name: 小十三 🌀
- Communication: Feishu direct messages
- Timezone: Asia/Shanghai (GMT+8)

## Schedule (all times Asia/Shanghai)

| Time | Task | Type | Action |
|------|------|------|--------|
| 7:00 | TED video recommendation | Push | Feishu message |
| 9:00 | Premarket data collection + pre-generation | Silent | Data → generate report → save to /tmp/premarket-content.txt → sync Cloudflare |
| 9:15 | Premarket report delivery | Push | Read /tmp/premarket-content.txt → Feishu → Obsidian → Cloudflare → update watchlist |
| 12:00 | Midday monitor (weekdays only) | Push | Fetch AM data → generate report → Feishu → Obsidian → Cloudflare → update watchlist |
| 15:45 | Closing data collection + pre-generation | Silent | Data → generate report → save to /tmp/closing-content.txt → sync Cloudflare |
| 16:00 | Closing report delivery | Push | Read /tmp/closing-content.txt → Feishu → Obsidian → Cloudflare → update watchlist |
| Sun 12:00 | Weekly review | Push | Full analysis → Feishu → Cloudflare → Obsidian → update watchlist |

## Delivery Chain (ALL reports)
Push Feishu → Sync Obsidian → Update watchlist → Sync Cloudflare

## Data Sources (priority order)
1. **Tushare `daily` API** (primary - has pct_chg) 
2. **东方财富 API** (fallback #1)
3. **腾讯财经 API** (fallback #2)

## Stock Holdings (31 stocks)
Source of truth: `config/stocks.json`

Sectors:
- 科技/半导体 (12): 688549,603019,688381,688323,688530,688268,301389,002600,603629,301396,600584,300604
- 通信/电子 (7): 000586,002384,300433,301611,603516,300975,002484
- AI/数字经济 (4): 300496,301171,300058,300290
- 化工/材料 (4): 600330,002407,300196,605006
- 能源/公用事业 (3): 603318,600396,002418
- 其他 (2): 000981,600860

## Report Templates
- Premarket: Blue header (#58a6ff), dark theme, 8 sections
- Closing: Red header (#f85149), dark theme, 10 sections + deviation analysis
- Midday: Blue header, 5 sections

## Deployment
- GitHub: `terryplayer/daily-report` (main branch → Cloudflare Pages auto-deploy)
- Wrangler backup: `npx wrangler pages deploy . --project-name=daily-report --branch=main`
- Live: `https://daily-report-3ai.pages.dev/`
- Obsidian vault: `/Users/shisan/openclaw-cn/workspace/`
- Report HTML dir: `/Users/shisan/.openclaw/workspace/daily-report-html/`
- Gitee mirror: `terryxue13/daily-report` (origin remote)

## Key Scripts (in workspace/scripts/)
- `tushare_fetch.py` - Stock data from Tushare/Sina/Tencent
- `stock_analysis.py` - RS ranking, multi-factor scoring, volatility alerts
- `parse_html.py` - HTML→Markdown conversion for Obsidian
- `gh-pages-sync.sh` - Deploy to Cloudflare Pages
- `obsidian-sync.sh` - Sync to Obsidian vault
- `daily_check.py` - Morning self-check

## Critical Rules
1. ALL reports go through: Feishu → Obsidian → Cloudflare → watchlist
2. Silent tasks (9:00, 15:45) must validate output files exist
3. Delivery tasks (9:15, 16:00) must have web_search fallback if file missing
4. Stock list source of truth = `config/stocks.json`
5. Links use `https://daily-report-3ai.pages.dev/` WITHOUT `.html` extension
6. 涨用🔴红标，跌用🟢绿标

## Premarket Rating System (v2 - 7-level + 3 correction factors)

### Base Ratings
Directional (counted in accuracy):
- 🔴🔴  Strong buy (high confidence) - RS A+, score TOP5, sector leading
- 🔴    Buy - technicals support but not triple-confirmed
- 🟢    Weak - technicals/funds weakening  
- 🟢🟢  Reduce/Stop-loss - clear downside signal

Non-directional (excluded from accuracy):
- ⚪    Neutral - no clear signal

High confidence (sector resonance):
- 🔴🔴★ Strong + sector resonance - strong stock + sector TOP2
- 🟢🟢★ Weak + sector drag - weak stock + sector BOTTOM2

### 3 Correction Factors (applied sequentially)
1. **Sector momentum** - Sector TOP2 upgrades weak stocks; BOTTOM2 downgrades strong stocks
2. **Overnight sentiment** - US markets up = weak ratings downgraded; US tech up = tech sector bonus
3. **Volume verification** - Shrinking volume decline = exhaustion → weak downgraded; expanding volume decline = capitulation → weak confirmed

## Stock Momentum Signals (v2 - added 2026-05-28)
Added to `stock_analysis.py --json` output as `stock_momentum` field.

Per-stock data:
- `trend_label`: 强势上攻/震荡偏强/横盘震荡/震荡偏弱/弱势下行
- `trend_slope_3d`: 3-day average price change (%)
- `position_label`: 靠近支撑/区间中段/靠近压力  
- `position_pct`: Position in 10-day range (0-100%)
- `volume_price`: 放量上攻/缩量反弹/放量下跌/缩量回调/量价常态 (when vol data available)
- `vol_ratio_5d`: Volume ratio vs 5-day average (when vol data available)
- `support_10d`: 10-day low
- `resistance_10d`: 10-day high

Usage in predictions:
- 弱势下行 + near support → possible bounce, cautious on short
- 强势上攻 + near resistance (>80%) → may hit ceiling, don't chase
- 弱势下行 + mid range → continue down likely, confirm short
- 强势上攻 + below mid → room to grow, confirm long
