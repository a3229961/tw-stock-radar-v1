"""產生可由 GitHub Pages 直接瀏覽的台股起漲雷達儀表板。"""
def render_dashboard():
    return r'''<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>台股全市場起漲雷達 V2</title>
<style>
:root{font-family:system-ui,-apple-system,"Noto Sans TC",sans-serif;color-scheme:dark;background:#0a1120;color:#e9efff}
*{box-sizing:border-box}body{margin:0;padding:20px}main{max-width:1220px;margin:auto}
header{display:flex;justify-content:space-between;gap:16px;align-items:center;flex-wrap:wrap}
h1{font-size:clamp(22px,3vw,30px);margin:6px 0}h2{font-size:18px;margin:6px 0}
.sub,.muted{color:#91a1bd}.sub{font-size:13px}.tag{background:#23365b;color:#cbe5ff;border-radius:99px;padding:6px 12px;font-size:12px}
.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:20px 0}
.card{border:1px solid #273650;border-radius:16px;padding:18px;background:#121f34}
.metric{font-size:clamp(21px,3vw,32px);font-weight:800;margin:8px 0}
.warning{border-left:3px solid #fbbf24;padding:10px 14px;background:#30291c;border-radius:6px;margin:15px 0;line-height:1.65}
.toolbar{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}
input,select{background:#101c30;color:#fff;border:1px solid #42506a;border-radius:9px;padding:10px 12px;font:inherit}
input{flex:1;min-width:200px}select{min-width:140px}
.scroll{overflow-x:auto}.stock-table{width:100%;border-collapse:collapse;min-width:830px}
.stock-table th,.stock-table td{padding:13px 11px;text-align:right;border-bottom:1px solid #283951}
.stock-table th:first-child,.stock-table td:first-child{text-align:left}
.stock-table th{color:#a7b7d2;white-space:nowrap;font-size:13px;cursor:pointer}
.stock-table tbody tr{cursor:pointer}.stock-table tbody tr:hover{background:#1d304f}
.pos{color:#64d0a7}.nil{color:#a9b4c7}button{cursor:pointer;background:#274b79;color:white;border:0;border-radius:8px;padding:7px 11px}
.pill{display:inline-block;border-radius:7px;padding:4px 9px;background:#263956;font-size:12px}
.detail{margin:18px 0;display:none}.detail.on{display:block}
.scoregrid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.score{font-size:27px;font-weight:800;margin:6px 0}
footer{color:#8fa1ba;font-size:12px;margin:25px 0;line-height:1.8}
a{color:#a5d6ff}
@media(max-width:660px){body{padding:12px}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.scoregrid{grid-template-columns:1fr}}
</style>
</head>
<body><main>
<header><div><div class="sub">TWSE × TPEx</div><h1>台股全市場起漲雷達</h1><div class="sub" id="asof">正在讀取報告…</div></div><span class="tag">V2 技術 × 分點觀察</span></header>
<div class="metrics">
<div class="card"><div class="muted">資料庫股票</div><div class="metric" id="total">—</div></div>
<div class="card"><div class="muted">80根K線達標</div><div class="metric" id="coverage">—</div></div>
<div class="card"><div class="muted">技術排名</div><div class="metric" id="ranked">—</div></div>
<div class="card"><div class="muted">分點資料狀態</div><div class="metric" id="branch" style="font-size:20px">讀取中</div></div>
</div>
<div class="warning" id="notice">本頁的技術分數是規則評分，不等於勝率或買進建議。分點資料不完整時，籌碼分數顯示「未提供」。</div>
<section class="card"><h2>技術起漲觀察榜</h2><div class="sub">依原V1技術分數和成交量比排序；點選個股查看指標及分點資料狀態。</div>
<div class="toolbar"><input id="q" placeholder="搜尋代號或股票名稱" aria-label="股票搜尋"><select id="market"><option value="">上市＋上櫃</option><option value="TWSE">上市</option><option value="TPEX">上櫃</option></select><select id="sort"><option value="tech_score">技術評分</option><option value="volume_ratio">成交量比</option><option value="score_delta5">五日分數增幅</option><option value="turnover">成交金額</option><option value="branch_score">分點品質分數</option></select></div>
<div class="scroll"><table class="stock-table"><thead><tr><th>股票</th><th>市場</th><th>收盤</th><th>技術分數</th><th>分點分數</th><th>量比</th><th>MA20乖離</th><th>五日增幅</th></tr></thead><tbody id="rows"><tr><td colspan="8">載入中…</td></tr></tbody></table></div>
<div class="sub" id="count" style="margin-top:12px"></div></section>
<section class="card detail" id="detail"><h2 id="stocktitle">個股指標</h2><div class="scoregrid">
<div><div class="muted">技術分數</div><div class="score" id="dt-tech">—</div></div>
<div><div class="muted">分點品質</div><div class="score" id="dt-branch">—</div></div>
<div><div class="muted">隔日沖分點買入占比</div><div class="score" id="dt-risk">—</div></div>
</div><p id="dt-metrics"></p><p id="dt-note" class="muted"></p></section>
<footer>資料來源：TWSE／TPEx官方逐日行情（技術面）。分點數據需額外取得授權或可靠完整資料，圖片中的分點操作類型僅為待驗證參考。券商分點不等於法人或單一帳戶。<br><a href="report.json">原始JSON</a> ｜ <a href="radar.csv">CSV資料</a>。資料僅供研究與風險管理，非投資建議。</footer>
</main>
<script>
'use strict';
const $=id=>document.getElementById(id);
let stocks=[];
function num(v,d=2){return v===null||v===undefined||!Number.isFinite(Number(v))?'—':Number(v).toLocaleString('zh-TW',{minimumFractionDigits:d,maximumFractionDigits:d});}
function txt(node,s){node.textContent=String(s);}
function cell(tr,s,cl){let td=document.createElement('td');td.textContent=s;if(cl)td.className=cl;tr.appendChild(td);}
function showDetail(x){
 $('detail').classList.add('on');
 txt($('stocktitle'),x.name+' ('+x.code+')｜'+(x.market==='TWSE'?'上市':'上櫃'));
 txt($('dt-tech'),num(x.tech_score,0));
 txt($('dt-branch'),x.branch_score===null||x.branch_score===undefined?'未提供':num(x.branch_score,1));
 txt($('dt-risk'),x.branch_overnight_risk==null?'未提供':num(x.branch_overnight_risk,1)+'%');
 txt($('dt-metrics'),'收盤 '+num(x.close)+'｜MA20 '+num(x.ma20)+'｜MA60 '+num(x.ma60)+'｜RSI14 '+num(x.rsi14,1)+'｜ADX14 '+num(x.adx14,1)+'｜量比 '+num(x.volume_ratio)+'倍');
 txt($('dt-note'),x.branch_score==null?'尚無足夠已驗證的分點交易資料，暫不提供籌碼品質分數。':('籌碼品質分數為規則試算，不代表單一主力吸籌。5日分點淨買 '+num(x.branch_net5,0)+'；20日分點淨買 '+num(x.branch_net20,0)+'。'));
 $('detail').scrollIntoView({behavior:'smooth',block:'nearest'});
}
function draw(){
 let q=$('q').value.trim().toLowerCase(),m=$('market').value,key=$('sort').value;
 let data=stocks.filter(x=>(!m||x.market===m)&&(!q||(String(x.code)+' '+String(x.name)).toLowerCase().includes(q)))
   .sort((a,b)=>(Number(b[key]??-999999)-Number(a[key]??-999999))||(Number(b.tech_score)-Number(a.tech_score)));
 const body=$('rows');body.replaceChildren();
 if(!data.length){let tr=document.createElement('tr');cell(tr,'沒有符合條件的股票');body.appendChild(tr);}
 data.forEach(x=>{let tr=document.createElement('tr');tr.tabIndex=0;tr.setAttribute('role','button');tr.setAttribute('aria-label','查看'+x.name+'詳細資料');
 cell(tr,x.name+' ('+x.code+')');cell(tr,x.market==='TWSE'?'上市':'上櫃');cell(tr,num(x.close));cell(tr,num(x.tech_score,0),'pos');
 cell(tr,x.branch_score==null?'未提供':num(x.branch_score,1));cell(tr,num(x.volume_ratio)+'×');cell(tr,num(x.bias20)+'%');cell(tr,num(x.score_delta5,0));
 tr.addEventListener('click',()=>showDetail(x));tr.addEventListener('keydown',e=>{if(e.key==='Enter')showDetail(x);});body.appendChild(tr);});
 txt($('count'),'顯示 '+data.length+' 檔（公開報告最多50檔），不是全市場完整候選清單');
}
async function load(){
 try{
  let r=await fetch('report.json',{cache:'no-store'});if(!r.ok)throw new Error('HTTP '+r.status);
  let data=await r.json(),s=data.summary||{};stocks=Array.isArray(data.top)?data.top:[];
  txt($('asof'),'行情日期：'+(s.latest_data_date||'—')+'｜報告生成：'+(s.generated_at_taipei||'—'));
  txt($('total'),num(s.total_symbols_in_database,0));txt($('coverage'),num(s.history_coverage_pct)+'%');
  txt($('ranked'),num(s.ranked_count,0));
  txt($('branch'),s.branch_coverage==='AVAILABLE_PROVISIONAL'?'試算中':'尚無完整資料');
  if(s.branch_coverage==='AVAILABLE_PROVISIONAL')txt($('notice'),'籌碼評分為初步試算，請檢查完整性、來源合法性及歷史回測；不可當成保證勝率。');
  draw();
 }catch(e){txt($('asof'),'載入失敗');txt($('notice'),'讀取 report.json 失敗：'+e.message+'。請透過 GitHub Pages 瀏覽本頁，確認JSON已發布。');txt($('rows'),'');}
}
['q','market','sort'].forEach(id=>$(id).addEventListener(id==='q'?'input':'change',draw));load();
</script></body></html>'''