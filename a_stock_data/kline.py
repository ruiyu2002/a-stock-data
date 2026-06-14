"""Auto-extracted from SKILL.md (V3.2.2). See kline.py source comments for section ids."""
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

def tencent_quote(codes: list[str]) -> dict[str, dict]:
    """
    批量拉取腾讯财经实时行情。
    codes: ["688017", "300476", "002463"]
    也支持指数: ["000001", "000300", "399006"]
    也支持ETF: ["510050", "510300"]
    返回: {code: {name, price, pe_ttm, pb, mcap, ...}}
    """
    prefixed = []
    for c in codes:
        if c.startswith(('6', '9')):
            prefixed.append(f'sh{c}')
        elif c.startswith('8'):
            prefixed.append(f'bj{c}')
        else:
            prefixed.append(f'sz{c}')
    url = 'https://qt.gtimg.cn/q=' + ','.join(prefixed)
    req = urllib.request.Request(url)
    req.add_header('User-Agent', 'Mozilla/5.0')
    resp = urllib.request.urlopen(req, timeout=10)
    data = resp.read().decode('gbk')
    result = {}
    for line in data.strip().split(';'):
        if not line.strip() or '=' not in line or '"' not in line:
            continue
        key = line.split('=')[0].split('_')[-1]
        vals = line.split('"')[1].split('~')
        if len(vals) < 53:
            continue
        code = key[2:]
        result[code] = {'name': vals[1], 'price': float(vals[3]) if vals[3] else 0, 'last_close': float(vals[4]) if vals[4] else 0, 'open': float(vals[5]) if vals[5] else 0, 'change_amt': float(vals[31]) if vals[31] else 0, 'change_pct': float(vals[32]) if vals[32] else 0, 'high': float(vals[33]) if vals[33] else 0, 'low': float(vals[34]) if vals[34] else 0, 'amount_wan': float(vals[37]) if vals[37] else 0, 'turnover_pct': float(vals[38]) if vals[38] else 0, 'pe_ttm': float(vals[39]) if vals[39] else 0, 'amplitude_pct': float(vals[43]) if vals[43] else 0, 'mcap_yi': float(vals[44]) if vals[44] else 0, 'float_mcap_yi': float(vals[45]) if vals[45] else 0, 'pb': float(vals[46]) if vals[46] else 0, 'limit_up': float(vals[47]) if vals[47] else 0, 'limit_down': float(vals[48]) if vals[48] else 0, 'vol_ratio': float(vals[49]) if vals[49] else 0, 'pe_static': float(vals[52]) if vals[52] else 0}
    return result

def baidu_kline_with_ma(code: str, start_time: str='') -> dict:
    """百度股市通K线 — 独有能力: 返回时自带 ma5/ma10/ma20 均价"""
    url = 'https://finance.pae.baidu.com/selfselect/getstockquotation'
    params = {'all': '1', 'isIndex': 'false', 'isBk': 'false', 'isBlock': 'false', 'isFutures': 'false', 'isStock': 'true', 'newFormat': '1', 'group': 'quotation_kline_ab', 'finClientType': 'pc', 'code': code, 'start_time': start_time, 'ktype': '1'}
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/vnd.finance-web.v1+json', 'Origin': 'https://gushitong.baidu.com', 'Referer': 'https://gushitong.baidu.com/'}
    r = requests.get(url, params=params, headers=headers, timeout=10)
    d = r.json()
    result = d.get('Result', {})
    md = result.get('newMarketData', {})
    keys = md.get('keys', [])
    rows = md.get('marketData', '').split(';')
    return {'keys': keys, 'rows': rows}

def mootdx_kline(ticker: str, category: int=4, offset: int=60):
    """K 线 / 周线 / 月线（mootdx，通达信 TCP）。

    category: 4=日线, 5=周线, 6=月线, 7=1分钟, 8=5分钟, 9=15分钟, 10=30分钟, 11=60分钟
    返回 DataFrame: open, close, high, low, vol, amount, datetime
    """
    from mootdx.quotes import Quotes
    client = Quotes.factory(market='std')
    return client.bars(symbol=_norm(ticker), category=category, offset=offset)

def mootdx_quote(tickers: list[str]):
    """实时五档报价 + 现价 / 涨跌停 / 昨收（mootdx）。"""
    from mootdx.quotes import Quotes
    client = Quotes.factory(market='std')
    return client.quotes(symbol=[_norm(t) for t in tickers])

def mootdx_transaction(ticker: str, date: str):
    """指定日期逐笔成交（mootdx）。date 形如 '20260502'。非交易时间返回空。"""
    from mootdx.quotes import Quotes
    client = Quotes.factory(market='std')
    return client.transaction(symbol=_norm(ticker), date=date)
