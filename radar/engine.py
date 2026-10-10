import numpy as np
import pandas as pd


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
    # Technical score is transparent, never a fabricated institution/chip score.
    score=(c>x['ma20']).astype(int)*15+(x['ma20']>x['ma60']).astype(int)*10+(x['slope20']>0).astype(int)*10
    score+=(x['bias20'].between(-2,8)).astype(int)*15+(x['volume_ratio'].between(1.2,3.5)).astype(int)*10
    score+=(x['rsi14'].between(48,70)).astype(int)*10+(x['macd_hist']>0).astype(int)*10
    score+=((x['adx14']>17)&(x['plus_di']>x['minus_di'])).astype(int)*10
    score+=x['higher_low'].astype(int)*5+x['range_contraction'].astype(int)*5
    x['tech_score']=score
    x['score_delta1']=score-score.shift(1);x['score_delta3']=score-score.shift(3);x['score_delta5']=score-score.shift(5)
    # Indicators require 80 bars for stable warmup; no scoring of insufficient history.
    x.loc[np.arange(len(x))<79,['tech_score','score_delta1','score_delta3','score_delta5']]=np.nan
    return x


def screen(prices, min_bars=80):
    if prices.empty: return pd.DataFrame()
    result=[]
    for (market,code),group in prices.groupby(['market','code'],sort=False):
        if len(group)<min_bars: continue
        d=indicators(group);last=d.iloc[-1]
        if pd.isna(last.tech_score): continue
        rec=last.to_dict();rec['bars']=len(group);result.append(rec)
    if not result: return pd.DataFrame()
    out=pd.DataFrame(result)
    return out.sort_values(['tech_score','volume_ratio'],ascending=[False,False],na_position='last')
