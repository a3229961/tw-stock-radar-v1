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
from .storage import connect,store,read_prices,replace_market_snapshot,record_attempt
from .engine import screen, SCORE_RULES
from .branch_signals import load_branch_trades, enrich_ranking, branch_summary, profiles
from .dashboard import render_dashboard
from .catalog import build_catalog
from .pump_export import publish_impulse, impulse_excel_view
from .signal_validation import aggregate_validation, sample_records_for_excel
from .data_quality import audit_candidate, MarketBatchRejected, save_quality_report
from .market_holidays import is_equity_session_candidate, label_past_empty_holidays

ROOT=pathlib.Path(__file__).resolve().parents[1]
LOG=logging.getLogger('radar')

def days_to_fetch(conn,today,lookback,max_days):
    start=today-dt.timedelta(days=lookback)
    recorded={x[0] for x in conn.execute("SELECT date FROM fetch_log GROUP BY date HAVING COUNT(DISTINCT CASE WHEN status='ok' THEN market END)=2")}
    # Retry partial failures, do not re-request known market holidays.
    all_days=[today-dt.timedelta(days=i) for i in range((today-start).days+1)]
    return [d for d in all_days if is_equity_session_candidate(d) and d.isoformat() not in recorded][:max_days]

def days_to_recheck(conn, count=2):
    """Double-check recent accepted market sessions for delayed official revisions."""
    if count<=0:
        return []
    dates=conn.execute(
        """SELECT date FROM fetch_log
           WHERE status='ok'
           GROUP BY date HAVING COUNT(DISTINCT market)=2
           ORDER BY date DESC LIMIT ?""",(count,)
    ).fetchall()
    return [dt.date.fromisoformat(d[0]) for d in dates]


def export(conn,outdir,docsdir,day):
    outdir.mkdir(parents=True,exist_ok=True);docsdir.mkdir(parents=True,exist_ok=True)
    prices=read_prices(conn)
    audit_today=day if isinstance(day,dt.date) else dt.date.fromisoformat(str(day))
    quality=save_quality_report(conn,prices,docsdir/'data_quality.json',today=audit_today)
    # An isolated new-date feed from only one market must not appear as a
    # complete next trading session. Preserve the raw rows for QA review,
    # but publish only up to the last date BOTH markets have accepted.
    complete_latest=quality['last_both_markets_verified_date']
    if complete_latest and not prices.empty:
        prices=prices.loc[prices.date<=complete_latest].copy()
    ranking, history, validation_data=screen(prices,return_history=True,return_validation=True)
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
    summary['data_quality']={
        'status':quality['status'],
        'last_both_markets_verified_date':quality['last_both_markets_verified_date'],
        'verified_both_market_sessions':quality['verified_both_market_sessions'],
        'latest_verified_market_counts':quality['latest_verified_market_counts'],
        'last_45d_problem_snapshots':quality['last_45d_problem_snapshots'],
        'recent_80_session_completeness_pct':quality['session_coverage']['latest_80_session_completeness_pct'],
        'recent_80_session_status':quality['session_coverage']['status'],
    }
    summary['caveats'].append('History_coverage_pct only counts 80 stored bars and is not an official universe coverage or data accuracy measurement.')
    summary['caveats'].append('Data quality evidence and unresolved missing sessions are in docs/data_quality.json.')
    impulse_info, impulse_candidates, impulse_hot, chart_shards = publish_impulse(
        docsdir, ranking, history, latest
    )
    summary['impulse_signals']=impulse_info
    summary['chart_shards']=len(chart_shards)
    validation=aggregate_validation(
        validation_data["records"],validation_data["pending"],
        validation_data["events"],latest
    )
    (docsdir/'signal_validation.json').write_text(
        json.dumps(validation,ensure_ascii=False,separators=(',',':'),
                   default=str,allow_nan=False),encoding='utf-8'
    )
    summary['signal_validation']={
        'method':validation['model'],
        'entry_rule':validation['entry_rule'],
        'event_count':validation['event_count'],
        'interpretation_status':validation['interpretation']['status'],
    }
    summary['caveats'].append('OHLCV momentum observations are not verified branch accumulation or out-of-sample forecast accuracy.')
    summary['caveats'].append('Historical event statistics use next-session open, exclude censored horizons, and omit costs/corporate actions.')
    with pd.ExcelWriter(outdir/'radar_latest.xlsx',engine='openpyxl') as w:
        (ranking.head(50) if not ranking.empty else pd.DataFrame({'status':['尚無80根完整K線，無法產生正式排名']})).to_excel(w,'技術雷達',index=False)
        impulse_excel_view(impulse_candidates,'當日沒有達到拉抬觀察條件的股票').to_excel(w,'量價起漲候選',index=False)
        impulse_excel_view(impulse_hot,'當日沒有符合過熱門檻的股票').to_excel(w,'短線過熱警示',index=False)
        pd.DataFrame(validation['sample_rows']).rename(columns={
            'stage':'訊號類型','horizon':'持有交易日',
            'sample_count':'已完成樣本數','pending_or_incomplete':'尚待觀察／資料不完整',
            'mean_pct':'平均報酬率%','median_pct':'中位數報酬率%',
            'positive_rate_pct':'正報酬占比%','mean_worst_intraperiod_pct':'平均期間最差低點%',
            'sample_status':'樣本狀態',
        }).to_excel(w,'訊號歷史統計',index=False)
        sample_records_for_excel(validation['recent_completed_5d_events']).to_excel(w,'已完成5日案例',index=False)
        pd.DataFrame([summary]).to_excel(w,'覆蓋率',index=False)
        pd.DataFrame([{
            '項目':'資料品質總覽',
            '最後雙市場成功日期':quality['last_both_markets_verified_date'],
            '成功市場日期數':quality['verified_both_market_sessions'],
            '最近45日問題批次數':quality['last_45d_problem_snapshots'],
            '近期80市場日資料完整率%':quality['session_coverage']['latest_80_session_completeness_pct'],
            '80市場日狀態':quality['session_coverage']['status'],
            '全市場普通股已完整驗證':'否（尚需官方證券名冊及完整交易日曆）',
        }]).to_excel(w,'資料品質總覽',index=False)
        pd.DataFrame(quality['recent_problem_snapshots'] or
            [{'狀態':'最近45日尚無已記錄的來源錯誤或不完整批次'}]).to_excel(w,'待補抓與異常',index=False)
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
            'score_rules':SCORE_RULES,'branch_profiles':profiles(),
            'impulse_summary':impulse_info,'impulse_top':impulse_candidates.head(40).astype(object).where(pd.notna(impulse_candidates.head(40)),None).to_dict('records') if not impulse_candidates.empty else [],
            'validation_status':validation['interpretation']['status']}
    (docsdir/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str,allow_nan=False),encoding='utf-8')
    catalog=build_catalog(prices,ranking,latest)
    (docsdir/'radar_all.json').write_text(json.dumps(catalog,ensure_ascii=False,separators=(',',':'),default=str,allow_nan=False),encoding='utf-8')
    (docsdir/'index.html').write_text(render_dashboard(),encoding='utf-8')
    LOG.info('Coverage: %s',summary)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--max-days',type=int,default=8)
    p.add_argument('--lookback',type=int,default=260)
    p.add_argument('--recheck-recent',type=int,default=2,
                   help='Re-download N recent successful market sessions for official revisions')
    p.add_argument('--date',default=None)
    p.add_argument('--quality-only',action='store_true',
                   help='Rebuild quality report and output from existing SQLite without downloading')
    args=p.parse_args()
    today=dt.date.fromisoformat(args.date) if args.date else dt.datetime.now(ZoneInfo('Asia/Taipei')).date()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    (ROOT/'data').mkdir(exist_ok=True);(ROOT/'output').mkdir(exist_ok=True)
    conn=connect(ROOT/'data'/'radar.sqlite')
    known_holidays=label_past_empty_holidays(conn)
    if known_holidays:
        LOG.info('Recognized %d historical empty snapshots as official 2026 holidays',known_holidays)
    session=requests.Session()
    if not args.quality_only:
        unfetched=days_to_fetch(conn,today,args.lookback,args.max_days)
        recheck=days_to_recheck(conn,args.recheck_recent)
        recheck_set=set(recheck)
        days=list(dict.fromkeys(unfetched+recheck))
        LOG.info('Fetch %s unresolved weekdays and recheck %s accepted sessions',len(unfetched),len(recheck))
        for day in days:
            day_text=day.isoformat()
            for market,func in [('TWSE',fetch_twse),('TPEX',fetch_tpex)]:
                old=conn.execute(
                    'SELECT status FROM fetch_log WHERE date=? AND market=?',
                    (day_text,market)
                ).fetchone()
                if old and old[0]=='ok' and day not in recheck_set:
                    continue
                if old and old[0]=='holiday':
                    continue
                try:
                    rows=func(session,day)
                    if not rows:
                        # Empty weekday is not automatically a holiday.
                        record_attempt(conn,day_text,market,'empty_unverified',0,
                                       'No parsed rows; official holiday or source schema drift')
                        LOG.warning('%s %s empty/unverified',day,market)
                        continue
                    try:
                        checks=audit_candidate(conn,day_text,market,rows)
                    except MarketBatchRejected as exc:
                        record_attempt(conn,day_text,market,'quality_rejected',len(rows),str(exc))
                        LOG.error('%s %s REJECTED: %s',day,market,exc)
                        continue
                    saved=replace_market_snapshot(
                        conn,day_text,market,rows,
                        detail=f"batch_min={checks['minimum_accepted_rows']}; value_suspects={checks['turnover_suspects']}"
                    )
                    LOG.info('%s %s: %d VERIFIED; revisions=%s new=%s gone=%s',
                             day,market,len(rows),saved['changed'],saved['added'],saved['removed'])
                except Exception as exc:
                    record_attempt(conn,day_text,market,'error',0,str(exc))
                    LOG.error('%s %s source error: %s',day,market,exc)
                time.sleep(float(os.getenv('SOURCE_DELAY_SECONDS','2')))
    export(conn,ROOT/'output',ROOT/'docs',today)
    conn.close()


if __name__=='__main__':main()
