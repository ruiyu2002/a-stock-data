"""Auto-extracted from SKILL.md (V3.2.2). See fundamentals.py source comments for section ids."""
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
from mootdx.quotes import Quotes
from mootdx.quotes import Quotes

def eastmoney_stock_info(code: str) -> dict:
    """
    东财个股基本面信息。
    返回: {code, name, industry, total_shares, float_shares, mcap, float_mcap, list_date}
    """
    market_code = 1 if code.startswith('6') else 0
    url = 'https://push2.eastmoney.com/api/qt/stock/get'
    params = {'fltt': '2', 'invt': '2', 'fields': 'f57,f58,f84,f85,f127,f116,f117,f189,f43', 'secid': f'{market_code}.{code}'}
    headers = {'User-Agent': UA}
    r = em_get(url, params=params, headers=headers, timeout=10)
    d = r.json().get('data', {})
    return {'code': d.get('f57', ''), 'name': d.get('f58', ''), 'industry': d.get('f127', ''), 'total_shares': d.get('f84', 0), 'float_shares': d.get('f85', 0), 'mcap': d.get('f116', 0), 'float_mcap': d.get('f117', 0), 'list_date': str(d.get('f189', '')), 'price': d.get('f43', 0)}

def sina_financial_report(code: str, report_type: str='lrb', num: int=8) -> list[dict]:
    """
    新浪财报三表。
    code: 6位代码
    report_type: "fzb"(资产负债表) / "lrb"(利润表) / "llb"(现金流量表)
    num: 取最近 N 期（默认 8 期）
    返回: 按报告期倒序的记录列表，每期一条 dict：
          {"报告期": "2026-03-31", "<科目>": "<值>", "<科目>_同比": <同比>, ...}
          （item_value 为新浪原始字符串数值，仅在有同比时附 "_同比" 键）
    """
    prefix = 'sh' if code.startswith('6') else 'sz'
    paper_code = f'{prefix}{code}'
    url = 'https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022'
    params = {'paperCode': paper_code, 'source': report_type, 'type': '0', 'page': '1', 'num': str(num)}
    headers = {'User-Agent': UA}
    r = requests.get(url, params=params, headers=headers, timeout=15)
    report_list = r.json().get('result', {}).get('data', {}).get('report_list', {}) or {}
    rows = []
    for period in sorted(report_list.keys(), reverse=True)[:num]:
        obj = report_list[period]
        rec = {'报告期': f'{period[:4]}-{period[4:6]}-{period[6:8]}'}
        for it in obj.get('data', []) or []:
            title = it.get('item_title', '')
            if not title or it.get('item_value') is None:
                continue
            rec[title] = it.get('item_value')
            tongbi = it.get('item_tongbi')
            if tongbi not in (None, ''):
                rec[title + '_同比'] = tongbi
        rows.append(rec)
    return rows

def forward_pe(price: float, eps_forecast: float) -> float:
    """前向PE = 当前股价 / 未来年度一致预期EPS"""
    if eps_forecast <= 0:
        return float('inf')
    return price / eps_forecast
import math

def pe_digestion(current_pe: float, cagr: float, target_pe: float=30) -> float:
    """
    当前PE消化到目标PE需要多少年。
    target_pe 固定30x（A股成长股合理估值锚点）。
    cagr: 用 下一年EPS / 当年EPS - 1
    """
    if current_pe <= target_pe:
        return 0.0
    if cagr <= 0:
        return float('inf')
    return math.log(current_pe / target_pe) / math.log(1 + cagr)

def calc_peg(pe: float, cagr: float) -> float:
    """
    PEG = 前向PE / (CAGR * 100)
    PEG < 1   → 便宜
    PEG 1-1.5 → 合理
    PEG > 1.5 → 贵
    """
    if cagr <= 0:
        return float('inf')
    return pe / (cagr * 100)
import math

def full_valuation(code: str) -> dict:
    """单票完整估值分析"""
    prefix = 'sh' if code.startswith(('6', '9')) else 'bj' if code.startswith('8') else 'sz'
    url = f'https://qt.gtimg.cn/q={prefix}{code}'
    req = urllib.request.Request(url)
    req.add_header('User-Agent', 'Mozilla/5.0')
    resp = urllib.request.urlopen(req, timeout=10)
    data = resp.read().decode('gbk')
    vals = data.split('"')[1].split('~')
    price = float(vals[3])
    mcap = float(vals[44])
    pe_ttm = float(vals[39]) if vals[39] else 0
    pb = float(vals[46]) if vals[46] else 0
    df = ths_eps_forecast(code)
    eps_cur = eps_next = None
    analyst_count = 0
    if not df.empty and len(df.columns) >= 3:
        try:
            for i, row in df.iterrows():
                if i == 0:
                    eps_cur = float(row.iloc[2]) if pd.notna(row.iloc[2]) else None
                    analyst_count = int(row.iloc[1]) if pd.notna(row.iloc[1]) else 0
                elif i == 1:
                    eps_next = float(row.iloc[2]) if pd.notna(row.iloc[2]) else None
        except (ValueError, IndexError):
            pass
    pe_fwd = price / eps_cur if eps_cur else float('inf')
    cagr = eps_next / eps_cur - 1 if eps_cur and eps_next else 0
    peg = pe_fwd / (cagr * 100) if cagr > 0 else float('inf')
    digest = math.log(pe_fwd / 30) / math.log(1 + cagr) if pe_fwd > 30 and cagr > 0 else 0
    return {'name': vals[1], 'price': price, 'mcap_yi': mcap, 'pe_ttm': pe_ttm, 'pb': pb, 'eps_cur': eps_cur, 'eps_next': eps_next, 'pe_fwd': round(pe_fwd, 1) if eps_cur else None, 'cagr_pct': round(cagr * 100, 0) if cagr else None, 'peg': round(peg, 2) if peg != float('inf') else None, 'digest_years': round(digest, 1), 'analyst_count': analyst_count}

def mootdx_finance_snapshot(ticker: str):
    """mootdx 财务快照（37 字段季报数据）— eps/roe/profit/income 等。"""
    from mootdx.financial import Financial
    client = Financial(market='std')
    return client.fetch(symbol=_norm(ticker))

def mootdx_f10_text(ticker: str):
    """mootdx F10 公司文本资料（9 大类）。"""
    from mootdx.affair import Affair
    return Affair.fetch(symbol=_norm(ticker))
