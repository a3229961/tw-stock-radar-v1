"""Market data quality checks: verify downloads, do not certify by row-count alone.

An accepted snapshot must pass shape, symbol, OHLC, numerical sanity, and
relative market-width checks. Public JSON explicitly separates internal
database coverage from certified all-common-share market coverage.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import statistics
from collections import Counter
from pathlib import Path

import pandas as pd

MIN_BASE_ROWS = {"TWSE": 600, "TPEX": 400}
# Reject a daily scrape missing >15% of the normal recorded stock symbols.
RELATIVE_MIN_FRACTION = 0.85
# Minor missing turnover is tolerated: some official rows legitimately omit it.
SUSPICIOUS_TURNOVER_FRACTION = 0.10


class MarketBatchRejected(ValueError):
    """A fetched snapshot was partial, malformed, or too small to trust."""


def historical_market_baseline(conn, market, exclude_date=None):
    records = conn.execute(
        """SELECT p.date, COUNT(DISTINCT p.code)
           FROM prices p JOIN fetch_log f
             ON p.date=f.date AND p.market=f.market
          WHERE p.market=? AND f.status='ok' AND p.date != COALESCE(?, '')
          GROUP BY p.date
          ORDER BY p.date DESC LIMIT 30""",
        (market, exclude_date),
    ).fetchall()
    valid = [int(n) for _, n in records if n >= MIN_BASE_ROWS.get(market, 100)]
    return round(statistics.median(valid)) if len(valid) >= 3 else None


def audit_candidate(conn, day, market, rows):
    """Fail closed on incomplete or malformed daily download.

    Return metrics for logging. Rejecting a refresh MUST NOT delete the
    existing persisted good snapshot for this date.
    """
    if market not in MIN_BASE_ROWS:
        raise MarketBatchRejected(f"Unknown market: {market!r}")
    if not rows:
        raise MarketBatchRejected("No parsed rows")
    codes = set()
    value_outliers = []
    violations = []
    for i, row in enumerate(rows):
        if len(row) != 11:
            violations.append(f"row[{i}] column count {len(row)}")
            continue
        d, m, code, name, o, h, l, c, volume, turnover, source = row
        code = str(code)
        if d != day or m != market or len(code) != 4 or not code.isdigit():
            violations.append(f"row[{i}] date/market/symbol mismatch")
        if code in codes:
            violations.append(f"row[{i}] duplicate code {code}")
        codes.add(code)
        if not str(name).strip() or str(name).strip().lower() in ("none", "nan"):
            violations.append(f"row[{i}] missing stock name")
        try:
            vals = [float(v) for v in (o, h, l, c, volume)]
            if not all(math.isfinite(v) for v in vals):
                raise ValueError("nonfinite")
            open_, high, low, close, vol = vals
            if not (0 < low <= min(open_, close) <= max(open_, close) <= high):
                raise ValueError("broken OHLC")
            if vol < 0 or vol != int(vol):
                raise ValueError("invalid volume")
            if turnover is not None:
                cash = float(turnover)
                if not math.isfinite(cash) or cash < 0:
                    raise ValueError("invalid turnover")
                # Turnover should be roughly shares times VWAP.
                # Some official data includes odd lots, so allow 10% leeway.
                if vol > 0 and cash > 0 and not (low * .9 <= cash / vol <= high * 1.1):
                    value_outliers.append(code)
        except (TypeError, ValueError) as exc:
            violations.append(f"row[{i}] {exc}")
        if not isinstance(source, str) or not source.startswith("https://"):
            violations.append(f"row[{i}] missing HTTPS provenance")
    if violations:
        raise MarketBatchRejected(
            f"{market} {day} contains {len(violations)} invalid values; "
            f"examples: {'; '.join(violations[:5])}"
        )
    count = len(rows)
    min_base = MIN_BASE_ROWS[market]
    baseline = historical_market_baseline(conn, market, exclude_date=day)
    threshold = max(min_base, math.ceil(baseline * RELATIVE_MIN_FRACTION)) if baseline else min_base
    if count < threshold:
        raise MarketBatchRejected(
            f"{market} {day}: parsed {count} stocks, require >= {threshold} "
            f"(historical median {baseline or 'unavailable'}); probable partial feed"
        )
    value_fraction = len(value_outliers) / count
    if value_fraction > SUSPICIOUS_TURNOVER_FRACTION:
        raise MarketBatchRejected(
            f"{market} {day}: {len(value_outliers)}/{count} stocks have turnover "
            "outside 10% OHLC/VWAP tolerance; likely field mapping/units drift"
        )
    return {
        "row_count": count,
        "historical_median": baseline,
        "minimum_accepted_rows": threshold,
        "turnover_suspects": len(value_outliers),
        "turnover_examples": value_outliers[:6],
    }


def _all_snapshot_counts(conn):
    rows = conn.execute(
        """SELECT f.date,f.market,f.status,f.rows,
                  (SELECT COUNT(*) FROM prices p WHERE p.date=f.date AND p.market=f.market)
           FROM fetch_log f ORDER BY f.date DESC,f.market"""
    ).fetchall()
    return [
        {"date": d, "market": m, "status": status,
         "logged_rows": int(n), "stored_rows": int(actual)}
        for d, m, status, n, actual in rows
    ]


def make_quality_report(conn, prices, today=None):
    """Quality is observable evidence, not a claim of verified common-stock universe."""
    today = today or dt.date.today()
    history = _all_snapshot_counts(conn)
    successful = [x for x in history if x["status"] == "ok"]
    by_date = {}
    market_dates = {"TWSE": set(), "TPEX": set()}
    for r in successful:
        by_date.setdefault(r["date"], {})[r["market"]] = r
        if r["market"] in market_dates:
            market_dates[r["market"]].add(r["date"])
    complete_days = sorted(d for d, markets in by_date.items()
                           if all(m in markets for m in ("TWSE", "TPEX")))
    last_both = complete_days[-1] if complete_days else None
    last_date = str(prices["date"].max()) if not prices.empty else None
    recent_accepted = [x for x in successful if x["date"] >=
                       (today - dt.timedelta(days=45)).isoformat()]
    recent_rejected = [x for x in history if x["status"] in
                       ("quality_rejected", "error", "empty_unverified")
                       and x["date"] >= (today - dt.timedelta(days=45)).isoformat()]
    latest_counts = {
        m: int(prices.loc[(prices.date == last_both) & (prices.market == m), "code"].nunique())
        if last_both and not prices.empty else 0
        for m in ("TWSE", "TPEX")
    }
    # market session completeness is a *different* metric from "80 rows in
    # SQLite", computed only when 80 fully fetched market dates exist.
    recent80 = complete_days[-80:]
    coverage = {
        "status": "READY" if len(recent80) == 80 else "INSUFFICIENT_COMPLETE_SESSIONS",
        "observed_complete_sessions": len(recent80),
        "required_sessions": 80,
        "latest_80_session_full_symbols": None,
        "latest_80_session_reference_symbols": None,
        "latest_80_session_completeness_pct": None,
    }
    if len(recent80) == 80 and not prices.empty:
        recent_prices = prices.loc[prices.date.isin(recent80)]
        counts = recent_prices.groupby(["market", "code"])["date"].nunique()
        recent_snapshot = recent_prices.loc[recent_prices.date == last_both, ["market", "code"]]
        latest_codes = set(zip(recent_snapshot.market, recent_snapshot.code))
        complete = sum(int(counts.get(key, 0) == 80) for key in latest_codes)
        denominator = len(latest_codes)
        coverage.update({
            "latest_80_session_full_symbols": int(complete),
            "latest_80_session_reference_symbols": int(denominator),
            "latest_80_session_completeness_pct":
                round(100 * complete / denominator, 2) if denominator else None,
        })
    # Large day-to-day jumps are not automatically invalid: ex-rights, splits,
    # price-limit behavior and long suspensions need a corporate-action feed.
    price_jumps = []
    if not prices.empty:
        data = prices.sort_values(["market", "code", "date"]).copy()
        prev = data.groupby(["market", "code"])["close"].shift(1)
        jump = (data["close"] / prev - 1) * 100
        suspect = data.loc[jump.abs() >= 30].copy()
        suspect["gap_pct"] = jump.loc[suspect.index]
        for r in suspect.tail(40).itertuples(index=False):
            price_jumps.append({
                "date": str(r.date), "market": str(r.market),
                "code": str(r.code), "name": str(r.name),
                "gap_pct": round(float(r.gap_pct), 1),
            })
    weekday_unverified = []
    if last_date:
        earliest = max(
            (today - dt.timedelta(days=35)),
            dt.date.fromisoformat(min(x["date"] for x in history)) if history else today,
        )
        known = set(x["date"] for x in successful)
        for i in range((today - earliest).days + 1):
            d = earliest + dt.timedelta(days=i)
            if d.weekday() < 5 and d.isoformat() not in known and d <= today:
                weekday_unverified.append(d.isoformat())
    failures = [
        {**r, "note": ("可能是假日、官方來源問題、部分資料或尚未回補，不能自行判定為休市")}
        for r in recent_rejected[:24]
    ]
    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "last_price_date_in_database": last_date,
        "last_both_markets_verified_date": last_both,
        "latest_verified_market_counts": latest_counts,
        "verified_both_market_sessions": len(complete_days),
        "last_45d_accepted_snapshots": len(recent_accepted),
        "last_45d_problem_snapshots": len(recent_rejected),
        "recent_problem_snapshots": failures,
        "recent_weekdays_without_verified_market_pairs": weekday_unverified[-20:],
        "session_coverage": coverage,
        "potential_unadjusted_corporate_actions": price_jumps[-20:],
        "status": "PARTIAL_COVERAGE_NOT_CERTIFIED",
        "assumptions": [
            "正式股票普通股母體尚未由證交所與櫃買官方證券分類名冊逐一核對。",
            "休市日清單尚未接入官方完整日曆，缺漏平日不能自動認定為休市。",
            "最近80個市場日完整度以已抓成功的共同日期計算，並非官方市場交易日曆。",
            "除權息、股票分割、減資等調整未接入，異常價差只提示人工審核，不推論錯誤或買賣訊號。",
            "有80筆行情只代表資料長度，不代表資料正確率或所有市場股票都已涵蓋。",
        ],
    }


def save_quality_report(conn, prices, destination, today=None):
    report = make_quality_report(conn, prices, today=today)
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False,
                               indent=2, allow_nan=False), encoding="utf-8")
    return report
