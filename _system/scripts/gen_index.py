#!/usr/bin/env python3
"""Generate index.html: static homepage (shell + footer) + dashboard link.
不再包含报告链接/动态内容，报告全部走 dashboard.html"""
import os

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_DIR = os.path.join(WORKSPACE, "daily-report-html")
SHELL = os.path.join(WORKSPACE, "scripts", "index-shell.html")
FOOTER = os.path.join(WORKSPACE, "scripts", "index-footer.html")

def main():
    for f in [SHELL, FOOTER]:
        if not os.path.exists(f):
            print(f"❌ 缺少模板文件: {f}")
            return 1

    with open(SHELL) as f:
        shell = f.read()
    with open(FOOTER) as f:
        footer = f.read()

    # Dashboard 入口横幅
    dashboard_link = (
        '<div style="background:#1a1a2e;border:1px solid #f778ba44;'
        'border-radius:8px;padding:14px 20px;margin-bottom:16px;text-align:center">'
        '<a href="/dashboard" style="color:#f778ba;text-decoration:none;'
        'font-size:15px;font-weight:600">📊 报告中心 Dashboard →</a>'
        '<p style="margin:4px 0 0;font-size:12px;color:#8b949e">'
        '盘前 · 午间 · 收盘 · 周复盘 · 标准版 · 进阶版</p>'
        '</div>'
    )

    idx_path = os.path.join(HTML_DIR, "index.html")
    with open(idx_path, "w") as f:
        f.write(shell + dashboard_link + footer)

    print(f"✅ index.html 已生成（静态主页，报告走 Dashboard）")
    return 0

if __name__ == "__main__":
    exit(main())
