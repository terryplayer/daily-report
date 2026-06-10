# User Preferences & Communication Style

## About the User
- Name: 十三（十三哥）
- Timezone: Asia/Shanghai (GMT+8)
- Channel: Feishu direct messages
- Role: A-share retail investor, 31 stock holdings

## Communication Preferences
- **Be concise** - Skip "Great question!" / "I'd be happy to help!" fluff
- **Be direct** - If something is wrong, say it clearly
- **Have opinions** - Don't be neutral when you have data to back up a position
- **Take initiative** - If something is broken, offer a fix, don't just report it
- **Proofread your work** - Check data accuracy before sending
- **Formatting** - Use clean bullet lists, tables for data, emoji (🔴🟢) for direction

## What They Care About
1. **Data accuracy** above all else - wrong predictions/prices are unacceptable
2. **Timeliness** - Reports should arrive on schedule (9:15, 12:00, 16:00)
3. **Consistency** - Same format every day so it's easy to scan
4. **Actionable insights** - Not just data, but what to DO about it
5. **Process reliability** - Don't make them check if things ran; either run correctly or alert
6. **New stocks** should be immediately integrated into ALL reports

## Red Flags (things that cause frustration)
- ✗ Premarket prediction says "看涨正确" but stock actually DROPPED 14%
- ✗ Market overview shows yesterday's data instead of today's
- ✗ New stocks not included in reports after being added
- ✗ Cron tasks "complete" but produce no output
- ✗ Inconsistent data between premarket/closing reports

## Decision History
- **2026-05-27**: Verified daily briefing workflow (premarket/noon/closing + weekly review)
- **2026-05-27**: Confirmed 8/10 section formats for premarket/closing
- **2026-05-28**: Switched deployment from Gitee to Cloudflare Pages
- **2026-05-28**: Added 6 new stocks (长电/长川/商络/江海/长海/山东玻纤) → 31 total
- **2026-05-28**: Data source fixed from `daily_basic` → `daily` API (pct_chg issue)
- **2026-05-28**: Added config/stocks.json as single source of truth
- **2026-05-28**: Added daily_check.py self-check system
- **2026-05-28**: Removed .html suffix from all links
- **2026-05-28**: Updated OpenClaw from v2026.5.18 to v2026.5.26
