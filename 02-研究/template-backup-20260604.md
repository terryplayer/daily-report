# 📦 模板备份记录

> 备份时间：2026-06-04 00:35
> 备份人：小十三
> 备份原因：应用candidate模板前的预防性备份

## 备份位置

```
~/backup_templates_20260604/
```

## 备份文件清单

| 文件 | 说明 | 大小 |
|:----|:----|:----:|
| `template-premarket.html` | 盘前简报样式模板 | 26KB |
| `template-midday.html` | 午间监测样式模板 | 26KB |
| `template-daily-combined.html` | 收盘简报样式模板 | 51KB |
| `template-weekly-review.html` | 周复盘样式模板 | 37KB |
| `premarket-data.md` | 盘前数据采集流程 | 4.5KB |
| `closing-data.md` | 收盘数据采集流程 | 5KB |
| `midday.md` | 午间监测流程 | 3KB |
| `weekly-review.md` | 周复盘流程 | 1.4KB |
| `daily-report-template.md` | 模板规范文档 | 7.3KB |

## 恢复方式

```bash
cp ~/backup_templates_20260604/* /Users/shisan/.openclaw/workspace/scripts/
cp ~/backup_templates_20260604/daily-report-template.md /Users/shisan/.openclaw/workspace/memory/
```
