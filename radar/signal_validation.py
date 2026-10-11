"""Point-in-time descriptive validation for public daily price-volume signals.

These figures are NOT a trading backtest or win-rate claim:
- Signal classification only uses prior/on-day observations in pump_signals.
- For an event on t, entry proxy is the *next market session OPEN* (t+1).
- Exit proxy is the market session CLOSE on t+h, where h is 1/3/5/10.
- Require all intervening market sessions for the same stock; never silently
  turn sparse observations into false 3/5/10-day holding periods.
- Pending signals without full future sessions are excluded, not counted as
  losing signals, winning signals or zeros.
- Fees, slippage, buy availability at limit-up, dividends and splits omitted.
- Historical descriptive statistics have selection, survivorship, multiple-
  testing and recent parameter-tuning biases. Not out-of-sample.
"""
from collections import defaultdict
import math

import pandas as pd

HORIZONS = (1, 3, 5, 10)
STAGES = ("START", "EARLY", "PREP")
EVAL_VERSION = "ohlcv-validation-v1"


def market_calendar(prices):
    """Infer well-covered sessions from downloaded market-wide OHLCV rows.

    A stray one-stock date must not create a fake trading session. This is still
    only an observed trading-day calendar, not an official exchange calendar.
    """
    if prices.empty:
        return {}
    daily = prices.groupby(["market", "date"])["code"].nunique()
    result = {}
    for market in daily.index.get_level_values("market").unique():
        counts = daily.xs(market).sort_index()
        normal = max(1, math.ceil(float(counts.quantile(.75)) * .55))
        result[str(market)] = [
            str(day) for day, n in counts.items() if n >= normal
        ]
    return result


def validate_one_stock(data, sessions, market, code):
    """Return only completed events, and count how many horizons are pending."""
    if data.empty or not sessions:
        return [], {}, 0
    rows = {str(r.date): r for r in data.itertuples(index=False)}
    day_index = {day: i for i, day in enumerate(sessions)}
    observed = []
    incomplete = defaultdict(lambda: {str(h): 0 for h in HORIZONS})
    total = 0
    last_hot_date_index = -10_000
    for r in data.itertuples(index=False):
        date = str(r.date)
        i = day_index.get(date)
        if i is None:
            continue
        stage = str(r.impulse_signal)
        new_entry = bool(r.impulse_event) and stage in STAGES
        # Count a hot *episode* only once after 3 non-HOT market sessions.
        hot_episode = stage == "HOT" and i - last_hot_date_index > 3
        if stage == "HOT":
            last_hot_date_index = i
        if not (new_entry or hot_episode):
            continue
        total += 1
        for horizon in HORIZONS:
            if i + horizon >= len(sessions):
                incomplete[stage][str(horizon)] += 1
                continue
            # If even one intervening market session is missing for the stock,
            # the event cannot be evaluated at this horizon.
            window_days = sessions[i + 1:i + horizon + 1]
            window = [rows.get(d) for d in window_days]
            if any(row is None for row in window):
                incomplete[str(horizon)] += 1
                continue
            try:
                entry = float(window[0].open)
                exit_ = float(window[-1].close)
                lows = [float(row.low) for row in window]
                highs = [float(row.high) for row in window]
                if not all(math.isfinite(z) and z > 0 for z in [entry, exit_, *lows, *highs]):
                    raise ValueError("invalid price")
            except (TypeError, ValueError):
                incomplete[str(horizon)] += 1
                continue
            # Use next-session open instead of unrealistically buying the
            # signal candle's close or low after knowing its final bar.
            observed.append({
                "market": str(market), "code": str(code),
                "signal_date": date, "stage": stage,
                "horizon": int(horizon),
                "entry_date": window_days[0], "exit_date": window_days[-1],
                "entry_open": round(entry, 4),
                "exit_close": round(exit_, 4),
                "forward_return_pct": round(100 * (exit_ / entry - 1), 4),
                "max_adverse_pct": round(100 * (min(lows) / entry - 1), 4),
                "max_favorable_pct": round(100 * (max(highs) / entry - 1), 4),
            })
    return observed, dict(incomplete), total


def aggregate_validation(records, pending, total_events, as_of):
    """All stages and horizons are explicit, even when counts are zero."""
    frame = pd.DataFrame(records)
    summary = []
    total_completed = {}
    for stage in (*STAGES, "HOT"):
        stage_pending = pending.get(stage, {})
        for h in HORIZONS:
            subset = (frame.loc[(frame.stage == stage) & (frame.horizon == h)]
                      if not frame.empty else pd.DataFrame())
            returns = subset["forward_return_pct"] if not subset.empty else pd.Series(dtype=float)
            n = int(len(returns))
            def stat(fn):
                return round(float(fn(returns)), 2) if n else None
            item = {
                "stage": stage, "horizon": int(h),
                "sample_count": n,
                "pending_or_incomplete": int(stage_pending.get(str(h), 0)),
                "mean_pct": stat(lambda s: s.mean()),
                "median_pct": stat(lambda s: s.median()),
                "positive_rate_pct": stat(lambda s: 100 * (s > 0).mean()),
                "mean_worst_intraperiod_pct": (round(float(subset["max_adverse_pct"].mean()), 2) if n else None),
                # Small or correlated samples must never be marketed as accuracy.
                "sample_status": "DESCRIPTIVE_ONLY" if n >= 30 else "INSUFFICIENT_SAMPLE",
            }
            summary.append(item)
            total_completed[f"{stage}:{h}"] = n
    # Recent full examples only; no per-stock recommendation or per-stock win-rate.
    examples = []
    if not frame.empty:
        matched = frame.loc[frame.horizon == 5].sort_values(
            ["signal_date", "market", "code"], ascending=[False, True, True]
        )
        examples = (
            matched.groupby("stage", sort=False, group_keys=False)
            .head(20)
            .sort_values(["signal_date", "market", "code"], ascending=[False, True, True])
            .to_dict("records")
        )
    return {
        "model": EVAL_VERSION,
        "latest_data_date": as_of,
        "event_count": int(total_events),
        "horizons_in_trading_sessions": list(HORIZONS),
        "entry_rule": "NEXT_SESSION_OPEN",
        "exit_rule": "SESSION_T_PLUS_H_CLOSE",
        "sample_rows": summary,
        "recent_completed_5d_events": examples,
        "interpretation": {
            "status": "RETROSPECTIVE_IN_SAMPLE_NOT_PROSPECTIVE",
            "not_a_success_probability": True,
            "unadjusted_prices": True,
            "includes_trading_costs": False,
            "verified_institutional_flow": False,
            "caveats": [
                "僅為現存資料庫證券的事後描述；不是成功率或有效的樣本外預測。",
                "訊號使用當日收盤後資料，報酬以下一個交易日開盤價起算。",
                "隔日漲停買不到、滑價、交易費、證交稅、除權息/分割未納入。",
                "近期訊號若尚未走完觀察期，列為待觀察，不計入統計。",
                "停牌、缺少整段交易日K線、價格異常的樣本均不計入，避免把不完整資料充作報酬。",
                "回測期間短、樣本彼此相關；挑選示例股票後調整參數會引入事後選擇偏差。",
                "目前無法以券商分點/主力帳戶資料交叉認證。",
            ],
        },
    }


def sample_records_for_excel(records):
    if not records:
        return pd.DataFrame({"狀態": ["歷史訊號尚未有可完整觀察的交易期間"]})
    view = pd.DataFrame(records)
    cols = ["signal_date", "market", "code", "stage", "horizon",
            "entry_date", "exit_date", "entry_open", "exit_close",
            "forward_return_pct", "max_adverse_pct", "max_favorable_pct"]
    rename = {
        "signal_date": "訊號出現日", "market": "市場", "code": "股票代號",
        "stage": "訊號類型", "horizon": "持有交易日",
        "entry_date": "隔日開盤日", "exit_date": "觀察截止日",
        "entry_open": "隔日開盤價", "exit_close": "截止收盤價",
        "forward_return_pct": "區間報酬率%", "max_adverse_pct": "期間最差低點%",
        "max_favorable_pct": "期間最高價幅度%",
    }
    return view[cols].rename(columns=rename)
