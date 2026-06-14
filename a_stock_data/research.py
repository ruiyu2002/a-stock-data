"""Auto-extracted from SKILL.md (V3.2.2). See research.py source comments for section ids."""
from __future__ import annotations
import re
import time
import json
import random
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
import requests
import pandas as pd
from a_stock_data._helpers import get_prefix, em_get, eastmoney_datacenter, EM_SESSION, EM_MIN_INTERVAL, UA, DATACENTER_URL

def _norm(t: str) -> str:
    """Normalize ticker to 6-digit code: '600519' / 'SH600519' / '600519.SH' -> '600519'."""
    s = t.strip().upper().replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
    for p in ('SH', 'SZ', 'BJ'):
        if s.startswith(p):
            s = s[len(p):]
    return s
REPORT_API = 'https://reportapi.eastmoney.com/report/list'
PDF_TPL = 'https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'

def eastmoney_reports(code: str, max_pages: int=5) -> list[dict]:
    """拉取指定股票的研报列表"""
    all_records = []
    for page in range(1, max_pages + 1):
        params = {'industryCode': '*', 'pageSize': '100', 'industry': '*', 'rating': '*', 'ratingChange': '*', 'beginTime': '2000-01-01', 'endTime': '2030-01-01', 'pageNo': str(page), 'fields': '', 'qType': '0', 'orgCode': '', 'code': code, 'rcode': '', 'p': str(page), 'pageNum': str(page), 'pageNumber': str(page)}
        r = em_get(REPORT_API, params=params, headers={'Referer': 'https://data.eastmoney.com/'}, timeout=30)
        d = r.json()
        rows = d.get('data') or []
        if not rows:
            break
        all_records.extend(rows)
        if page >= (d.get('TotalPage', 1) or 1):
            break
    return all_records

def download_pdf(record: dict, target_dir: str='./reports') -> str | None:
    """下载单份研报PDF，返回保存路径或None"""
    info_code = record.get('infoCode', '')
    if not info_code:
        return None
    date = (record.get('publishDate') or '')[:10]
    org = record.get('orgSName') or '未知'
    title = re.sub('[\\\\/:*?"<>|]', '_', record.get('title', ''))[:80]
    fname = f'{date}_{org}_{title}.pdf'
    target = Path(target_dir) / fname
    if target.exists():
        return str(target)
    url = PDF_TPL.format(info_code=info_code)
    r = em_get(url, headers={'Referer': 'https://data.eastmoney.com/'}, timeout=60)
    if r.status_code == 200 and len(r.content) >= 1024:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(r.content)
        return str(target)
    return None
from io import StringIO

def ths_eps_forecast(code: str) -> pd.DataFrame:
    """
    同花顺机构一致预期EPS。
    直连 basic.10jqka.com.cn，解析HTML表格。
    返回 DataFrame: 年度, 预测机构数, 最小值, 均值, 最大值
    "均值" = 机构一致预期EPS
    """
    url = f'https://basic.10jqka.com.cn/new/{code}/worth.html'
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36', 'Referer': 'https://basic.10jqka.com.cn/'}
    r = requests.get(url, headers=headers, timeout=15)
    r.encoding = 'gbk'
    dfs = pd.read_html(StringIO(r.text))
    for df in dfs:
        cols = [str(c) for c in df.columns]
        if any(('每股收益' in c or '均值' in c for c in cols)):
            return df
    return dfs[0] if dfs else pd.DataFrame()
import os
import secrets
IWENCAI_BASE = os.environ.get('IWENCAI_BASE_URL', 'https://openapi.iwencai.com')
IWENCAI_KEY = os.environ.get('IWENCAI_API_KEY', '')

def _claw_headers(call_type: str='normal') -> dict:
    """SkillHub 2.0 必须的 X-Claw 鉴权头"""
    return {'X-Claw-Call-Type': call_type, 'X-Claw-Skill-Id': 'report-search', 'X-Claw-Skill-Version': '2.0.0', 'X-Claw-Plugin-Id': 'none', 'X-Claw-Plugin-Version': 'none', 'X-Claw-Trace-Id': secrets.token_hex(32)}

def iwencai_search(query: str, channel: str='report', size: int=50) -> list[dict]:
    """
    iwencai 语义搜索。
    channel: "report"(研报) / "announcement"(公告) / "news"(新闻)
    size: 默认10, 实测可调到50（隐藏参数）
    """
    headers = {'Authorization': f'Bearer {IWENCAI_KEY}', 'Content-Type': 'application/json', **_claw_headers()}
    payload = {'channels': [channel], 'app_id': 'AIME_SKILL', 'query': query, 'size': size}
    r = requests.post(f'{IWENCAI_BASE}/v1/comprehensive/search', json=payload, headers=headers, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f'iwencai HTTP {r.status_code}: {r.text[:200]}')
    data = r.json()
    if data.get('status_code', 0) != 0:
        raise RuntimeError(f"iwencai error: {data.get('status_msg', '')}")
    return data.get('data') or []

def iwencai_query(query: str, page: int=1, limit: int=50) -> list[dict]:
    """
    iwencai NL数据查询（结构化字段）。
    例: "贵州茅台 ROE" → DataFrame-like rows
    """
    headers = {'Authorization': f'Bearer {IWENCAI_KEY}', 'Content-Type': 'application/json', **_claw_headers()}
    payload = {'query': query, 'page': str(page), 'limit': str(limit), 'is_cache': '1', 'expand_index': 'true'}
    r = requests.post(f'{IWENCAI_BASE}/v1/query2data', json=payload, headers=headers, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f'iwencai HTTP {r.status_code}: {r.text[:200]}')
    data = r.json()
    if data.get('status_code', 0) != 0:
        raise RuntimeError(f"iwencai error: {data.get('status_msg', '')}")
    return data.get('datas') or []

def dedup_articles(articles: list[dict]) -> list[dict]:
    """同一uid仅保留score最高的段落"""
    best = {}
    for a in articles:
        uid = a.get('uid', '') or f"{a.get('title', '')}|{a.get('publish_date', '')}"
        score = float(a.get('score', 0))
        if uid not in best or score > float(best[uid].get('score', 0)):
            best[uid] = a
    return sorted(best.values(), key=lambda x: x.get('publish_date', ''), reverse=True)
