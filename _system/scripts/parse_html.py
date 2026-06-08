#!/usr/bin/env python3
"""HTML → Markdown 转换工具 — 用于 Obsidian 同步"""
import re, sys
from html.parser import HTMLParser

# ---- 颜色/标记映射 ----
COLOR_UP = "🔴"   # 上涨/红色
COLOR_DOWN = "🟢"  # 下跌/绿色
COLOR_FLAT = "⚪"  # 持平

def unescape(text):
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&#x27;", "'")
    text = text.replace("&#34;", '"').replace("&#160;", " ")
    return text

class TableExtractor(HTMLParser):
    """从HTML中提取表格 → 二维数组"""
    def __init__(self):
        super().__init__()
        self.tables = []
        self._cur_table = None
        self._cur_row = None
        self._cur_cell = None
        self._in_cell = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "table":
            self._cur_table = []
        elif tag == "tr" and self._cur_table is not None:
            self._cur_row = []
        elif tag in ("td", "th") and self._cur_row is not None:
            self._cur_cell = ""
            self._in_cell = True

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ("td", "th") and self._cur_cell is not None:
            self._cur_row.append(self._cur_cell.strip())
            self._cur_cell = None
            self._in_cell = False
        elif tag == "tr" and self._cur_row is not None:
            self._cur_table.append(self._cur_row)
            self._cur_row = None
        elif tag == "table" and self._cur_table is not None:
            if self._cur_table:
                self.tables.append(self._cur_table)
            self._cur_table = None

    def handle_data(self, data):
        if self._in_cell and self._cur_cell is not None:
            self._cur_cell += data

    def handle_startendtag(self, tag, attrs):
        pass

def extract_tables(html):
    """提取HTML中所有表格，返回[[[row_cells]]]"""
    parser = TableExtractor()
    parser.feed(html)
    return parser.tables

def extract_sections(html):
    """提取 <div class='section'> 包裹的文本块"""
    sections = []
    # 找到所有 section 起始位置
    starts = [m.end() for m in re.finditer(r'<div\s+class="section"[^>]*>', html)]
    if not starts:
        return sections
    for start in starts:
        # 从此位置开始找对应的 </div>，跟踪 div 嵌套
        depth = 1
        i = start
        content = ""
        while i < len(html) and depth > 0:
            # 查找下一个 <div 或 </div>
            next_open = html.find('<div', i)
            next_close = html.find('</div>', i)
            if next_open == -1 and next_close == -1:
                break
            if next_close == -1 or (next_open != -1 and next_open < next_close):
                # 遇到开启标签
                content += html[i:next_open]
                # 跳过整个标签
                tag_end = html.find('>', next_open)
                if tag_end == -1:
                    break
                content += html[next_open:tag_end+1]
                i = tag_end + 1
                depth += 1
            else:
                # 遇到关闭标签
                # 把从 i 到 next_close 的内容加入
                content += html[i:next_close]
                i = next_close + 6
                depth -= 1
                if depth == 0:
                    sections.append(content.strip())
                    content = ""
                    break
        if content.strip():
            sections.append(content.strip())
    return sections

def table_to_md(table):
    """二维数组 → Markdown 表格"""
    if not table or len(table) < 2:
        return ""
    header = table[0]
    rows = [r for r in table[1:] if any(c.strip() for c in r)]
    if not rows:
        return ""
    cols = max(len(header), max(len(r) for r in rows))
    while len(header) < cols:
        header.append("")
    md = "| " + " | ".join(header[:cols]) + " |\n"
    md += "| " + " | ".join(["---"] * cols) + " |\n"
    for row in rows:
        while len(row) < cols:
            row.append("")
        md += "| " + " | ".join(row[:cols]) + " |\n"
    return md

def get_weekday(date_str):
    from datetime import datetime
    wds = ["周一","周二","周三","周四","周五","周六","周日"]
    try:
        return wds[datetime.strptime(date_str, "%Y-%m-%d").weekday()]
    except:
        return ""

def html_to_md(html_file, report_type, date_str):
    """HTML文件 → Markdown 内容"""
    with open(html_file) as f:
        html = f.read()

    # 提取标题
    title_m = re.search(r'<title>(.*?)</title>', html, re.DOTALL)
    title = unescape(title_m.group(1).strip()) if title_m else f"{report_type} 简报"

    # 提取 sections
    sections_html = extract_sections(html)

    # 提取所有表格（全局，不按 section 分）
    all_tables = extract_tables(html)

    # 组装 Markdown
    md_parts = []
    table_idx = 0

    for sec_html in sections_html:
        # 提取 h2 标题
        h2_m = re.search(r'<h2>(.*?)</h2>', sec_html, re.DOTALL)
        heading = ""
        if h2_m:
            heading = re.sub(r'<[^>]+>', '', h2_m.group(1)).strip()

        # 提取纯文本段落（去标签，保留换行）
        # block-level 标签转换行
        text = re.sub(r'<br\s*/?>', '\n', sec_html, flags=re.IGNORECASE)
        text = re.sub(r'</?(?:div|p|tr|/tr|table|/table|h\d|ul|ol|li)[^>]*>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = unescape(text)
        # 压缩空白，但保留段落换行
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n[ \t]+', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()

        # 去掉标题本身的重复（如果 text 以 heading 开头）
        if heading and text.startswith(heading):
            text = text[len(heading):].strip()

        md_lines = []
        if heading:
            md_lines.append(f"### {heading}\n")

        if text:
            md_lines.append(text)
            md_lines.append("")

        # 查找这个 section 中有多少个 <table>
        table_count = sec_html.count("<table")
        for _ in range(table_count):
            if table_idx < len(all_tables):
                md_table = table_to_md(all_tables[table_idx])
                if md_table:
                    md_lines.append(md_table)
                    md_lines.append("")
                table_idx += 1

        md_parts.append("\n".join(md_lines).strip())

    body = "\n\n".join(md_parts)
    if not body.strip():
        body = unescape(re.sub(r'<[^>]+>', ' ', html))
        body = re.sub(r'\s+', ' ', body).strip()

    weekday = get_weekday(date_str)
    display_date = date_str.replace("-", ".")

    # 类型标签
    type_emoji = {"premarket":"📋","midday":"🌤","daily-combined":"📊","weekend":"🌙","weekly-review":"📑"}
    type_cn = {"premarket":"盘前简报","midday":"午间监测","daily-combined":"收盘简报","weekend":"周末简报","weekly-review":"周复盘"}
    type_tag = {"premarket":"盘前","midday":"午间","daily-combined":"收盘","weekend":"周末","weekly-review":"周复盘"}
    prefix_map = {"premarket":"premarket","midday":"midday","daily-combined":"daily-combined","weekend":"weekend","weekly-review":"weekly-review"}

    emoji = type_emoji.get(report_type, "📋")
    cn = type_cn.get(report_type, report_type)
    tag = type_tag.get(report_type, report_type)
    prefix = prefix_map.get(report_type, report_type)

    frontmatter = f"""---
title: "{title}"
date: {date_str}
type: {tag}
tags:
  - 日报
  - {tag}
  - 股票
---"""

    content = f"""{frontmatter}

# {emoji} {cn} · {display_date} {weekday}

{body}

---

📎 [在线查看](https://daily-report-3ai.pages.dev/{prefix}-{date_str})
"""

    return content, body


def extract_stock_rows(body_text):
    """从 Markdown 正文中提取个股行情数据"""
    stock_data = {}
    lines = body_text.split("\n")

    for i, line in enumerate(lines):
        code_m = re.search(r'\b(6\d{5}|3\d{5}|0\d{5})\b', line)
        if not code_m:
            continue
        code = code_m.group(1)

        # Look at this line and next 2 lines for price and change
        price = None
        change = None
        for j in range(i, min(i + 3, len(lines))):
            # 查找价格: 连续数字.数字 格式
            prices = re.findall(r'\b(\d+\.\d{2})\b', lines[j])
            changes = re.findall(r'[🔴🟢⚪]\s*[+-]?[\d.]+%', lines[j])
            if prices and not price:
                price = prices[0]
            if changes and not change:
                change = changes[0].replace(' ', '')
            if price and change:
                break

        if price and change:
            stock_data[code] = {'price': price, 'change': change}

    return stock_data


def run(html_dir, vault_dir, date_str):
    """运行同步"""
    types = ["premarket", "midday", "daily-combined", "weekend", "weekly-review"]
    all_stock_data = {}
    results = []

    for rt in types:
        prefix_map = {"premarket":"premarket","midday":"midday","daily-combined":"daily-combined","weekend":"weekend","weekly-review":"weekly-review"}
        html_file = f"{html_dir}/{prefix_map[rt]}-{date_str}.html"
        if not os.path.exists(html_file):
            continue

        content, body = html_to_md(html_file, rt, date_str)

        # 写入
        out_dir = os.path.join(vault_dir, "日报", date_str)
        os.makedirs(out_dir, exist_ok=True)
        out_file = os.path.join(out_dir, f"{prefix_map[rt]}-{date_str}.md")
        with open(out_file, "w") as f:
            f.write(content)

        # 提取个股数据
        stock_data = extract_stock_rows(body)
        all_stock_data.update(stock_data)
        results.append((rt, out_file))

    # 更新个股页面
    stock_data = update_stock_pages(all_stock_data, date_str, vault_dir)
    return results, stock_data


def update_stock_pages(all_stock_data, date_str, vault_dir):
    """更新持仓/ 个股页面"""
    stock_dir = os.path.join(vault_dir, "持仓")
    os.makedirs(stock_dir, exist_ok=True)

    # 完整持仓列表
    watchlist = [
        ("688549","中巨芯-U","科技/半导体"),("603019","电科蓝天","科技/半导体"),
        ("688381","帝奥微","科技/半导体"),("688323","瑞华泰","科技/半导体"),
        ("688530","欧莱新材","科技/半导体"),("688268","华特气体","科技/半导体"),
        ("301389","隆扬电子","科技/半导体"),("002600","领益智造","科技/半导体"),
        ("603629","利通电子","科技/半导体"),("301396","宏景科技","科技/半导体"),
        ("600584","长电科技","科技/半导体"),("300604","长川科技","科技/半导体"),
        ("000586","汇源通信","通信/电子"),("002384","东山精密","通信/电子"),
        ("300433","蓝思科技","通信/电子"),("301611","珂玛科技","通信/电子"),
        ("603516","淳中科技","通信/电子"),("300975","商络电子","通信/电子"),
        ("002484","江海股份","通信/电子"),
        ("300496","中科创达","AI/数字经济"),("301171","易点天下","AI/数字经济"),
        ("300058","蓝色光标","AI/数字经济"),("300290","荣科科技","AI/数字经济"),
        ("600330","天通股份","化工/材料"),("002407","多氟多","化工/材料"),
        ("300196","长海股份","化工/材料"),("605006","山东玻纤","化工/材料"),
        ("603318","水发燃气","能源/公用事业"),("600396","华电辽能","能源/公用事业"),
        ("002418","康盛股份","能源/公用事业"),
        ("000981","山子高科","其他"),("600860","京城股份","其他"),
    ]

    from datetime import datetime
    wds = ["周一","周二","周三","周四","周五","周六","周日"]
    weekday = wds[datetime.strptime(date_str, "%Y-%m-%d").weekday()]
    display_date = date_str.replace("-", ".")

    updated = 0
    for code, name, sector in watchlist:
        data = all_stock_data.get(code)
        if not data:
            continue

        file_path = os.path.join(stock_dir, f"{name}-{code}.md")
        line = f"| {display_date} {weekday} | {data['price']} | {data['change']} |\n"

        if os.path.exists(file_path):
            with open(file_path) as f:
                existing = f.read()
            # 检查是否已有今日数据
            if display_date in existing:
                # 替换
                existing = re.sub(
                    rf'\| {re.escape(display_date)} .* \|',
                    line.strip(),
                    existing
                )
            else:
                # 在表格最后追加
                tbl_end = existing.rfind("|------|--------|--------|")
                if tbl_end >= 0:
                    insert_at = existing.index("\n", tbl_end) + 1
                    existing = existing[:insert_at] + line + existing[insert_at:]
                else:
                    existing += f"\n## 每日行情\n\n| 日期 | 收盘价 | 涨跌幅 |\n|------|--------|--------|\n{line}"
            new_content = existing
        else:
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
{line}
"""

        # 板块导航
        new_content += f"\n---\n板块: [[_moc/持仓分析|{sector}]]\n"

        with open(file_path, "w") as f:
            f.write(new_content)
        updated += 1

    print(f"  📈 个股页面更新: {updated} 只")
    return updated


if __name__ == "__main__":
    import os
    WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    VAULT = "/Users/shisan/openclaw-cn/workspace"
    HTML_DIR = os.path.join(WORKSPACE, "daily-report-html")

    if len(sys.argv) > 1:
        date_str = sys.argv[1]
    else:
        from datetime import date
        date_str = date.today().isoformat()

    print(f"\n🌀 同步到 Obsidian | {date_str}\n")
    results, stock_count = run(HTML_DIR, VAULT, date_str)
    for rt, fp in results:
        print(f"  ✅ {rt}: {os.path.basename(fp)}")
    print(f"\n✅ 同步完成\n")
