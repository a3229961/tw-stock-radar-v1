"""Historical signal validation panel for static GitHub Pages dashboard."""
CSS = r"""
.val-panel{margin-bottom:18px}
.val-top{display:flex;gap:12px;justify-content:space-between;align-items:center;flex-wrap:wrap}
.val-help{color:#b1c0d5;font-size:12px;line-height:1.85}
.val-table{width:100%;border-collapse:collapse;min-width:680px}
.val-table th,.val-table td{text-align:right;border-bottom:1px solid #2b3e58;padding:12px 10px}
.val-table th:first-child,.val-table td:first-child{text-align:left}
.val-table th{font-size:13px;color:#a1b5cd}
.val-stage{font-weight:700;color:#cfe5ff}
.val-warn{color:#efbd79}
.val-ok{color:#83ddbb}
.val-bad{color:#f4adad}
.val-number{font-size:19px;font-weight:750}
.val-box{background:#0a1729;border:1px solid #2e405e;border-radius:10px;padding:12px 14px;margin-top:12px}
.val-events{max-height:330px;overflow-y:auto}
.val-controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.val-controls select{min-width:130px}
.val-tag{font-size:11px;color:#f5d7a5;background:#433523;padding:4px 9px;border-radius:20px}
"""
PANEL = r"""
<section class="card val-panel" id="val-panel">
<div class="val-top">
<div><h2>歷史起漲訊號驗證</h2><div class="val-help">觀察起點：訊號出現後的<b>下一交易日開盤價</b>。不以訊號日收盤前已知低點買進。未滿觀察期的訊號不算成功或失敗。</div></div>
<span class="val-tag">回溯描述｜非樣本外勝率</span>
</div>
<div class="toolbar val-controls">
<label for="val-days" class="muted">觀察期間</label>
<select id="val-days"><option value="1">1交易日</option><option value="3">3交易日</option><option value="5" selected>5交易日</option><option value="10">10交易日</option></select>
</div>
<div class="scroll"><table class="val-table"><thead>
<tr><th>型態</th><th>完成樣本</th><th>平均報酬</th><th>中位數</th><th>正報酬占比</th><th>待觀察／資料不完整</th></tr>
</thead><tbody id="val-rows"><tr><td colspan="6">正在讀取歷史訊號驗證…</td></tr></tbody></table></div>
<p class="val-help" id="val-summary">所有數據僅作回溯觀察，不是獲利保證。</p>
<div class="val-box">
<div class="val-top"><h2>已完成5個交易日的實際案例</h2><div class="val-controls"><label for="val-stage" class="muted">訊號類別</label>
<select id="val-stage"><option value="ALL">所有類別</option><option value="START">放量啟動</option><option value="EARLY">起漲初期</option><option value="PREP">低量前兆</option><option value="HOT">過熱警示</option></select></div></div>
<div class="scroll val-events"><table class="val-table"><thead><tr><th>訊號日</th><th>股票</th><th>分類</th><th>隔日開盤</th><th>第5日收盤</th><th>變化率</th></tr></thead><tbody id="val-examples"><tr><td colspan="6">載入中…</td></tr></tbody></table></div>
</div>
<p class="val-help">限制：現有股票名單有存續／選擇偏差；未還原除權息及分割；不含手續費、證交稅、滑價、漲停難以成交等因素。訊號門檻曾以部分歷史示例調整，因此結果<b>不能當成真正樣本外績效</b>。樣本少於30筆不應據此判定有效性。</p>
<p class="val-help"><a href="signal_validation.json">查看完整的歷史驗證JSON及計算限制</a></p>
</section>
"""
JS = r"""
const validationStageLabels={START:'放量啟動',EARLY:'起漲初期',PREP:'低量突破前兆',HOT:'過熱風險'};
let validationData={sample_rows:[],recent_completed_5d_events:[],interpretation:{}};
function valValue(v,suffix='',digits=2){
 if(v===null||v===undefined||!Number.isFinite(Number(v)))return '—';
 return num(Number(v),digits)+suffix;
}
function valDrawTable(){
 const h=Number($('val-days').value);
 const body=$('val-rows');body.replaceChildren();
 const rows=validationData.sample_rows.filter(row=>row.horizon===h);
 if(!rows.length){const tr=document.createElement('tr');cell(tr,'尚未產生完整的歷史訊號驗證。');body.append(tr);return;}
 for(const x of rows){
   const tr=document.createElement('tr');
   const first=document.createElement('td');first.className='val-stage';first.textContent=validationStageLabels[x.stage]||x.stage;tr.append(first);
   cell(tr,valValue(x.sample_count,'',0));
   cell(tr,valValue(x.mean_pct,'%'));
   cell(tr,valValue(x.median_pct,'%'));
   cell(tr,valValue(x.positive_rate_pct,'%'));
   cell(tr,valValue(x.pending_or_incomplete,'',0));
   if(x.sample_count<30){
     tr.classList.add('val-warn');
     first.textContent+='（樣本不足）';
   }
   body.append(tr);
 }
 const totals=rows.map(x=>Number(x.sample_count)||0).reduce((a,b)=>a+b,0);
 txt($('val-summary'),'這是依目前已載入的交易日K線所做的'+h+'日回溯描述；各類別合計'+
     totals+'筆已完成觀察紀錄。重複訊號與市場同漲同跌可能相關，不可將正報酬占比直接稱為勝率。');
}
function valDrawExamples(){
 const f=$('val-stage').value;
 let rows=validationData.recent_completed_5d_events||[];
 if(f!=='ALL')rows=rows.filter(x=>x.stage===f);
 rows=rows.slice(0,60);
 const body=$('val-examples');body.replaceChildren();
 if(!rows.length){const tr=document.createElement('tr');cell(tr,'目前沒有此類別已完成5日觀察的案例。');body.append(tr);return;}
 for(const x of rows){
    const tr=document.createElement('tr');
    cell(tr,x.signal_date);
    cell(tr,String(x.code)+'（'+x.market+'）');
    cell(tr,validationStageLabels[x.stage]||x.stage);
    cell(tr,valValue(x.entry_open));
    cell(tr,valValue(x.exit_close));
    const td=document.createElement('td');
    const r=Number(x.forward_return_pct);
    td.textContent=valValue(x.forward_return_pct,'%');
    td.className=Number.isFinite(r)?(r>0?'val-ok':r<0?'val-bad':''):'';
    tr.append(td);body.append(tr);
 }
}
$('val-days').addEventListener('change',valDrawTable);
$('val-stage').addEventListener('change',valDrawExamples);
(async()=>{
 try{
  const res=await fetch('signal_validation.json',{cache:'no-store'});
  if(!res.ok)throw new Error('HTTP '+res.status);
  const d=await res.json();
  if(!Array.isArray(d.sample_rows)||!Array.isArray(d.recent_completed_5d_events))
    throw new Error('歷史報告格式不符');
  validationData=d;valDrawTable();valDrawExamples();
 }catch(err){
   $('val-rows').replaceChildren();$('val-examples').replaceChildren();
   txt($('val-summary'),'歷史驗證尚未完成匯出：'+err.message+'。現有拉抬觀察功能不受影響。');
 }
})();
"""


def add_validation_panel(html):
    assert '</style>' in html and '</script>' in html
    assert '<section class="card" id="pv-panel"' in html
    html=html.replace('</style>', CSS+'\n</style>',1)
    html=html.replace('<section class="card" id="pv-panel"', PANEL+'\n<section class="card" id="pv-panel"',1)
    html=html.replace('</script>', JS+'\n</script>',1)
    return html
