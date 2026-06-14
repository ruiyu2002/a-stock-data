"""a_stock_data — A 股全栈数据工具包.

Forked from simonlin1212/a-stock-data (Apache 2.0), repackaged as a Python module.
Original SKILL.md (V3.2.2) extracted into modules by topic.
"""

__version__ = "3.2.2.post0"

from a_stock_data.announcements import cninfo_announcements, mootdx_f10_announcements
from a_stock_data.fundamentals import eastmoney_stock_info, sina_financial_report, forward_pe, pe_digestion, calc_peg, full_valuation, mootdx_finance_snapshot, mootdx_f10_text
from a_stock_data.kline import tencent_quote, baidu_kline_with_ma, mootdx_kline, mootdx_quote, mootdx_transaction
from a_stock_data.money_flow import hsgt_realtime, eastmoney_fund_flow_minute, margin_trading, block_trade, holder_num_change, dividend_history, stock_fund_flow_120d
from a_stock_data.news import eastmoney_stock_news, cls_telegraph, eastmoney_global_news
from a_stock_data.research import eastmoney_reports, download_pdf, ths_eps_forecast, iwencai_search, iwencai_query, dedup_articles
from a_stock_data.signals import ths_hot_reason, eastmoney_concept_blocks, dragon_tiger_board, lockup_expiry, industry_comparison, daily_dragon_tiger
from a_stock_data._helpers import get_prefix, em_get, eastmoney_datacenter

__all__ = [
    "cninfo_announcements",
    "mootdx_f10_announcements",
    "eastmoney_stock_info",
    "sina_financial_report",
    "forward_pe",
    "pe_digestion",
    "calc_peg",
    "full_valuation",
    "mootdx_finance_snapshot",
    "mootdx_f10_text",
    "tencent_quote",
    "baidu_kline_with_ma",
    "mootdx_kline",
    "mootdx_quote",
    "mootdx_transaction",
    "hsgt_realtime",
    "eastmoney_fund_flow_minute",
    "margin_trading",
    "block_trade",
    "holder_num_change",
    "dividend_history",
    "stock_fund_flow_120d",
    "eastmoney_stock_news",
    "cls_telegraph",
    "eastmoney_global_news",
    "eastmoney_reports",
    "download_pdf",
    "ths_eps_forecast",
    "iwencai_search",
    "iwencai_query",
    "dedup_articles",
    "ths_hot_reason",
    "eastmoney_concept_blocks",
    "dragon_tiger_board",
    "lockup_expiry",
    "industry_comparison",
    "daily_dragon_tiger",
    "get_prefix",
    "em_get",
    "eastmoney_datacenter",
]
