#!/usr/bin/env python3
"""
📋 报告验证器 v2 — 全要素自动比对
"""

import re, sys, os, json

CANDIDATE_PATHS = {
    'premarket': 'daily-report-html/temp_reports/盘前报告_candidate.html',
    'midday': 'daily-report-html/temp_reports/午间监测_candidate.html',
    'closing': 'daily-report-html/temp_reports/收盘简报_candidate.html',
    'weekly': 'daily-report-html/temp_reports/周复盘_candidate.html',
}
THEME_COLORS = {'premarket':'#58a6ff','midday':'#56d4dd','closing':'#f85149','weekly':'#f778ba'}

def get_candidate_html(report_type):
    path = CANDIDATE_PATHS.get(report_type)
    if not path: return None, f"未知类型: {report_type}"
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', path)
    path = os.path.abspath(path)
    if not os.path.exists(path): return None, f"模板缺失: {path}"
    with open(path) as f: return f.read(), None

def _load_sample_keywords(report_type):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'candidate_sample_keywords.json')
    if not os.path.exists(path): return set()
    with open(path) as f: data = json.load(f)
    return set(data.get(report_type, []))

def validate(report_type, html, raise_on_error=True):
    errors = []
    cand, err = get_candidate_html(report_type)
    if err: errors.append(err); return errors

    cand_css = re.search(r'<style>(.*?)</style>', cand, re.DOTALL)
    gen_css = re.search(r'<style>(.*?)</style>', html, re.DOTALL)
    ccs = cand_css.group(1) if cand_css else ''
    gcs = gen_css.group(1) if gen_css else ''

    # 1. CSS类
    cc = {c for c in (set(re.findall(r'\.([a-z][\w-]*)', ccs)) - set(re.findall(r'\.([a-z][\w-]*)', gcs))) if len(c)>1}
    if cc: errors.append(f'缺少CSS类: {sorted(cc)}')

    # 2. 主题色
    th = THEME_COLORS.get(report_type)
    if th and th not in html: errors.append(f'缺少主题色 {th}')

    # 3. h1颜色
    ch = re.search(r'h1\{[^}]*color:([^;}]+)', ccs)
    gh = re.search(r'h1\{[^}]*color:([^;}]+)', gcs)
    if ch and gh and ch.group(1).strip() != gh.group(1).strip():
        errors.append(f'h1颜色: 候选={ch.group(1).strip()} 生成={gh.group(1).strip()}')

    # 4. h1下划线
    cb = re.search(r'h1\{[^}]*border-bottom[^}]*#[0-9a-fA-F]{6}', ccs)
    gb = re.search(r'h1\{[^}]*border-bottom[^}]*#[0-9a-fA-F]{6}', gcs)
    if cb and gb:
        cbc = re.search(r'#[0-9a-fA-F]{6}', cb.group()).group()
        gbc = re.search(r'#[0-9a-fA-F]{6}', gb.group()).group()
        if cbc != gbc: errors.append(f'h1下划线: 候选={cbc} 生成={gbc}')
    elif cb and not gb: errors.append('缺少h1下划线')

    # 5. 字体
    cf = re.search(r'font-family:([^;}]+)', ccs)
    gf = re.search(r'font-family:([^;}]+)', gcs)
    if cf and gf and cf.group(1).strip() != gf.group(1).strip():
        errors.append(f'字体: 候选={cf.group(1).strip()} 生成={gf.group(1).strip()}')

    # 6. 板块结构
    ch2 = set(re.findall(r'<h2>([^<]+)', cand))
    gh2 = set(re.findall(r'<h2>([^<]+)', html))
    ms = ch2 - gh2; es = gh2 - ch2
    if ms: errors.append(f'缺少板块: {ms}')
    if es: errors.append(f'多余板块: {es}')

    # 7. 表格（weekly放宽顺序检查）
    ct = re.findall(r'<table>.*?</table>', cand, re.DOTALL)
    gt = re.findall(r'<table>.*?</table>', html, re.DOTALL)
    
    # 逐section检查表格数（确保每个板块的表格分布正确）
    c_secs = [s for s in cand.split('<div class="section">') if '<h2>' in s]
    g_secs = [s for s in html.split('<div class="section">') if '<h2>' in s]
    for c_sec, g_sec in zip(c_secs, g_secs):
        c_h2 = re.search(r'<h2>([^<]+)', c_sec)
        g_h2 = re.search(r'<h2>([^<]+)', g_sec)
        if c_h2 and g_h2 and c_h2.group(1) == g_h2.group(1):
            c_t = c_sec.count('<table>')
            g_t = g_sec.count('<table>')
            if c_t != g_t and c_t > 0:
                errors.append(f'[{c_h2.group(1)[:10]}...] 表格数: 候选={c_t} 生成={g_t}')
    if report_type == 'weekly' or report_type == 'midday':
        # 只确保每种列头都存在，不要求顺序
        cand_sets = {tuple(re.findall(r'<th[^>]*>([^<]+)', t)) for t in ct}
        gen_sets = {tuple(re.findall(r'<th[^>]*>([^<]+)', t)) for t in gt}
        missing_ths = cand_sets - gen_sets
        if missing_ths:
            for m in missing_ths: errors.append(f'缺少候选表列头: {list(m)}')
    else:
        if len(ct) != len(gt): errors.append(f'表格数: 候选={len(ct)} 生成={len(gt)}')
        for i, (c_, g_) in enumerate(zip(ct, gt)):
            cth = re.findall(r'<th[^>]*>([^<]+)', c_)
            gth = re.findall(r'<th[^>]*>([^<]+)', g_)
            if cth != gth: errors.append(f'表{i+1}: 候选={cth} 生成={gth}')

    # 8. colgroup
    ccol = re.findall(r'<col class="([^"]+)"', cand)
    gcol = re.findall(r'<col class="([^"]+)"', html)
    if ccol and gcol and sorted(set(ccol)) != sorted(set(gcol)):
        errors.append(f'colgroup: 候选={sorted(set(ccol))} 生成={sorted(set(gcol))}')

    # 9. 颜色
    for c in ['#f85149','#3fb950','#d9a52e','#8b949e','#0d1117','#e6edf3']:
        if c in cand and c not in html: errors.append(f'缺少颜色 {c}')

    # 10. 占位符
    ph = re.findall(r'\{\{[A-Z_]+\}\}', html)
    if ph: errors.append(f'残留占位符: {ph}')

    # 11. 标签
    for t in ['tag-up','tag-down','tag-hold']:
        if t in cand and t not in html: errors.append(f'缺少 {t}')
    for r in ['rate-aplus','rate-a','rate-b','rate-c','rate-d']:
        if r in cand and r not in html: errors.append(f'缺少 {r}')

    # 12. Banner/Footer
    if 'class="banner"' in cand and 'class="banner"' not in html: errors.append('缺少Banner')
    if 'class="footer"' in cand and 'class="footer"' not in html: errors.append('缺少Footer')

    # 13. 专用布局类
    for lc in ['metric-grid','metric-card','stat-line','tech-signal','judge-up','judge-down','judge-neutral','summary-card','sub-hdr','lbl','num']:
        if lc in ccs and lc not in gcs: errors.append(f'缺少布局类: .{lc}')

    # 14. 背景渐变
    if report_type in ('closing','weekly') and 'linear-gradient' not in gcs:
        errors.append('缺少背景渐变')


    
    # 16. style="color:up" 错误用法检查
    bad_colors = re.findall(r'style="[^"]*color:(up|down)[^"]*"', html)
    if bad_colors:
        errors.append(f'CSS类名被当颜色值: {len(bad_colors)}处 (color:up/down)')
    
    if errors:
        msg = '\n' + ('-'*50) + f'\n❌ 验证失败 ({report_type}):\n' + '\n'.join(f'  - {e}' for e in errors)
        if raise_on_error: raise ValueError(msg)
    return errors

if __name__ == '__main__':
    if len(sys.argv) < 2: print("用法: python3 validate_report.py <type> [html_file]"); sys.exit(1)
    rt = sys.argv[1]; html = open(sys.argv[2]).read() if len(sys.argv) >= 3 else ''
    e = validate(rt, html, raise_on_error=True)
    if e: print(f'❌ {len(e)}个问题'); [print(f'  - {x}') for x in e]; sys.exit(1)
    else: print(f'✅ {rt} 验证通过')
