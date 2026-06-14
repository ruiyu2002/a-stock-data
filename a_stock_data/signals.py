"""Auto-extracted from SKILL.md (V3.2.2). See signals.py source comments for section ids."""
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

def ths_hot_reason(date: str=None) -> pd.DataFrame:
    """
    同花顺当日强势股归因。
    date: 'YYYY-MM-DD' 格式，None=今天
    返回 DataFrame，含每只股票的题材标签 (reason)。

    实测: 73ms 拿到 ~125 只 + 完整字段
    """
    if date is None:
        date = _date.today().strftime('%Y-%m-%d')
    url = f'http://zx.10jqka.com.cn/event/api/getharden/date/{date}/orderby/date/orderway/desc/charset/GBK/'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/117.0.0.0 Safari/537.36'}
    r = requests.get(url, headers=headers, timeout=10)
    data = r.json()
    if data.get('errocode', 0) != 0:
        raise RuntimeError(f"同花顺热点错误: {data.get('errormsg', '')}")
    rows = data.get('data') or []
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    rename_map = {'name': '名称', 'code': '代码', 'reason': '题材归因', 'close': '收盘价', 'zhangdie': '涨跌额', 'zhangfu': '涨幅%', 'huanshou': '换手率%', 'chengjiaoe': '成交额', 'chengjiaoliang': '成交量', 'ddejingliang': '大单净量', 'market': '市场'}
    df = df.rename(columns=rename_map)
    return df

def eastmoney_concept_blocks(code: str) -> dict:
    """
    个股所属板块/概念归属（东财 slist，一次请求拿全，已内置限流）。
    返回: {total, boards: [{name, code(BK码), change_pct, lead_stock}], concept_tags: [板块名...]}
    boards 混合 行业/概念/地域，板块名自解释；concept_tags 是所有板块名的便捷列表。
    """
    market_code = 1 if code.startswith('6') else 0
    params = {'fltt': '2', 'invt': '2', 'secid': f'{market_code}.{code}', 'spt': '3', 'pi': '0', 'pz': '200', 'po': '1', 'fields': 'f12,f14,f3,f128'}
    headers = {'User-Agent': UA, 'Referer': 'https://quote.eastmoney.com/'}
    try:
        r = em_get('https://push2.eastmoney.com/api/qt/slist/get', params=params, headers=headers, timeout=15)
        d = r.json()
    except Exception as e:
        print(f'[WARN] 东财板块归属请求失败: {e}')
        return {'total': 0, 'boards': [], 'concept_tags': []}
    diff = (d.get('data') or {}).get('diff') or {}
    items = diff.values() if isinstance(diff, dict) else diff
    boards = []
    for it in items:
        boards.append({'name': it.get('f14', ''), 'code': it.get('f12', ''), 'change_pct': it.get('f3', ''), 'lead_stock': it.get('f128', '')})
    return {'total': len(boards), 'boards': boards, 'concept_tags': [b['name'] for b in boards]}

def dragon_tiger_board(code: str, trade_date: str, look_back: int=30) -> dict:
    """
    龙虎榜数据聚合。
    trade_date: YYYY-MM-DD
    look_back: 回看天数
    返回: {records: [...], seats: {buy: [...], sell: [...]}, institution: {...}}
    """
    start = datetime.strptime(trade_date, '%Y-%m-%d') - timedelta(days=look_back)
    start_str = start.strftime('%Y-%m-%d')
    records = []
    data = eastmoney_datacenter('RPT_DAILYBILLBOARD_DETAILSNEW', filter_str=f'''(TRADE_DATE>='{start_str}')(TRADE_DATE<='{trade_date}')(SECURITY_CODE="{code}")''', page_size=50, sort_columns='TRADE_DATE', sort_types='-1')
    for row in data:
        records.append({'date': str(row.get('TRADE_DATE', ''))[:10], 'reason': row.get('EXPLANATION', ''), 'net_buy': round((row.get('BILLBOARD_NET_AMT') or 0) / 10000, 1), 'turnover': round(float(row.get('TURNOVERRATE') or 0), 2)})
    seats = {'buy': [], 'sell': []}
    if records:
        latest_date = records[0]['date']
        buy_data = eastmoney_datacenter('RPT_BILLBOARD_DAILYDETAILSBUY', filter_str=f'''(TRADE_DATE='{latest_date}')(SECURITY_CODE="{code}")''', page_size=10, sort_columns='BUY', sort_types='-1')
        for row in buy_data[:5]:
            seats['buy'].append({'name': row.get('OPERATEDEPT_NAME', ''), 'buy_amt': round((row.get('BUY') or 0) / 10000, 1), 'sell_amt': round((row.get('SELL') or 0) / 10000, 1), 'net': round((row.get('NET') or 0) / 10000, 1)})
        sell_data = eastmoney_datacenter('RPT_BILLBOARD_DAILYDETAILSSELL', filter_str=f'''(TRADE_DATE='{latest_date}')(SECURITY_CODE="{code}")''', page_size=10, sort_columns='SELL', sort_types='-1')
        for row in sell_data[:5]:
            seats['sell'].append({'name': row.get('OPERATEDEPT_NAME', ''), 'buy_amt': round((row.get('BUY') or 0) / 10000, 1), 'sell_amt': round((row.get('SELL') or 0) / 10000, 1), 'net': round((row.get('NET') or 0) / 10000, 1)})
    institution = {'buy_amt': 0, 'sell_amt': 0, 'net_amt': 0}
    for detail_data, side in [(buy_data, 'buy'), (sell_data, 'sell')]:
        for row in detail_data:
            if str(row.get('OPERATEDEPT_CODE', '')) == '0':
                amt = row.get('BUY') or 0 if side == 'buy' else row.get('SELL') or 0
                if side == 'buy':
                    institution['buy_amt'] += amt
                else:
                    institution['sell_amt'] += amt
    institution['buy_amt'] = round(institution['buy_amt'] / 10000, 1)
    institution['sell_amt'] = round(institution['sell_amt'] / 10000, 1)
    institution['net_amt'] = round(institution['buy_amt'] - institution['sell_amt'], 1)
    return {'records': records, 'seats': seats, 'institution': institution}

def lockup_expiry(code: str, trade_date: str, forward_days: int=90) -> dict:
    """
    限售解禁日历。
    返回: {history: [...], upcoming: [...]}
    """
    history_data = eastmoney_datacenter('RPT_LIFT_STAGE', filter_str=f'(SECURITY_CODE="{code}")', page_size=15, sort_columns='FREE_DATE', sort_types='-1')
    history = []
    for row in history_data:
        history.append({'date': str(row.get('FREE_DATE', ''))[:10], 'type': row.get('LIMITED_STOCK_TYPE', ''), 'shares': row.get('FREE_SHARES_NUM', 0), 'ratio': row.get('FREE_RATIO', 0)})
    end_date = datetime.strptime(trade_date, '%Y-%m-%d') + timedelta(days=forward_days)
    end_str = end_date.strftime('%Y-%m-%d')
    upcoming_data = eastmoney_datacenter('RPT_LIFT_STAGE', filter_str=f"""(SECURITY_CODE="{code}")(FREE_DATE>='{trade_date}')(FREE_DATE<='{end_str}')""", page_size=20, sort_columns='FREE_DATE', sort_types='1')
    upcoming = []
    for row in upcoming_data:
        upcoming.append({'date': str(row.get('FREE_DATE', ''))[:10], 'type': row.get('LIMITED_STOCK_TYPE', ''), 'shares': row.get('FREE_SHARES_NUM', 0), 'ratio': row.get('FREE_RATIO', 0)})
    return {'history': history, 'upcoming': upcoming}

def industry_comparison(top_n: int=20) -> dict:
    """
    全行业涨跌幅排名（东财行业板块，~100 个行业）。
    返回: {top: [...], bottom: [...], total: int}
    """
    url = 'https://push2.eastmoney.com/api/qt/clist/get'
    params = {'pn': '1', 'pz': '100', 'po': '1', 'np': '1', 'fltt': '2', 'invt': '2', 'fs': 'm:90+t:2', 'fields': 'f2,f3,f4,f12,f13,f14,f104,f105,f128,f136,f140,f141,f207'}
    headers = {'User-Agent': UA}
    r = em_get(url, params=params, headers=headers, timeout=15)
    d = r.json()
    items = d.get('data', {}).get('diff', [])
    if not items:
        return {'top': [], 'bottom': [], 'total': 0}
    rows = []
    for i, item in enumerate(items):
        rows.append({'rank': i + 1, 'name': item.get('f14', ''), 'change_pct': item.get('f3', 0), 'code': item.get('f12', ''), 'up_count': item.get('f104', 0), 'down_count': item.get('f105', 0), 'leader': item.get('f140', ''), 'leader_change': item.get('f136', 0)})
    return {'top': rows[:top_n], 'bottom': rows[-top_n:], 'total': len(rows)}

def daily_dragon_tiger(trade_date: str=None, min_net_buy: float=None) -> dict:
    """
    全市场龙虎榜。
    trade_date: YYYY-MM-DD（默认当日）
    min_net_buy: 净买入下限（万元），None 不过滤
    返回: {date, total_records, stocks: [{code, name, reason, close, change_pct,
           net_buy_wan, buy_wan, sell_wan, turnover_pct}]}
    """
    if trade_date is None:
        trade_date = datetime.now().strftime('%Y-%m-%d')
    data = eastmoney_datacenter('RPT_DAILYBILLBOARD_DETAILSNEW', filter_str=f"(TRADE_DATE>='{trade_date}')(TRADE_DATE<='{trade_date}')", page_size=500, sort_columns='BILLBOARD_NET_AMT', sort_types='-1')
    if not data:
        return {'date': trade_date, 'total_records': 0, 'stocks': [], 'note': '无数据（非交易日或盘后未更新）'}
    actual_date = str(data[0].get('TRADE_DATE', ''))[:10] if data else trade_date
    stocks = []
    for row in data:
        net_buy = (row.get('BILLBOARD_NET_AMT') or 0) / 10000
        if min_net_buy is not None and net_buy < min_net_buy:
            continue
        stocks.append({'code': row.get('SECURITY_CODE', ''), 'name': row.get('SECURITY_NAME_ABBR', ''), 'reason': row.get('EXPLANATION', ''), 'close': row.get('CLOSE_PRICE') or 0, 'change_pct': round(float(row.get('CHANGE_RATE') or 0), 2), 'net_buy_wan': round(net_buy, 1), 'buy_wan': round((row.get('BILLBOARD_BUY_AMT') or 0) / 10000, 1), 'sell_wan': round((row.get('BILLBOARD_SELL_AMT') or 0) / 10000, 1), 'turnover_pct': round(float(row.get('TURNOVERRATE') or 0), 2)})
    return {'date': actual_date, 'total_records': len(stocks), 'stocks': stocks}
