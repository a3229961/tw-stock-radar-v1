import numpy as np
import pandas as pd

from .pump_signals import detect_price_volume_impulse, summarize_events


# V1 原始的10項評分規則；此處是唯一分數規則來源，網頁只負責顯示。
# 滿分 100，未加入分點或法人買賣超。
SCORE_RULES = [
    {"key": "close_above_ma20", "label": "收盤站上20日均線", "weight": 15, "group": "趨勢結構",
     "criterion": "收盤價 > MA20"},
    {"key": "ma20_above_ma60", "label": "20日均線高於60日均線", "weight": 10, "group": "趨勢結構",
     "criterion": "MA20 > MA60"},
    {"key": "slope20_positive", "label": "20日均線斜率向上", "weight": 10, "group": "趨勢結構",
     "criterion": "MA20 五日斜率 > 0%"},
    {"key": "bias20_reasonable", "label": "20日乖離處於指定範圍", "weight": 15, "group": "價格位置",
     "criterion": "-2% ≤ MA20乖離 ≤ 8%"},
    {"key": "volume_ratio", "label": "成交量相對放大", "weight": 10, "group": "量能",
     "criterion": "1.2 ≤ 量比 ≤ 3.5"},
    {"key": "rsi14_range", "label": "RSI在指定區間", "weight": 10, "group": "動能",
     "criterion": "48 ≤ RSI14 ≤ 70"},
    {"key": "macd_hist_positive", "label": "MACD柱狀體為正", "weight": 10, "group": "動能",
     "criterion": "MACD柱狀體 > 0"},
    {"key": "adx_positive_di", "label": "趨勢強度及多方方向", "weight": 10, "group": "動能",
     "criterion": "ADX14 > 17 且 +DI > -DI"},
    {"key": "higher_low", "label": "近期低點墊高", "weight": 5, "group": "價格型態",
     "criterion": "最近10日最低價 > 前10日最低價"},
    {"key": "range_contraction", "label": "10日價格區間收斂", "weight": 5, "group": "價格型態",
     "criterion": "最近10日相對振幅 < 前10日相對振幅"},
]
assert sum(rule["weight"] for rule in SCORE_RULES) == 100


def indicators(df):
    x=df.sort_values('date').copy()
    c=x['close'].astype(float); h=x['high'].astype(float); l=x['low'].astype(float); v=x['volume'].astype(float)
    for n in (5,10,20,60):
        ma=c.rolling(n,min_periods=n).mean(); x[f'ma{n}']=ma
        x[f'slope{n}']=ma.diff(5)/ma.shift(5)*100
    x['bias20']=(c/x['ma20']-1)*100
    x['position20']=(c-l.rolling(20).min())/(h.rolling(20).max()-l.rolling(20).min()).replace(0,np.nan)*100
    x['position60']=(c-l.rolling(60).min())/(h.rolling(60).max()-l.rolling(60).min()).replace(0,np.nan)*100
    x['volume_ratio']=v/v.rolling(20).mean().shift(1).replace(0,np.nan)
    delta=c.diff(); up=delta.clip(lower=0).ewm(alpha=1/14,adjust=False,min_periods=14).mean(); down=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False,min_periods=14).mean()
    x['rsi14']=100-100/(1+up/down.replace(0,np.nan))
    fast=c.ewm(span=12,adjust=False).mean(); slow=c.ewm(span=26,adjust=False).mean()
    x['macd']=fast-slow; x['macd_signal']=x['macd'].ewm(span=9,adjust=False).mean();x['macd_hist']=x['macd']-x['macd_signal']
    tr=pd.concat([(h-l),(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    plus=h.diff().where((h.diff()>-l.diff())&(h.diff()>0),0)
    minus=(-l.diff()).where((-l.diff()>h.diff())&(-l.diff()>0),0)
    atr=tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean()
    x['plus_di']=100*plus.ewm(alpha=1/14,adjust=False,min_periods=14).mean()/atr.replace(0,np.nan)
    x['minus_di']=100*minus.ewm(alpha=1/14,adjust=False,min_periods=14).mean()/atr.replace(0,np.nan)
    dx=100*(x['plus_di']-x['minus_di']).abs()/(x['plus_di']+x['minus_di']).replace(0,np.nan)
    x['adx14']=dx.ewm(alpha=1/14,adjust=False,min_periods=14).mean()
    x['higher_low']=l.rolling(10).min()>l.shift(10).rolling(10).min()
    x['range_contraction']=((h.rolling(10).max()-l.rolling(10).min())/c)<((h.shift(10).rolling(10).max()-l.shift(10).rolling(10).min())/c.shift(10))
    x['breakout20']=c>h.shift(1).rolling(20).max()
    # 每一項得分由原始指標直接計算，再加總為 tech_score。
    # 不另造新評分公式，也不把「20日突破」誤計入原V1的100分。
    signals={
        "close_above_ma20": c>x['ma20'],
        "ma20_above_ma60": x['ma20']>x['ma60'],
        "slope20_positive": x['slope20']>0,
        "bias20_reasonable": x['bias20'].between(-2,8),
        "volume_ratio": x['volume_ratio'].between(1.2,3.5),
        "rsi14_range": x['rsi14'].between(48,70),
        "macd_hist_positive": x['macd_hist']>0,
        "adx_positive_di": (x['adx14']>17)&(x['plus_di']>x['minus_di']),
        "higher_low": x['higher_low'],
        "range_contraction": x['range_contraction'],
    }
    score_columns=[]
    for rule in SCORE_RULES:
        column='score_'+rule['key']
        x[column]=signals[rule['key']].fillna(False).astype(int)*rule['weight']
        score_columns.append(column)
    score=x[score_columns].sum(axis=1)
    x['tech_score']=score
    x['score_delta1']=score-score.shift(1);x['score_delta3']=score-score.shift(3);x['score_delta5']=score-score.shift(5)
    # Indicators require 80 bars for stable warmup; no scoring of insufficient history.
    x.loc[np.arange(len(x))<79,['tech_score','score_delta1','score_delta3','score_delta5',*score_columns]]=np.nan
    return detect_price_volume_impulse(x)


def _chart_value(value, decimals=2):
    if pd.isna(value):
        return None
    return round(float(value), decimals)


def screen(prices, min_bars=80, return_history=False, chart_bars=65):
    """Scan once for both daily signals and past signals shown on mini K charts.

    Default API remains a DataFrame. return_history=True returns
    (ranking, {market-code: [candles]}) and avoids double recomputation.
    """
    if prices.empty:
        return (pd.DataFrame(), {}) if return_history else pd.DataFrame()
    result = []
    history = {}
    for (market, code), group in prices.groupby(["market", "code"], sort=False):
        if len(group) < min_bars:
            continue
        d = indicators(group)
        last = d.iloc[-1]
        if pd.isna(last.tech_score):
            continue
        rec = last.to_dict()
        rec["bars"] = len(group)
        rec.update(summarize_events(d))
        result.append(rec)
        if return_history:
            candles = []
            for r in d.tail(chart_bars).itertuples(index=False):
                candles.append([
                    str(r.date), _chart_value(r.open), _chart_value(r.high),
                    _chart_value(r.low), _chart_value(r.close),
                    int(r.volume) if pd.notna(r.volume) else None,
                    _chart_value(r.ma5), _chart_value(r.ma20),
                    str(r.impulse_signal), bool(r.impulse_event),
                    _chart_value(r.impulse_volume_ratio),
                ])
            history[str(market) + "-" + str(code)] = candles
    if not result:
        return (pd.DataFrame(), {}) if return_history else pd.DataFrame()
    out = pd.DataFrame(result).sort_values(
        ["tech_score", "volume_ratio"], ascending=[False, False], na_position="last"
    )
    return (out, history) if return_history else out
