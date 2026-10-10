import datetime as dt
import numpy as np
import pandas as pd
from radar.sources import parse_twse,parse_tpex,valid_symbol
from radar.engine import indicators,screen

def test_twse_table_and_filter():
    p={'stat':'OK','tables':[{'fields':['證券代號','證券名稱','成交股數','成交金額','開盤價','最高價','最低價','收盤價'],
    'data':[['2330','測試股','1,000','200,000','100','105','99','102'],['0050','ETF','100','1000','50','51','49','50'],['9999','壞價','1','1','105','100','90','99']]}]}
    x=parse_twse(p,dt.date(2026,10,8),'source');assert len(x)==1 and x[0][2]=='2330' and x[0][7]==102

def test_tpex_legacy():
    p={'aaData':[['4939','亞電','78.3','+1.4','76.2','80.7','76.2','78','12238000','950000000']]}
    x=parse_tpex(p,dt.date(2026,10,8),'source');assert len(x)==1 and x[0][2]=='4939'

def test_80_bar_gate_and_indicators():
    n=100; df=pd.DataFrame({'date':pd.date_range('2026-01-01',periods=n,freq='B').astype(str),
      'market':['TWSE']*n,'code':['2330']*n,'name':['測試']*n,
      'open':np.arange(n)+100,'high':np.arange(n)+102,'low':np.arange(n)+99,
      'close':np.arange(n)+101,'volume':np.full(n,100000)})
    x=indicators(df);assert np.isnan(x.tech_score.iloc[40]);assert not np.isnan(x.tech_score.iloc[-1]);assert 'adx14' in x
    assert len(screen(df))==1
    assert screen(df.iloc[:70]).empty
