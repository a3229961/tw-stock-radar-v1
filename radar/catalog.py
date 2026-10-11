"""Export a compact, searchable stock catalog separate from the Top-50 report.

Ranking covers stocks with validated 80-bar history on the latest market day.
Unranked directory entries explicitly record why they are not in the ranking.
"""
from __future__ import annotations

import pandas as pd

PUBLIC_COLUMNS = (
    "date market code name open high low close volume turnover "
    "ma5 ma10 ma20 ma60 slope5 slope10 slope20 slope60 "
    "bias20 position20 position60 volume_ratio rsi14 macd macd_signal macd_hist "
    "adx14 plus_di minus_di higher_low range_contraction breakout20 "
    "tech_score score_delta1 score_delta3 score_delta5 bars "
    "branch_score branch_status branch_net5 branch_net20 "
    "branch_wave_branches branch_overnight_risk"
).split()


def _safe_records(frame, columns):
    if frame.empty:
        return []
    found = [col for col in columns if col in frame.columns]
    copy = frame.loc[:, found].copy().astype(object)
    copy = copy.where(pd.notna(copy), None)
    return copy.to_dict("records")


def build_catalog(prices, ranking, latest):
    """Build results without treating a Top-50 cutoff as missing stock data."""
    ranked = _safe_records(ranking, PUBLIC_COLUMNS)
    missing = []
    if not prices.empty:
        latest_rows = prices.sort_values("date").groupby(
            ["market", "code"], sort=False
        ).tail(1)
        bars = prices.groupby(["market", "code"]).size().to_dict()
        ranked_keys = {(str(s["market"]), str(s["code"])) for s in ranked}
        for r in latest_rows.itertuples(index=False):
            key = (str(r.market), str(r.code))
            if key in ranked_keys:
                continue
            count = int(bars.get(key, 0))
            missing.append({
                "market": str(r.market),
                "code": str(r.code),
                "name": str(r.name) if pd.notna(r.name) else "",
                "last_data_date": str(r.date),
                "close": float(r.close) if pd.notna(r.close) else None,
                "bars": count,
                "status": "INSUFFICIENT_HISTORY" if count < 80 else "NOT_RANKED_ON_LATEST_DATE",
            })
    missing.sort(key=lambda x: (x["market"], x["code"]))
    return {
        "latest_data_date": latest,
        "ranked_count": len(ranked),
        "unranked_count": len(missing),
        "stocks": ranked,
        "unranked": missing,
        "notes": (
            "全名單搜尋涵蓋本資料庫中的技術排名及未入榜股票；"
            "不代表官方完整普通股名冊，且資料僅供技術研究。"
        ),
    }
