"""基於公開 OHLCV 的「疑似拉抬／起漲」訊號，不能識別真正的主力帳戶。

所有判斷只使用該日及其之前的價量資料。參數是可審查的啟發式條件，
尚未完成歷史回測、分點驗證或已調整股價處理。
"""
import numpy as np
import pandas as pd

SIGNAL_NAMES = {
    "START": "疑似拉抬啟動",
    "EARLY": "起漲初期觀察",
    "PREP": "低量突破前兆",
    "FOLLOW": "量價推升延續",
    "HOT": "短線過熱・勿追",
    "WATCH": "量價異動觀察",
    "NONE": "尚無訊號",
}
SIGNAL_DESCRIPTIONS = {
    "START": "突破前20日高點、放量且收盤位置偏強；仍須觀察隔日是否站穩。",
    "EARLY": "突破前10日高點或重新站回20日線並放量；尚非確定主力進場。",
    "PREP": "低量突破前10日高點且收盤偏強，但未見足夠量能確認；僅列低信心前兆觀察。",
    "FOLLOW": "近期曾觸發啟動訊號，價量仍在延續；不代表適合追高。",
    "HOT": "RSI／乖離／短期漲幅出現過熱風險；優先列為風險警示。",
    "WATCH": "有價量轉強跡象但尚未達確認門檻；適合繼續觀察。",
    "NONE": "未達本模型的量價啟動門檻。",
}
SIGNAL_MODEL_VERSION = "pv-impulse-v2-prep"


def detect_price_volume_impulse(frame):
    """Return a copy with signal columns; input must already include engine indicators.

    START / EARLY / PREP are *new* daily signals, FOLLOW covers 1–3 trading days
    after a prior trigger. HOT overrides buy-interest types.
    """
    x = frame.copy()
    c = pd.to_numeric(x["close"], errors="coerce")
    o = pd.to_numeric(x["open"], errors="coerce")
    h = pd.to_numeric(x["high"], errors="coerce")
    l = pd.to_numeric(x["low"], errors="coerce")
    vol = pd.to_numeric(x["volume"], errors="coerce")
    cash = pd.to_numeric(x["turnover"], errors="coerce") if "turnover" in x else pd.Series(np.nan, index=x.index)
    vr = pd.to_numeric(x["volume_ratio"], errors="coerce")
    bias = pd.to_numeric(x["bias20"], errors="coerce")
    rsi = pd.to_numeric(x["rsi14"], errors="coerce")
    ma5 = pd.to_numeric(x["ma5"], errors="coerce")
    ma20 = pd.to_numeric(x["ma20"], errors="coerce")
    macd_hist = pd.to_numeric(x["macd_hist"], errors="coerce")
    prev10 = h.shift(1).rolling(10, min_periods=10).max()
    prev20 = h.shift(1).rolling(20, min_periods=20).max()
    high20 = (c > prev20 * 1.002).fillna(False)
    high10 = (c > prev10 * 1.002).fillna(False)
    cross20 = ((c > ma20) & (c.shift(1) <= ma20.shift(1))).fillna(False)
    day_pct = (c.div(c.shift(1)) - 1) * 100
    five_pct = (c.div(c.shift(5)) - 1) * 100
    ten_pct = (c.div(c.shift(10)) - 1) * 100
    position = (c-l).div((h-l).where((h-l)>0, np.nan))
    # Avoid marking flat/zero-volume or illiquid securities as institutional activity.
    liquid = (cash >= 15_000_000) & (vol > 0) & (c > 3) & (h >= l) & (c >= l) & (c <= h)
    valid = (np.arange(len(x)) >= 79) & liquid.fillna(False).to_numpy()
    valid = pd.Series(valid, index=x.index)
    # No lookahead: previous highs/MA20/volume averages are historical.
    good_close = (c > o) & (position >= .62) & (day_pct >= 1.3)
    early_position = bias.between(-3, 8) & (five_pct <= 17) & rsi.between(40, 74)
    volume_shock = vr >= 1.35
    baseline = valid & (c > ma20) & good_close & early_position & volume_shock
    launch = baseline & high20 & (vr >= 1.55) & (day_pct >= 2.0)
    potential = baseline & (high10 | cross20)
    # Price can start its first breakout before volume expansion (e.g. 2466).
    # PREP has *lower confidence* and is never an actual 主力進場 claim.
    # It needs a 10-day closing breakout, strong candle, moderate momentum,
    # adequate cash turnover, but volume ratio below the 1.35 confirmation bar.
    prep = (
        valid & high10 & (c > ma20) & (c > o)
        & (position >= .70) & (day_pct >= 2.0)
        & vr.between(.65, 1.349999) & bias.between(-2, 9)
        & (five_pct <= 15) & rsi.between(38, 77)
    )
    # Prioritize risk flags regardless of any raw launch feature.
    hot_rsi = (rsi >= 78).fillna(False)
    hot_bias = (bias >= 12).fillna(False)
    hot_5d = (five_pct >= 24).fillna(False)
    hot_10d = (ten_pct >= 38).fillna(False)
    hot = valid & (hot_rsi | hot_bias | hot_5d | hot_10d)
    cooling = valid & ((rsi >= 74) | (bias >= 9) | (five_pct >= 19))
    # Mark a new launch after a quiet period; not each consecutive candle.
    any_trigger = launch | potential | prep
    recently_triggered = pd.Series(False, index=x.index)
    for lag in (1, 2, 3):
        recently_triggered |= any_trigger.shift(lag, fill_value=False).astype(bool)
    first_trigger = any_trigger & ~recently_triggered
    new_start = first_trigger & launch & ~hot & ~cooling
    new_early = first_trigger & potential & ~launch & ~hot & ~cooling
    new_prep = first_trigger & prep & ~hot & ~(new_start | new_early)
    follow = recently_triggered & valid & (c >= ma5) & (vr >= .85) & ~hot
    watch = (valid & (c > ma20) & good_close &
             (vr >= 1.15) & (bias <= 8) & (five_pct < 17) & ~hot)
    labels = np.select(
        [hot, new_start, new_early, new_prep, follow, watch],
        ["HOT", "START", "EARLY", "PREP", "FOLLOW", "WATCH"],
        default="NONE"
    )
    x["impulse_signal"] = labels
    x["impulse_event"] = new_start | new_early | new_prep
    x["impulse_volume_ratio"] = vr
    x["impulse_return1_pct"] = day_pct
    x["impulse_return5_pct"] = five_pct
    x["impulse_close_position"] = position * 100
    x["impulse_breakout10"] = high10
    x["impulse_breakout20"] = high20
    x["impulse_overheat"] = hot
    x["impulse_risk_flags"] = [
        "、".join(flag for flag, yes in [
            ("RSI過熱", bool(rr)), ("MA20乖離過高", bool(bb)),
            ("5日漲幅過大", bool(ff)), ("10日漲幅過大", bool(tt))
        ] if yes)
        for rr, bb, ff, tt in zip(hot_rsi, hot_bias, hot_5d, hot_10d)
    ]
    # Transparent heuristic strength score: not probability of success.
    strength = (
        (c > ma20).astype(int) * 10
        + (ma5 > ma20).astype(int) * 10
        + (macd_hist > 0).astype(int) * 10
        + high10.astype(int) * 12
        + high20.astype(int) * 13
        + (vr >= 1.35).astype(int) * 10
        + (vr >= 2.0).astype(int) * 8
        + (position >= .68).astype(int) * 7
        + (day_pct >= 2).astype(int) * 5
        + (bias.between(-2, 6)).astype(int) * 7
        + (five_pct.between(0, 13)).astype(int) * 5
        + (rsi.between(48, 70)).astype(int) * 3
    )
    # 100 maximum, no "HOT" score inflation; risk is shown separately.
    x["impulse_strength"] = np.where(valid, strength, np.nan)
    # No actionable stages for <80 bars; other status uses NONE with a separate data reason.
    x.loc[~valid, ["impulse_strength"]] = np.nan
    # Labels for nonliquid stocks should be descriptive, not imply confirmed active funds.
    x["impulse_reason"] = [SIGNAL_DESCRIPTIONS[s] for s in labels]
    return x


def summarize_events(indicator_frame, window=30):
    """Latest stock signal summary with trigger date and age in trading bars."""
    if indicator_frame.empty:
        return {}
    x = indicator_frame
    last = x.iloc[-1]
    recent = x.iloc[-max(window, 1):]
    indices = [i for i, (_, r) in enumerate(recent.iterrows()) if bool(r["impulse_event"])]
    last_date = str(recent.iloc[indices[-1]]["date"]) if indices else None
    age = len(recent) - 1 - indices[-1] if indices else None
    kind = str(last["impulse_signal"])
    latest_in_history = recent.loc[recent["impulse_event"]]
    return {
        "impulse_last_event_date": last_date,
        "impulse_age_bars": age,
        "impulse_recent_events": int(len(latest_in_history)),
        "impulse_model": SIGNAL_MODEL_VERSION,
        "impulse_label": SIGNAL_NAMES.get(kind, SIGNAL_NAMES["NONE"]),
    }
