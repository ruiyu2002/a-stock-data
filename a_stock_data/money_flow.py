"""Auto-extracted from SKILL.md (V3.2.2). See money_flow.py source comments for section ids."""
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
HSGT_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/117.0.0.0 Safari/537.36', 'Host': 'data.hexin.cn', 'Referer': 'https://data.hexin.cn/'}

def hsgt_realtime() -> pd.DataFrame:
    """
    沪深股通当日实时分钟流向（含集合竞价 09:10–15:00，262 个时间点）。
    返回字段: time, hgt(沪股通累计净买入), sgt(深股通累计净买入)
    单位: 亿元
    """
    url = 'https://data.hexin.cn/market/hsgtApi/method/dayChart/'
    r = requests.get(url, headers=HSGT_HEADERS, timeout=10)
    d = r.json()
    times = d.get('time', [])
    hgt = d.get('hgt', [])
    sgt = d.get('sgt', [])
    n = len(times)
    return pd.DataFrame({'time': times, 'hgt_yi': hgt[:n] + [None] * (n - len(hgt)), 'sgt_yi': sgt[:n] + [None] * (n - len(sgt))})

def _northbound_cache_path() -> Path:
    """北向资金本地 CSV 缓存路径"""
    p = Path.home() / '.tradingagents' / 'cache' / 'northbound_daily.csv'
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def _save_northbound_snapshot(date: str, hgt: float, sgt: float):
    """写入/更新当天北向收盘数据到 CSV"""
    path = _northbound_cache_path()
    rows = {}
    if path.exists():
        for line in path.read_text().strip().split('\n')[1:]:
            parts = line.split(',')
            if len(parts) == 3:
                rows[parts[0]] = line
    rows[date] = f'{date},{hgt},{sgt}'
    with open(path, 'w') as f:
        f.write('date,hgt,sgt\n')
        for d in sorted(rows.keys()):
            f.write(rows[d] + '\n')

def _load_northbound_history(n: int=20) -> pd.DataFrame:
    """读取最近 N 天北向历史"""
    path = _northbound_cache_path()
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    return df.tail(n)

def eastmoney_fund_flow_minute(code: str) -> list[dict]:
    """
    个股资金流向（分钟级，当日盘中）。
    code: 6位股票代码
    返回: [{time, main_net, small_net, mid_net, large_net, super_net}, ...]
    单位: 元
    """
    secid = f'1.{code}' if code.startswith('6') else f'0.{code}'
    url = 'https://push2.eastmoney.com/api/qt/stock/fflow/kline/get'
    params = {'secid': secid, 'klt': 1, 'fields1': 'f1,f2,f3,f7', 'fields2': 'f51,f52,f53,f54,f55,f56,f57'}
    headers = {'User-Agent': UA, 'Referer': 'https://quote.eastmoney.com/', 'Origin': 'https://quote.eastmoney.com'}
    try:
        r = em_get(url, params=params, headers=headers, timeout=10)
        d = r.json()
    except Exception as e:
        print(f'[WARN] push2 资金流请求失败: {e}')
        return []
    rows = []
    for line in d.get('data', {}).get('klines', []):
        parts = line.split(',')
        if len(parts) >= 6:
            rows.append({'time': parts[0], 'main_net': float(parts[1]), 'small_net': float(parts[2]), 'mid_net': float(parts[3]), 'large_net': float(parts[4]), 'super_net': float(parts[5])})
    return rows

def margin_trading(code: str, page_size: int=30) -> list[dict]:
    """
    融资融券明细（日级）。
    返回: [{date, rzye(融资余额), rzmre(融资买入), rqye(融券余额), ...}]
    """
    data = eastmoney_datacenter('RPTA_WEB_RZRQ_GGMX', filter_str=f'(SCODE="{code}")', page_size=page_size, sort_columns='DATE', sort_types='-1')
    rows = []
    for row in data:
        rows.append({'date': str(row.get('DATE', ''))[:10], 'rzye': row.get('RZYE', 0), 'rzmre': row.get('RZMRE', 0), 'rzche': row.get('RZCHE', 0), 'rqye': row.get('RQYE', 0), 'rqmcl': row.get('RQMCL', 0), 'rqchl': row.get('RQCHL', 0), 'rzrqye': row.get('RZRQYE', 0)})
    return rows

def block_trade(code: str, page_size: int=20) -> list[dict]:
    """
    大宗交易记录。
    返回: [{date, price, vol, amount, buyer, seller, premium_pct}]
    """
    data = eastmoney_datacenter('RPT_DATA_BLOCKTRADE', filter_str=f'(SECURITY_CODE="{code}")', page_size=page_size, sort_columns='TRADE_DATE', sort_types='-1')
    rows = []
    for row in data:
        close = row.get('CLOSE_PRICE') or 0
        deal_price = row.get('DEAL_PRICE') or 0
        premium = (deal_price / close - 1) * 100 if close else 0
        rows.append({'date': str(row.get('TRADE_DATE', ''))[:10], 'price': deal_price, 'close': close, 'premium_pct': round(premium, 2), 'vol': row.get('DEAL_VOLUME', 0), 'amount': row.get('DEAL_AMT', 0), 'buyer': row.get('BUYER_NAME', ''), 'seller': row.get('SELLER_NAME', '')})
    return rows

def holder_num_change(code: str, page_size: int=10) -> list[dict]:
    """
    股东户数变化（季度级）。
    返回: [{date, holder_num, change_num, change_ratio, avg_shares}]
    """
    data = eastmoney_datacenter('RPT_HOLDERNUMLATEST', filter_str=f'(SECURITY_CODE="{code}")', page_size=page_size, sort_columns='END_DATE', sort_types='-1')
    rows = []
    for row in data:
        rows.append({'date': str(row.get('END_DATE', ''))[:10], 'holder_num': row.get('HOLDER_NUM', 0), 'change_num': row.get('HOLDER_NUM_CHANGE', 0), 'change_ratio': row.get('HOLDER_NUM_RATIO', 0), 'avg_shares': row.get('AVG_FREE_SHARES', 0)})
    return rows

def dividend_history(code: str, page_size: int=20) -> list[dict]:
    """
    分红送转历史。
    返回: [{date, bonus_rmb(每股派息), transfer_ratio(转增比例), bonus_ratio(送股比例)}]
    """
    data = eastmoney_datacenter('RPT_SHAREBONUS_DET', filter_str=f'(SECURITY_CODE="{code}")', page_size=page_size, sort_columns='EX_DIVIDEND_DATE', sort_types='-1')
    rows = []
    for row in data:
        rows.append({'date': str(row.get('EX_DIVIDEND_DATE', ''))[:10], 'bonus_rmb': row.get('PRETAX_BONUS_RMB', 0), 'transfer_ratio': row.get('TRANSFER_RATIO', 0), 'bonus_ratio': row.get('BONUS_RATIO', 0), 'plan': row.get('ASSIGN_PROGRESS', '')})
    return rows

def stock_fund_flow_120d(code: str) -> list[dict]:
    """
    个股资金流（日级，最近120个交易日）。
    返回: [{date, main_net(主力净流入), small_net, mid_net, large_net, super_net}]
    单位: 元
    """
    market_code = 1 if code.startswith('6') else 0
    url = 'https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get'
    params = {'secid': f'{market_code}.{code}', 'fields1': 'f1,f2,f3,f7', 'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65', 'lmt': '120'}
    headers = {'User-Agent': UA, 'Referer': 'https://quote.eastmoney.com/', 'Origin': 'https://quote.eastmoney.com'}
    try:
        r = em_get(url, params=params, headers=headers, timeout=15)
        d = r.json()
    except Exception as e:
        print(f'[WARN] push2 资金流请求失败: {e}')
        return []
    klines = d.get('data', {}).get('klines', [])
    rows = []
    for line in klines:
        parts = line.split(',')
        if len(parts) >= 7:
            rows.append({'date': parts[0], 'main_net': float(parts[1]) if parts[1] != '-' else 0, 'small_net': float(parts[2]) if parts[2] != '-' else 0, 'mid_net': float(parts[3]) if parts[3] != '-' else 0, 'large_net': float(parts[4]) if parts[4] != '-' else 0, 'super_net': float(parts[5]) if parts[5] != '-' else 0})
    return rows
