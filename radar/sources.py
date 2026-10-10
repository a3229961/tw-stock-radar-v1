"""Official daily whole-market OHLCV collectors. No private/4J sources."""
import datetime as dt
import re
import time
import requests

UA = {'User-Agent':'Mozilla/5.0 (compatible; TWStockRadar/1.0; public research)','Accept':'application/json,text/plain,*/*'}


def number(x):
    if x is None: return None
    s = re.sub(r'<[^>]+>', '', str(x)).strip().replace(',', '').replace('＋','+').replace('−','-')
    if s in ('', '--', '---', '-', 'N/A', '除權', '除息', '暫停交易'): return None
    try: return float(s)
    except ValueError: return None


def field_index(fields, *options):
    normalized = [re.sub(r'\s|<[^>]*>', '', str(v)) for v in fields]
    for opt in options:
        for i, name in enumerate(normalized):
            if opt in name: return i
    return None


def get_json(session, url, params, retries=3):
    last = None
    for attempt in range(retries):
        try:
            r=session.get(url,params=params,headers=UA,timeout=35)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as exc:
            last=exc
            if attempt < retries-1: time.sleep(2*(attempt+1))
    raise RuntimeError(f'Official source request failed: {url}: {last}')


def valid_symbol(code):
    # V1 deliberately restricts to 4-digit common-stock-like codes; log exclusions.
    return bool(re.fullmatch(r'[1-9]\d{3}', str(code).strip()))


def normalize(date, market, code, name, volume, op, hi, lo, close, value, url):
    code=str(code).strip()
    if not valid_symbol(code): return None
    nums=[number(v) for v in (volume,op,hi,lo,close,value)]
    vol,o,h,l,c,turnover=nums
    if any(v is None for v in (o,h,l,c)) or not (0<l<=min(o,c)<=max(o,c)<=h): return None
    if vol is None or vol < 0: return None
    return (date.isoformat(),market,code,str(name).strip(),o,h,l,c,int(vol),turnover,url)


def parse_twse(payload, date, url):
    if payload.get('stat') not in (None,'OK'): return []
    tables=list(payload.get('tables') or [])
    for n in range(1,30):
        if f'fields{n}' in payload and f'data{n}' in payload:
            tables.append({'fields':payload[f'fields{n}'],'data':payload[f'data{n}']})
    out=[]
    for table in tables:
        fields=table.get('fields',[])
        code=field_index(fields,'證券代號'); name=field_index(fields,'證券名稱')
        o=field_index(fields,'開盤價'); h=field_index(fields,'最高價'); l=field_index(fields,'最低價'); c=field_index(fields,'收盤價')
        v=field_index(fields,'成交股數'); amt=field_index(fields,'成交金額')
        if any(i is None for i in (code,name,o,h,l,c,v)): continue
        for row in table.get('data',[]):
            try: item=normalize(date,'TWSE',row[code],row[name],row[v],row[o],row[h],row[l],row[c],row[amt] if amt is not None else None,url)
            except (IndexError,TypeError): continue
            if item: out.append(item)
    return list({(r[1],r[2]):r for r in out}.values())


def parse_tpex(payload,date,url):
    if isinstance(payload,dict) and payload.get('stat') not in (None,'OK','ok'): return []
    tables=[]
    if isinstance(payload,list): tables=[payload]
    elif isinstance(payload,dict):
        for key in ('tables','aaData','data','rows'):
            value=payload.get(key)
            if isinstance(value,list):
                if key=='tables': tables += [v.get('data',[]) for v in value if isinstance(v,dict)]
                else: tables.append(value)
    out=[]
    for rows in tables:
        for row in rows:
            if isinstance(row,dict):
                def pick(*keys):
                    for k in keys:
                        if k in row: return row[k]
                    return None
                item=normalize(date,'TPEX',pick('SecuritiesCompanyCode','Code','股票代號','代號','證券代號'),pick('CompanyName','Name','股票名稱','名稱','證券名稱'),pick('TradingShares','TradeVolume','成交股數','成交量'),pick('Open','開盤','開盤價'),pick('High','最高','最高價'),pick('Low','最低','最低價'),pick('Close','收盤','收盤價'),pick('TradeValue','成交金額'),url)
            elif isinstance(row,(list,tuple)) and len(row)>=9:
                # TPEx legacy stk_wn1430: code,name,close,change,open,high,low,avg,volume(shares),value
                item=normalize(date,'TPEX',row[0],row[1],row[8],row[4],row[5],row[6],row[2],row[9] if len(row)>9 else None,url)
            else: continue
            if item: out.append(item)
    return list({(r[1],r[2]):r for r in out}.values())


def fetch_twse(session,date):
    url='https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX'
    params={'response':'json','date':date.strftime('%Y%m%d'),'type':'ALLBUT0999'}
    return parse_twse(get_json(session,url,params),date,url)


def fetch_tpex(session,date):
    # TPEx current historical endpoint; fallback to legacy format. Fail closed if parsing fails.
    url='https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes'
    params={'response':'json','date':date.strftime('%Y/%m/%d')}
    data=get_json(session,url,params)
    rows=parse_tpex(data,date,url)
    if rows: return rows
    legacy='https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php'
    roc=f'{date.year-1911}/{date.month:02d}/{date.day:02d}'
    return parse_tpex(get_json(session,legacy,{'l':'zh-tw','d':roc,'se':'EW'}),date,legacy)
