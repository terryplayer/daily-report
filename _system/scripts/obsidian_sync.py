#!/usr/bin/env python3
"""
🌀 Obsidian 日报同步脚本 — 增强版

功能:
  1. HTML → 高质量Markdown（表格完整转换）
  2. 同步所有报告类型：盘前/午间/收盘/周末/周复盘
  3. 个股独立页面（持仓/）每日追加数据

用法:
  python3 scripts/obsidian_sync.py                    # 同步今日所有报告
  python3 scripts/obsidian_sync.py 2026-05-27          # 指定日期
  python3 scripts/obsidian_sync.py --stock-only        # 仅更新个股页面
"""

import sys, os, re, json
from html.parser import HTMLParser
from datetime import datetime, date

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAULT = "/Users/shisan/.openclaw/workspace"
HTML_DIR = os.path.join(WORKSPACE, "daily-report-html")

WATCHLIST = [
    # (code, name, sector)
    ("688549", "中巨芯-U", "科技/半导体"),
    ("603019", "电科蓝天", "科技/半导体"),
    ("688381", "帝奥微", "科技/半导体"),
    ("688323", "瑞华泰", "科技/半导体"),
    ("688530", "欧莱新材", "科技/半导体"),
    ("688268", "华特气体", "科技/半导体"),
    ("301389", "隆扬电子", "科技/半导体"),
    ("002600", "领益智造", "科技/半导体"),
    ("603629", "利通电子", "科技/半导体"),
    ("301396", "宏景科技", "科技/半导体"),
    ("000586", "汇源通信", "通信/电子"),
    ("002384", "东山精密", "通信/电子"),
    ("300433", "蓝思科技", "通信/电子"),
    ("301611", "珂玛科技", "通信/电子"),
    ("603516", "淳中科技", "通信/电子"),
    ("300496", "中科创达", "AI/数字经济"),
    ("301171", "易点天下", "AI/数字经济"),
    ("300058", "蓝色光标", "AI/数字经济"),
    ("300290", "荣科科技", "AI/数字经济"),
    ("600330", "天通股份", "化工/材料"),
    ("002407", "多氟多", "化工/材料"),
    ("603318", "水发燃气", "能源/公用事业"),
    ("600396", "华电辽能", "能源/公用事业"),
    ("002418", "康盛股份", "能源/公用事业"),
    ("000981", "山子高科", "其他"),
    ("600860", "京城股份", "其他"),
]

STOCK_CODE_MAP = {c: (n, s) for c, n, s in WATCHLIST}


class TableParser(HTMLParser):
    """解析HTML表格 → 列表格式"""
    def __init__(self):
        super().__init__()
        self.tables = []
        self._current_table = []
        self._current_row = []
        self._current_cell = ""
        self._in_table = False
        self._in_tr = False
        self._in_td_th = False
        self._skip_tags = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "table":
            self._current_table = []
            self._in_table = True
        if not self._in_table:
            return
        if tag in ("tr",):
            self._current_row = []
            self._in_tr = True
        if tag in ("td", "th"):
            self._current_cell = ""
            self._in_td_th = True
            # 提取 class 用于颜色判断
            for k, v in attrs:
                if k == "class":
                    self._current_cell_cls = v

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "table":
            if self._current_table:
                self.tables.append(self._current_table)
            self._in_table = False
        if tag == "tr" and self._in_tr:
            if self._current_row:
                self._current_table.append(self._current_row)
            self._current_row = []
            self._in_tr = False
        if tag in ("td", "th"):
            self._in_td_th = False

    def handle_data(self, data):
        if self._in_td_th:
            self._current_cell += data.strip()

    def handle_startendtag(self, tag, attrs):
        pass


def html_to_markdown(html_content, report_type="premarket"):
    """HTML 转 Markdown，保留表格结构"""
    # 提取标题
    title_m = re.search(r'<title>(.*?)</title>', html_content, re.DOTALL)
    title = title_m.group(1).strip() if title_m else f"{report_type} 简报"

    # 解析所有表格
    parser = TableParser()
    parser.feed(html_content)

    # 按 section 提取内容
    # 每个 section 结构: <div class="section">...内容...</div> 然后可能有注释/空白再 </div>
    sections = re.findall(
        r'<div class="section">(.*?)</div>', html_content, re.DOTALL)

    md_parts = []

    for sec_html in sections:
        # 提取板块标题 h2
        h2_m = re.search(r'<h2>(.*?)</h2>', sec_html, re.DOTALL)
        heading = ""
        if h2_m:
            heading = h2_m.group(1).strip()
            heading = re.sub(r'<[^>]+>', '', heading)  # 去内嵌标签

        # 提取该section内的文字段落
        texts = []
        for p in re.findall(r'<p[^>]*>(.*?)</p>', sec_html, re.DOTALL):
            txt = re.sub(r'<[^>]+>', '', p)
            txt = _unescape(txt)
            txt = re.sub(r'\s+', ' ', txt).strip()
            if txt:
                texts.append(txt)

        # 提取该section内的表格并转为Markdown
        sec_parser = TableParser()
        sec_parser.feed(sec_html)

        md_lines = []
        if heading:
            md_lines.append(f"\n### {heading}\n")

        for text in texts:
            md_lines.append(text)
            md_lines.append("")

        for table in sec_parser.tables:
            md_table = table_to_markdown(table)
            if md_table:
                md_lines.append(md_table)
                md_lines.append("")

        md_parts.append("\n".join(md_lines).strip())

    body = "\n\n".join(md_parts)
    if not body.strip():
        # fallback: 纯文本提取
        body = re.sub(r'<[^>]+>', ' ', html_content)
        body = self._unescape(body)
        body = re.sub(r'\s+', ' ', body).strip()

    # 提取日期
    date_m = re.search(r'(\d{4})[\.-](\d{2})[\.-](\d{2})', title)
    report_date = f"{date_m.group(1)}-{date_m.group(2)}-{date_m.group(3)}" if date_m else date.today().isoformat()

    return title, report_date, body


def _unescape(text):
    """HTML转义还原"""
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    return text


def table_to_markdown(table_data):
    """HTML表格数据 → Markdown 表格"""
    if not table_data or len(table_data) < 2:
        return ""

    header = table_data[0]
    rows = table_data[1:]

    # 过滤空行
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        return ""

    # 生成表头
    md = "| " + " | ".join(header) + " |\n"
    md += "| " + " | ".join(["---"] * len(header)) + " |\n"

    for row in rows:
        # 补足列数
        while len(row) < len(header):
            row.append("")
        md += "| " + " | ".join(row[:len(header)]) + " |\n"

    return md


def extract_stock_data(body_text, report_date):
    """从简报文字中提取个股行情数据"""
    stock_data = {}
    for code, name, sector in WATCHLIST:
        # 在正文中查找该股票代码
        # 格式示例：帝奥微 688381 44.90 🔴+0.22%
        patterns = [
            rf'{re.escape(name)}\s+{code}\s+([\d.]+)\s+([🟢🔴⚪][+-]?[\d.]+%)',
            rf'{code}[^0-9]*?([\d.]+)[^0-9]*?([🟢🔴⚪][+-]?[\d.]+%)',
        ]
        for pat in patterns:
            m = re.search(pat, body_text)
            if m:
                price = m.group(1)
                change = m.group(2)
                stock_data[code] = {
                    "name": name,
                    "sector": sector,
                    "price": price,
                    "change": change,
                    "date": report_date
                }
                break
    return stock_data


def sync_report(report_type, date_str):
    """同步一份报告到Obsidian"""
    type_map = {
        "premarket": ("盘前简报", "盘前", "premarket"),
        "midday": ("午间监测", "午间", "midday"),
        "daily-combined": ("收盘简报", "收盘", "daily-combined"),
        "weekend": ("周末简报", "周末", "weekend"),
        "weekly-review": ("周复盘", "周复盘", "weekly-review"),
    }

    if report_type not in type_map:
        print(f"  ⚠️ 未知类型: {report_type}")
        return None, {}

    label_cn, type_tag, prefix = type_map[report_type]
    html_file = os.path.join(HTML_DIR, f"{prefix}-{date_str}.html")

    if not os.path.exists(html_file):
        print(f"  ⏭ 没有 {label_cn} ({os.path.basename(html_file)})")
        return None, {}

    print(f"  📋 {label_cn}...")

    with open(html_file) as f:
        html_content = f.read()

    title, _, body = html_to_markdown(html_content, report_type)

    # 日期显示
    display_date = date_str.replace("-", ".")
    weekday_map = {
        0: "周一", 1: "周二", 2: "周三", 3: "周四",
        4: "周五", 5: "周六", 6: "周日"
    }
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        weekday = weekday_map[dt.weekday()]
    except:
        weekday = ""

    # frontmatter
    frontmatter = f"""---
title: "{title}"
date: {date_str}
type: {type_tag}
tags:
  - 日报
  - {type_tag}
  - 股票
---"""

    # 正文
    content = f"""{frontmatter}

# {'📋' if type_tag=='盘前' else '🌤' if type_tag=='午间' else '📊' if type_tag=='收盘' else '🌙' if type_tag=='周末' else '📑'} {label_cn} · {display_date} {weekday}

{body}

---

📎 [在线查看](https://daily-report-3ai.pages.dev/{prefix}-{date_str}.html)
"""

    # 写入文件
    vault_dir = os.path.join(VAULT, "日报", date_str)
    os.makedirs(vault_dir, exist_ok=True)
    out_file = os.path.join(vault_dir, f"{prefix}-{date_str}.md")

    with open(out_file, "w") as f:
        f.write(content)

    print(f"    ✅ {out_file}")

    # 提取个股数据
    stock_data = extract_stock_data(body, date_str)
    return out_file, stock_data


def update_stock_pages(all_stock_data, date_str):
    """更新持仓/ 下的个股独立页面"""
    stock_dir = os.path.join(VAULT, "持仓")
    os.makedirs(stock_dir, exist_ok=True)

    updated = 0
    for code, name, sector in WATCHLIST:
        data = all_stock_data.get(code)
        if not data:
            continue

        file_name = f"{name}-{code}.md"
        file_path = os.path.join(stock_dir, file_name)

        # 日期显示
        display_date = date_str.replace("-", ".")
        weekday_map = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            weekday = weekday_map[dt.weekday()]
        except:
            weekday = ""

        line = f"| {display_date} {weekday} | {data['price']} | {data['change']} |\n"

        if os.path.exists(file_path):
            # 追加当日数据（在表格最后一行前插入）
            with open(file_path) as f:
                existing = f.read()

            # 找到表格插入点
            table_marker = "| 日期 | 收盘价 | 涨跌幅 |"
            if table_marker in existing:
                # 检查是否已有今日数据
                if display_date in existing:
                    # 替换已有行
                    new_content = re.sub(
                        rf'\| {re.escape(display_date)} .* \|',
                        line.strip(),
                        existing
                    )
                else:
                    # 在表格末尾、---之前插入
                    new_content = existing.rstrip()
                    # 找到最后一个数据行，在其后添加
                    new_content += "\n" + line
            else:
                # 新建表格
                new_content = existing.rstrip() + "\n\n"
                new_content += "## 每日行情\n\n"
                new_content += "| 日期 | 收盘价 | 涨跌幅 |\n"
                new_content += "|------|--------|--------|\n"
                new_content += line
        else:
            # 新建个股页面
            new_content = f"""---
title: "{name}"
code: {code}
sector: "{sector}"
tags:
  - 持仓
  - {sector}
  - {name}
---

# {name} ({code})

**板块**: {sector}

## 基本信息

| 项目 | 内容 |
|------|------|
| 代码 | {code} |
| 名称 | {name} |
| 板块 | {sector} |

## 每日行情

| 日期 | 收盘价 | 涨跌幅 |
|------|--------|--------|
{line}"""

        # 补充板块导航链接
        sector_tag = sector.replace("/", "")
        new_content += f"\n---\n板块: [[_moc/持仓分析|{sector}]]\n"

        with open(file_path, "w") as f:
            f.write(new_content)
        updated += 1

    print(f"  📈 个股页面更新: {updated} 只")
    return updated


def main():
    # 解析日期参数
    if len(sys.argv) > 1 and sys.argv[1] == "--stock-only":
        date_str = date.today().isoformat()
        stock_only = True
    elif len(sys.argv) > 1 and re.match(r'^\d{4}-\d{2}-\d{2}$', sys.argv[1]):
        date_str = sys.argv[1]
        stock_only = "--stock-only" in sys.argv
    else:
        date_str = date.today().isoformat()
        stock_only = False

    display = date_str.replace("-", ".")
    print(f"\n🌀 同步到 Obsidian | {display}\n")

    # 收集该日期的所有报告类型
    report_types = ["premarket", "midday", "daily-combined", "weekend", "weekly-review"]

    all_stock_data = {}

    if not stock_only:
        for rtype in report_types:
            file_path, stock_data = sync_report(rtype, date_str)
            if stock_data:
                all_stock_data.update(stock_data)

    # 更新个股页面
    if all_stock_data:
        update_stock_pages(all_stock_data, date_str)
    elif not stock_only:
        # 尝试从现有MD文件提取数据
        vault_dir = os.path.join(VAULT, "日报", date_str)
        if os.path.exists(vault_dir):
            for f in os.listdir(vault_dir):
                if f.endswith(".md"):
                    with open(os.path.join(vault_dir, f)) as fh:
                        content = fh.read()
                    data = extract_stock_data(content, date_str)
                    if data:
                        all_stock_data.update(data)
            if all_stock_data:
                update_stock_pages(all_stock_data, date_str)

    print(f"\n✅ 同步完成 | {display}\n")


if __name__ == "__main__":
    main()
