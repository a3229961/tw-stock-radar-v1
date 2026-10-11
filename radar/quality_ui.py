"""Show meaningful data-quality evidence without calling 80-bar count accuracy."""
CSS=r"""
.qa-panel{margin-bottom:18px}
.qa-flex{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:16px 0}
.qa-box{background:#0b1a2e;border:1px solid #304761;border-radius:12px;padding:12px}
.qa-number{font-size:23px;font-weight:750;margin-top:8px}
.qa-muted{font-size:12px;color:#a9bad3;line-height:1.8}
.qa-warning{color:#f5bc84}
.qa-critical{border-left:4px solid #eb9a6a;padding:10px;background:#2a2529}
.qa-table{border-collapse:collapse;width:100%;min-width:600px}
.qa-table td,.qa-table th{padding:10px;border-bottom:1px solid #2e435d;text-align:left;font-size:13px}
.qa-table th{color:#acc2da}
@media(max-width:690px){.qa-flex{grid-template-columns:repeat(2,minmax(0,1fr))}}
"""
PANEL=r"""
<section class="card qa-panel" id="qa-panel">
<div class="pv-head"><h2>行情完整度與正確性檢查</h2><span class="tag">V5 資料品質監控</span></div>
<p class="qa-muted">「歷史80根K線覆蓋率」只能確認資料庫已累積的長度，不代表與官方全市場完全一致。此區列出雙市場成功日期、最近需補抓的異常，以及近期交易日K線完整率。</p>
<div class="qa-flex">
<div class="qa-box"><span class="muted">兩市場最後成功日期</span><div class="qa-number" id="qa-date">—</div></div>
<div class="qa-box"><span class="muted">已收錄雙市場日期</span><div class="qa-number" id="qa-days">—</div></div>
<div class="qa-box"><span class="muted">近45日待核實批次</span><div class="qa-number" id="qa-problems">—</div></div>
<div class="qa-box"><span class="muted">近80市場日完整率</span><div class="qa-number" id="qa-coverage">—</div></div>
</div>
<div id="qa-message" class="qa-muted qa-critical">讀取品質檢查結果中…</div>
<div class="scroll"><table class="qa-table"><thead><tr><th>日期</th><th>市場</th><th>狀態</th><th>記錄股票數</th></tr></thead><tbody id="qa-issues"><tr><td colspan="4">載入中…</td></tr></tbody></table></div>
<p class="qa-muted">官方股票分類母體、完整休市日曆與除權息還原尚待整合。若遇到某個交易日異常缺漏或官方資料修訂，系統會保留上次成功的資料，不拿異常批次取代。</p>
<a class="qa-muted" href="data_quality.json">查看完整資料品質 JSON、缺漏清單和待驗證的除權息疑點</a>
</section>
"""
JS=r"""
(async()=>{
 try{
 const response=await fetch('data_quality.json',{cache:'no-store'});
 if(!response.ok)throw Error('HTTP '+response.status);
 const qa=await response.json();
 const complete=qa.session_coverage||{};
 txt($('qa-date'),qa.last_both_markets_verified_date||'未確認');
 txt($('qa-days'),qa.verified_both_market_sessions??'—');
 txt($('qa-problems'),qa.last_45d_problem_snapshots??'—');
 txt($('qa-coverage'),complete.latest_80_session_completeness_pct==null?
   '未達80日':num(complete.latest_80_session_completeness_pct)+'%');
 const problems=qa.recent_problem_snapshots||[];
 const absent=qa.recent_weekdays_without_verified_market_pairs||[];
 txt($('qa-message'),
  '最近45天異常批次：'+problems.length+'筆；最近35天沒有完整雙市場成功資料的平日：'+
  (absent.length?absent.slice(-10).join('、'):'無')+
  '。2026年官方休市日已另行排除；未核實的平日仍可能是來源或回補問題。');
 const table=$('qa-issues');table.replaceChildren();
 if(!problems.length){
   const tr=document.createElement('tr');
   const td=document.createElement('td');td.colSpan=4;td.textContent='最近45日暫無已記錄的錯誤批次。';
   tr.append(td);table.append(tr);
 }else{
   problems.slice(0,25).forEach(p=>{
     const tr=document.createElement('tr');
     cell(tr,p.date);
     cell(tr,p.market==='TWSE'?'上市':p.market==='TPEX'?'上櫃':p.market);
     cell(tr,p.status);
     cell(tr,String(p.logged_rows??'—'));
     table.append(tr);
   });
 }
 }catch(err){
  txt($('qa-message'),'尚未取得資料品質報告：'+err.message);
  $('qa-issues').replaceChildren();
 }
})();
"""
def augment_quality_panel(html):
    if '</style>' not in html or '</script>' not in html or 'id="pv-panel"' not in html:
        raise ValueError("Unsupported base radar HTML")
    return (html.replace('</style>',CSS+'\n</style>',1)
                .replace('<section class="card" id="pv-panel"',
                         PANEL+'\n<section class="card" id="pv-panel"',1)
                .replace('</script>',JS+'\n</script>',1))
