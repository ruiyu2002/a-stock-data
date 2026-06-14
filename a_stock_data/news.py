"""Auto-extracted from SKILL.md (V3.2.2). See news.py source comments for section ids."""
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

def eastmoney_stock_news(code: str, page_size: int=20) -> list[dict]:
    """
    东财个股新闻（JSONP 接口）。
    返回: [{title, content, time, source, url}]
    """
    cb = 'jQuery_news'
    url = 'https://search-api-web.eastmoney.com/search/jsonp'
    inner_params = json.dumps({'uid': '', 'keyword': code, 'type': ['cmsArticleWebOld'], 'client': 'web', 'clientType': 'web', 'clientVersion': 'curr', 'param': {'cmsArticleWebOld': {'searchScope': 'default', 'sort': 'default', 'pageIndex': 1, 'pageSize': page_size, 'preTag': '', 'postTag': ''}}}, separators=(',', ':'))
    params = {'cb': cb, 'param': inner_params}
    headers = {'User-Agent': UA, 'Referer': 'https://so.eastmoney.com/'}
    r = em_get(url, params=params, headers=headers, timeout=15)
    text = r.text
    json_str = text[text.index('(') + 1:text.rindex(')')]
    d = json.loads(json_str)
    rows = []
    articles = d.get('result', {}).get('cmsArticleWebOld', []) or []
    for a in articles:
        rows.append({'title': re.sub('<[^>]+>', '', a.get('title', '')), 'content': re.sub('<[^>]+>', '', a.get('content', ''))[:200], 'time': a.get('date', ''), 'source': a.get('mediaName', ''), 'url': a.get('url', '')})
    return rows

def cls_telegraph(page_size: int=50) -> list[dict]:
    """
    财联社电报（全市场实时快讯）。
    返回: [{title, content, time}]
    """
    url = 'https://www.cls.cn/nodeapi/telegraphList'
    params = {'rn': str(page_size), 'page': '1'}
    headers = {'User-Agent': UA, 'Referer': 'https://www.cls.cn/'}
    r = requests.get(url, params=params, headers=headers, timeout=10)
    d = r.json()
    rows = []
    for item in d.get('data', {}).get('roll_data', []):
        rows.append({'title': item.get('title', '') or item.get('brief', ''), 'content': item.get('content', '') or item.get('brief', ''), 'time': item.get('ctime', '')})
    return rows
import uuid

def eastmoney_global_news(page_size: int=50) -> list[dict]:
    """
    东方财富全球财经资讯（7x24 滚动）。
    返回: [{title, summary, time}]
    """
    url = 'https://np-weblist.eastmoney.com/comm/web/getFastNewsList'
    params = {'client': 'web', 'biz': 'web_724', 'fastColumn': '102', 'sortEnd': '', 'pageSize': str(page_size), 'req_trace': str(uuid.uuid4())}
    headers = {'User-Agent': UA, 'Referer': 'https://kuaixun.eastmoney.com/'}
    r = em_get(url, params=params, headers=headers, timeout=10)
    d = r.json()
    rows = []
    for item in d.get('data', {}).get('fastNewsList', []):
        rows.append({'title': item.get('title', ''), 'summary': item.get('summary', '')[:200], 'time': item.get('showTime', '')})
    return rows
