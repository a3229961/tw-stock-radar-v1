"""Publish OHLCV-only early-rally shortlist, overheat list and chart shards.

This is *not* branch/beneficial-owner confirmation. Signal thresholds are
heuristics and have not been backtested. No position or return is assumed.
"""
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

SIGNAL_PRIORITY = {"START": 0, "EARLY": 1, "FOLLOW": 2, "WATCH": 3, "HOT": 4}
FIELDS = (
    "date market code name close volume turnover tech_score impulse_signal "
    "impulse_label impulse_strength impulse_age_bars impulse_last_event_date "
    "impulse_recent_events impulse_return1_pct impulse_return5_pct "
    "impulse_volume_ratio impulse_breakout10 impulse_breakout20 "
    "impulse_risk_flags impulse_reason rsi14 bias20 ma5 ma20"
).split()
DISPLAY = {
    "date": "行情日期", "market": "市場", "code": "代號", "name": "股票名稱",
    "close": "收盤價", "tech_score": "技術分數", "impulse_signal": "型態階段",
    "impulse_strength": "拉抬型態強度", "impulse_age_bars": "距上次啟動交易日",
    "impulse_last_event_date": "上次啟動日期", "impulse_volume_ratio": "成交量比",
    "impulse_return5_pct": "五日漲幅%", "rsi14": "RSI14", "bias20": "20日乖離%",
    "impulse_risk_flags": "過熱原因",
}


def _safe_records(frame, columns):
    if frame.empty:
        return []
    subset = frame[[col for col in columns if col in frame.columns]].copy()
    return subset.astype(object).where(pd.notna(subset), None).to_dict("records")


def select_impulse_stocks(ranking, limit=80):
    if ranking.empty:
        return pd.DataFrame(), pd.DataFrame()
    ordered = ranking.copy()
    ordered = ordered.loc[ordered.impulse_signal.isin(SIGNAL_PRIORITY)].copy()
    ordered["_priority"] = ordered.impulse_signal.map(SIGNAL_PRIORITY)
    ordered["_age"] = pd.to_numeric(ordered.impulse_age_bars, errors="coerce").fillna(999)
    ordered = ordered.sort_values(
        ["_priority", "_age", "impulse_strength", "turnover"],
        ascending=[True, True, False, False], na_position="last",
    )
    safe = ordered.loc[ordered.impulse_signal != "HOT"].drop(columns=["_priority", "_age"])
    hot = ordered.loc[ordered.impulse_signal == "HOT"].drop(columns=["_priority", "_age"])
    return safe.head(limit), hot.head(limit)


def market_impulse_summary(ranking, latest):
    if ranking.empty:
        return {
            "latest_data_date": latest, "new_start_count": 0, "new_early_count": 0,
            "follow_count": 0, "watch_count": 0, "hot_count": 0,
            "recent_3bar_events": 0, "eligible": 0,
        }
    types = ranking.impulse_signal.value_counts()
    age = pd.to_numeric(ranking.impulse_age_bars, errors="coerce")
    return {
        "latest_data_date": latest,
        "new_start_count": int(types.get("START", 0)),
        "new_early_count": int(types.get("EARLY", 0)),
        "follow_count": int(types.get("FOLLOW", 0)),
        "watch_count": int(types.get("WATCH", 0)),
        "hot_count": int(types.get("HOT", 0)),
        "recent_3bar_events": int(age.between(0, 2).sum()),
        "eligible": int(len(ranking)),
        "method": "OHLCV_PV_IMPULSE_HEURISTIC_V1",
        "branch_verified": False,
    }


def publish_impulse(docsdir, ranking, history, latest):
    """Export compact summary + sharded on-demand candlestick data."""
    docsdir = Path(docsdir)
    docsdir.mkdir(parents=True, exist_ok=True)
    info = market_impulse_summary(ranking, latest)
    shortlist, overheated = select_impulse_stocks(ranking)
    payload = {
        "summary": info,
        "candidates": _safe_records(shortlist, FIELDS),
        "overheated": _safe_records(overheated, FIELDS),
        "notices": [
            "本模型以每日OHLCV推估疑似資金推升，無法辨識實際券商帳戶或認定主力進場。",
            "啟動/延續/過熱為啟發式分類，尚未完成樣本外回測或分點交叉驗證。",
            "收盤後才可確認當日訊號，不能假設能在同一根K線低點成交。",
        ],
    }
    (docsdir / "impulse.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str,
                   allow_nan=False), encoding="utf-8")
    # Split 60–65 bar per-stock charts by market and first symbol digit.
    # Browser loads exactly one relevant shard when user selects any stock.
    history_dir = docsdir / "charts"
    history_dir.mkdir(parents=True, exist_ok=True)
    current = ({(str(row.market), str(row.code))
                for row in ranking[["market", "code"]].itertuples(index=False)}
               if not ranking.empty else set())
    groups = defaultdict(dict)
    for key, candles in history.items():
        market, code = key.split("-", 1)
        if (market, code) not in current:
            continue
        if len(code) != 4 or not code.isdigit() or market not in ("TWSE", "TPEX"):
            continue
        groups[f"{market}-{code[0]}"][code] = candles
    files = []
    for shard, payload in sorted(groups.items()):
        path = history_dir / f"{shard}.json"
        path.write_text(json.dumps(
            {"latest_data_date": latest,
             "chart_columns": ["date", "open", "high", "low", "close", "volume",
                               "ma5", "ma20", "signal", "is_new_trigger", "volume_ratio"],
             "stocks": payload},
            ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ), encoding="utf-8")
        files.append(shard)
    return info, shortlist, overheated, files


def impulse_excel_view(frame, empty_text):
    if frame.empty:
        return pd.DataFrame({"狀態": [empty_text]})
    chosen = [c for c in DISPLAY if c in frame.columns]
    return frame[chosen].rename(columns=DISPLAY).copy()
