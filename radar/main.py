import argparse
import datetime as dt
import json
import logging
import os
import pathlib
import time
from zoneinfo import ZoneInfo
import requests
import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment
from .sources import fetch_twse,fetch_tpex
from .storage import connect,store,read_prices
from .engine import screen
from .branch_signals import load_branch_trades, enrich_ranking, branch_summary, profiles
from .dashboard import render_dashboard

ROOT=pathlib.Path(__file__).resolve().parents[1]
LOG=logging.getLogger('radar')

def days_to_fetch(conn,today,lookback,max_days):
    start=today-dt.timedelta(days=lookback)
    recorded={x[0] for x in conn.execute("SELECT date FROM fetch_log GROUP BY date HAVING COUNT(DISTINCT CASE WHEN status='ok' THEN market END)=2")}
    # Retry partial failures, do not re-request known market holidays.
    all_days=[today-dt.timedelta(days=i) for i in range((today-start).days+1)]
    return [d for d in all_days if d.weekday()<5 and d.isoformat() not in recorded][:max_days]

def export(conn,outdir,docsdir,day):
    outdir.mkdir(parents=True,exist_ok=True);docsdir.mkdir(parents=True,exist_ok=True)
    prices=read_prices(conn)
    ranking=screen(prices)
    branch_data, branch_status = load_branch_trades(ROOT/'data'/'branch_trades.csv')
    log=pd.read_sql_query('SELECT * FROM fetch_log ORDER BY date DESC,market',conn)
    latest=prices['date'].max() if not prices.empty else None
    latest_count=prices[prices.date==latest].groupby('market')['code'].nunique().to_dict() if latest else {}
    eligible=prices.groupby(['market','code']).size() if not prices.empty else pd.Series(dtype=int)
    sufficient=int((eligible>=80).sum())
    total=int(len(eligible))
    summary={'generated_at_taipei':dt.datetime.now(ZoneInfo('Asia/Taipei')).isoformat(),
      'latest_data_date':latest,'total_symbols_in_database':total,'symbols_with_80_bars':sufficient,
      'history_coverage_pct':round(100*sufficient/total,2) if total else 0,
      'latest_day_symbols_by_market':latest_count,'ranked_count':int(len(ranking)),
      'complete_full_market_scan':False, 'branch_coverage':'NOT_IMPLEMENTED_V1',
      'caveats':['V1 4-digit symbol filter is a proxy, not a verified common-stock security master.',
      'No corporate-action-adjusted prices; do not infer split/dividend adjusted signals.',
      'Historical score acceleration uses same-day price features; no chip/branch scoring.',
      'Market-wide coverage cannot be certified without verified official universe.',
      'Github scheduled jobs may run late; no direct ChatGPT task ingestion guarantee.']}
    if latest:
        ranking=ranking[ranking.date==latest].copy() if not ranking.empty else ranking
    summary['ranked_count']=int(len(ranking))
    ranking=enrich_ranking(ranking,branch_data,latest) if latest else ranking
    branch_info=branch_summary(branch_data,branch_status)
    summary['branch_coverage']='AVAILABLE_PROVISIONAL' if (not ranking.empty and 'branch_score' in ranking and ranking['branch_score'].notna().any()) else 'NOT_AVAILABLE'
    summary['branch_data_status']=branch_info
    with pd.ExcelWriter(outdir/'radar_latest.xlsx',engine='openpyxl') as w:
        (ranking.head(50) if not ranking.empty else pd.DataFrame({'status':['尚無80根完整K線，無法產生正式排名']})).to_excel(w,'技術雷達',index=False)
        pd.DataFrame([summary]).to_excel(w,'覆蓋率',index=False)
        log.head(200).to_excel(w,'資料擷取紀錄',index=False)
        for sheet in w.book:
            sheet.freeze_panes='A2';sheet.auto_filter.ref=sheet.dimensions
            for cell in sheet[1]:cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='17365D')
            for col in sheet.columns:
                letter=col[0].column_letter
                sheet.column_dimensions[letter].width=min(28,max(12,max(len(str(c.value or '')) for c in list(col)[:80])+2))
    if not ranking.empty:
        ranking.head(50).to_csv(docsdir/'radar.csv',index=False,encoding='utf-8-sig')
    else:(docsdir/'radar.csv').write_text('status\ninsufficient_verified_history\n',encoding='utf-8')
    top=ranking.head(50).copy() if not ranking.empty else pd.DataFrame()
    if not top.empty:
        top=top.astype(object).where(pd.notna(top),None)
    report={'summary':summary,'top':top.to_dict('records') if not top.empty else [],
            'branch_profiles':profiles()}
    (docsdir/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str,allow_nan=False),encoding='utf-8')
    (docsdir/'index.html').write_text(render_dashboard(),encoding='utf-8')
    LOG.info('Coverage: %s',summary)


def main():
    p=argparse.ArgumentParser();p.add_argument('--max-days',type=int,default=8);p.add_argument('--lookback',type=int,default=260);p.add_argument('--date',default=None);args=p.parse_args()
    today=dt.date.fromisoformat(args.date) if args.date else dt.datetime.now(ZoneInfo('Asia/Taipei')).date()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    (ROOT/'data').mkdir(exist_ok=True);(ROOT/'output').mkdir(exist_ok=True)
    conn=connect(ROOT/'data'/'radar.sqlite');session=requests.Session()
    # Per-market fetch logs are tracked separately, so a failure on one source is retryable.
    for day in days_to_fetch(conn,today,args.lookback,args.max_days):
        for market,func in [('TWSE',fetch_twse),('TPEX',fetch_tpex)]:
            old=conn.execute('SELECT status FROM fetch_log WHERE date=? AND market=?',(day.isoformat(),market)).fetchone()
            if old and old[0] in ('ok','holiday'):continue
            try:
                rows=func(session,day)
                if rows:
                    store(conn,day.isoformat(),market,rows,'ok');LOG.info('%s %s: %d',day,market,len(rows))
                else:
                    # Could be source schema drift rather than holiday. Do not mark weekday empty as holiday.
                    store(conn,day.isoformat(),market,[],'empty_unverified','No rows; holiday or schema drift');LOG.warning('%s %s empty',day,market)
            except Exception as exc:
                store(conn,day.isoformat(),market,[],'error',str(exc));LOG.error('%s %s %s',day,market,exc)
            time.sleep(float(os.getenv('SOURCE_DELAY_SECONDS','2')))
    export(conn,ROOT/'output',ROOT/'docs',today)
    conn.close()

if __name__=='__main__':main()
