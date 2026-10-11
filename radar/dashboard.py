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
.score-trigger{font:inherit;font-weight:800;color:#6ed5ad;white-space:nowrap;border:1px solid #355c60;border-radius:8px;background:#162f3a;padding:6px 11px;cursor:pointer}
.score-trigger:hover,.score-trigger:focus-visible{background:#245363;outline:2px solid #66ddbd;outline-offset:2px}
.score-heading{display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap;margin:22px 0 12px}
.breakdown-list{display:grid;gap:9px;margin-top:12px}
.breakdown-row{border:1px solid #293b56;border-radius:11px;background:#0e1b2c;padding:13px 14px;display:grid;grid-template-columns:minmax(0,1fr) 100px;align-items:center;gap:12px}
.breakdown-row.passed{border-left:4px solid #43cba2}
.breakdown-row.failed{border-left:4px solid #e7a55e}
.breakdown-name{font-size:14px;font-weight:700}
.breakdown-meta{font-size:12px;color:#99a9c2;line-height:1.7;margin-top:3px}
.breakdown-points{text-align:right;font-size:17px;font-weight:750}
.breakdown-flag{display:block;font-size:12px;margin-top:5px;font-weight:500}
.passed .breakdown-points,.passed .breakdown-flag{color:#6be1b8}
.failed .breakdown-points,.failed .breakdown-flag{color:#f7be77}
.score-note{font-size:13px;color:#aabbd0;line-height:1.7}
footer{color:#8fa1ba;font-size:12px;margin:25px 0;line-height:1.8}
a{color:#a5d6ff}
@media(max-width:660px){body{padding:12px}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.scoregrid{grid-template-columns:1fr}.breakdown-row{grid-template-columns:minmax(0,1fr) 65px;padding:11px}.breakdown-points{font-size:15px}}
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
<section class="card"><h2>技術起漲觀察榜</h2><div class="sub">可搜尋完整技術排名；<strong>點選技術分數</strong>展開十項評分的得分、條件及失分原因。預設只顯示前100檔以保持載入速度。</div>
<div class="toolbar"><input id="q" placeholder="搜尋代號或股票名稱" aria-label="股票搜尋"><select id="market"><option value="">上市＋上櫃</option><option value="TWSE">上市</option><option value="TPEX">上櫃</option></select><select id="sort"><option value="tech_score">技術評分</option><option value="volume_ratio">成交量比</option><option value="score_delta5">五日分數增幅</option><option value="turnover">成交金額</option><option value="branch_score">分點品質分數</option></select></div>
<div class="scroll"><table class="stock-table"><thead><tr><th>股票</th><th>市場</th><th>收盤</th><th>技術分數</th><th>分點分數</th><th>量比</th><th>MA20乖離</th><th>五日增幅</th></tr></thead><tbody id="rows"><tr><td colspan="8">載入中…</td></tr></tbody></table></div>
<div class="sub" id="count" style="margin-top:12px"></div><div class="sub" id="searchinfo" style="margin-top:10px"></div></section>
<section class="card detail" id="detail"><h2 id="stocktitle">個股指標</h2><div class="scoregrid">
<div><div class="muted">技術分數（100分制）</div><div class="score" id="dt-tech">—</div></div>
<div><div class="muted">分點品質</div><div class="score" id="dt-branch">—</div></div>
<div><div class="muted">隔日沖分點買入占比</div><div class="score" id="dt-risk">—</div></div>
</div><p id="dt-metrics"></p><p id="dt-note" class="muted"></p>
<div class="score-heading"><h2>技術分數細項分析</h2><span class="tag">原始V1評分公式</span></div>
<p id="dt-score-status" class="score-note">載入評分規則中…</p>
<div id="dt-breakdown" class="breakdown-list"></div>
<p id="dt-lost" class="score-note"></p>
<p class="score-note">說明：本表以同一套Python公式計算十項加分；未得分表示當日未滿足該項門檻，不等於隔日必跌。20日突破等指標可供觀察，但目前不列入這100分；分點評分另計。</p></section>
<footer>資料來源：TWSE／TPEx官方逐日行情（技術面）。分點數據需額外取得授權或可靠完整資料，圖片中的分點操作類型僅為待驗證參考。券商分點不等於法人或單一帳戶。<br><a href="report.json">原始JSON</a> ｜ <a href="radar.csv">CSV資料</a>。資料僅供研究與風險管理，非投資建議。</footer>
</main>
<script>
'use strict';
const $=id=>document.getElementById(id);
let stocks=[];
let unranked=[];
let searchReady=false;
let scoreRules=[];
function num(v,d=2){return v===null||v===undefined||!Number.isFinite(Number(v))?'—':Number(v).toLocaleString('zh-TW',{minimumFractionDigits:d,maximumFractionDigits:d});}
function txt(node,s){node.textContent=String(s);}
function cell(tr,s,cl){let td=document.createElement('td');td.textContent=s;if(cl)td.className=cl;tr.appendChild(td);}

function ruleEvidence(x,key){
 switch(key){
  case 'close_above_ma20':return '收盤 '+num(x.close)+' 元；MA20 '+num(x.ma20)+' 元';
  case 'ma20_above_ma60':return 'MA20 '+num(x.ma20)+' 元；MA60 '+num(x.ma60)+' 元';
  case 'slope20_positive':return 'MA20五日斜率 '+num(x.slope20)+'%';
  case 'bias20_reasonable':return 'MA20乖離 '+num(x.bias20)+'%';
  case 'volume_ratio':return '量比 '+num(x.volume_ratio)+' 倍';
  case 'rsi14_range':return 'RSI14 '+num(x.rsi14,1);
  case 'macd_hist_positive':return 'MACD柱狀體 '+num(x.macd_hist,3);
  case 'adx_positive_di':return 'ADX14 '+num(x.adx14,1)+'；+DI '+num(x.plus_di,1)+'；-DI '+num(x.minus_di,1);
  case 'higher_low':return '近期低點墊高：'+(x.higher_low===true?'是':x.higher_low===false?'否':'資料不足');
  case 'range_contraction':return '近期區間收斂：'+(x.range_contraction===true?'是':x.range_contraction===false?'否':'資料不足');
  default:return '詳見條件';
 }
}
function renderBreakdown(x){
 const box=$('dt-breakdown');box.replaceChildren();
 txt($('dt-lost'),'');
 if(!Array.isArray(scoreRules)||scoreRules.length!==10){
   txt($('dt-score-status'),'評分細項尚未完整載入，請在GitHub執行新版報告後重新整理。');
   return;
 }
 let scored=0,possible=0;
 const missing=[];
 for(const rule of scoreRules){
  const raw=x['score_'+rule.key];
  if(raw===null||raw===undefined||!Number.isFinite(Number(raw))){
   box.replaceChildren();
   txt($('dt-score-status'),'這檔股票尚無完整分項得分資料，暫不顯示推算結果。');
   return;
  }
  const earned=Number(raw),max=Number(rule.weight);
  if(!Number.isFinite(max)||max<0||earned<0||earned>max){
   txt($('dt-score-status'),'評分資料格式異常，請勿根據目前分數交易。');
   box.replaceChildren();return;
  }
  scored+=earned;possible+=max;
  const pass=earned===max;
  const item=document.createElement('div');item.className='breakdown-row '+(pass?'passed':'failed');
  const explanation=document.createElement('div');
  const name=document.createElement('div');name.className='breakdown-name';name.textContent=rule.label;
  const meta=document.createElement('div');meta.className='breakdown-meta';
  meta.textContent='判定：'+rule.criterion+'｜實際：'+ruleEvidence(x,rule.key);
  explanation.append(name,meta);
  const points=document.createElement('div');points.className='breakdown-points';points.textContent=earned+' / '+max;
  const status=document.createElement('span');status.className='breakdown-flag';status.textContent=pass?'符合條件':'未符合';
  points.appendChild(status);item.append(explanation,points);box.appendChild(item);
  if(!pass)missing.push(rule.label+'（少'+(max-earned)+'分）');
 }
 const agrees=possible===100&&Math.abs(scored-Number(x.tech_score))<0.001;
 txt($('dt-score-status'),(agrees?'得分核對一致：':'⚠ 得分核對不一致，請勿作為交易依據：')+
     scored+'／'+possible+'分｜'+x.date+'｜'+
     (agrees?'每項得分直接取自原始Python評分結果。':'需檢查程式或資料版本。'));
 txt($('dt-lost'),missing.length?'尚未得分的項目：'+missing.join('、')+'。':'全部十項技術條件皆達標；100分不代表保證上漲。');
}

function showDetail(x){
 $('detail').classList.add('on');
 txt($('stocktitle'),x.name+' ('+x.code+')｜'+(x.market==='TWSE'?'上市':'上櫃'));
 txt($('dt-tech'),num(x.tech_score,0));
 txt($('dt-branch'),x.branch_score===null||x.branch_score===undefined?'未提供':num(x.branch_score,1));
 txt($('dt-risk'),x.branch_overnight_risk==null?'未提供':num(x.branch_overnight_risk,1)+'%');
 txt($('dt-metrics'),'收盤 '+num(x.close)+'｜MA20 '+num(x.ma20)+'｜MA60 '+num(x.ma60)+'｜RSI14 '+num(x.rsi14,1)+'｜ADX14 '+num(x.adx14,1)+'｜量比 '+num(x.volume_ratio)+'倍');
 txt($('dt-note'),x.branch_score==null?'尚無足夠已驗證的分點交易資料，暫不提供籌碼品質分數。':('籌碼品質分數為規則試算，不代表單一主力吸籌。5日分點淨買 '+num(x.branch_net5,0)+'；20日分點淨買 '+num(x.branch_net20,0)+'。'));
 renderBreakdown(x);
 $('detail').scrollIntoView({behavior:'smooth',block:'nearest'});
}
function draw(){
 let q=$('q').value.trim().toLowerCase(),m=$('market').value,key=$('sort').value;
 $('detail').classList.remove('on');
 let data=stocks.filter(x=>(!m||x.market===m)&&(!q||(String(x.code)+' '+String(x.name)).toLowerCase().includes(q)))
   .sort((a,b)=>(Number(b[key]??-999999)-Number(a[key]??-999999))||(Number(b.tech_score)-Number(a.tech_score)));
 const body=$('rows');body.replaceChildren();
 const shown=data.slice(0,100);
 if(!shown.length){let tr=document.createElement('tr');cell(tr,'沒有符合篩選條件的已排名股票');body.appendChild(tr);}
 shown.forEach(x=>{let tr=document.createElement('tr');tr.tabIndex=0;tr.setAttribute('role','button');tr.setAttribute('aria-label','查看'+x.name+'詳細資料');
 cell(tr,x.name+' ('+x.code+')');cell(tr,x.market==='TWSE'?'上市':'上櫃');cell(tr,num(x.close));
 const td=document.createElement('td');const button=document.createElement('button');button.className='score-trigger';button.type='button';
 button.textContent=num(x.tech_score,0)+' 分 ▸';button.setAttribute('aria-label','查看'+x.name+'技術分數細項');
 button.addEventListener('click',event=>{event.stopPropagation();showDetail(x);});
 td.appendChild(button);tr.appendChild(td);
 cell(tr,x.branch_score==null?'未提供':num(x.branch_score,1));cell(tr,num(x.volume_ratio)+'×');cell(tr,num(x.bias20)+'%');cell(tr,num(x.score_delta5,0));
 tr.addEventListener('click',()=>showDetail(x));tr.addEventListener('keydown',e=>{if(e.key==='Enter')showDetail(x);});body.appendChild(tr);});
 txt($('count'),'顯示 '+shown.length+' 檔／符合條件 '+data.length+' 檔；搜尋來源 '+(searchReady?'完整技術排名':'僅前50名備援資料')+'（預設最多顯示100列）');
 if(!searchReady){txt($('searchinfo'),'完整股票清單尚未載入，暫時無法判定不在前50名的股票。');return;}
 if(!q){txt($('searchinfo'),'可用股票名稱或代號搜尋資料庫全部股票；未達80根K線的股票會另外說明。');return;}
 if(data.length){txt($('searchinfo'),'已於全部 '+stocks.length+' 檔技術排名中找到 '+data.length+' 檔。');return;}
 const matches=unranked.filter(x=>(!m||x.market===m)&&(String(x.code)+' '+String(x.name)).toLowerCase().includes(q));
 if(matches.length){
    txt($('searchinfo'),matches.slice(0,8).map(x=>
      x.name+'（'+x.code+'）：'+(x.status==='INSUFFICIENT_HISTORY'?'歷史K線不足80根':'沒有當日完整技術排名')+
      '；已儲存 '+x.bars+' 根，最後行情 '+x.last_data_date).join('；'));
 }else{
    txt($('searchinfo'),'完整資料庫中找不到符合「'+q+'」的股票。可能未被目前V1的四碼代號或行情來源收錄，並不代表該證券不存在。');
 }
}
async function load(){
 try{
  let r=await fetch('report.json',{cache:'no-store'});if(!r.ok)throw new Error('HTTP '+r.status);
  let data=await r.json(),s=data.summary||{};stocks=Array.isArray(data.top)?data.top:[];
  scoreRules=Array.isArray(data.score_rules)?data.score_rules:[];
  txt($('asof'),'行情日期：'+(s.latest_data_date||'—')+'｜報告生成：'+(s.generated_at_taipei||'—'));
  txt($('total'),num(s.total_symbols_in_database,0));txt($('coverage'),num(s.history_coverage_pct)+'%');
  txt($('ranked'),num(s.ranked_count,0));
  txt($('branch'),s.branch_coverage==='AVAILABLE_PROVISIONAL'?'試算中':'尚無完整資料');
  if(s.branch_coverage==='AVAILABLE_PROVISIONAL')txt($('notice'),'籌碼評分為初步試算，請檢查完整性、來源合法性及歷史回測；不可當成保證勝率。');
  try{
   const full=await fetch('radar_all.json',{cache:'no-store'});if(!full.ok)throw new Error('HTTP '+full.status);
   const catalog=await full.json();
   if(!Array.isArray(catalog.stocks)||!Array.isArray(catalog.unranked))throw new Error('完整名單格式不符');
   stocks=catalog.stocks;unranked=catalog.unranked;searchReady=true;
   if(Array.isArray(catalog.score_rules))scoreRules=catalog.score_rules;
  }catch(err){
   searchReady=false;
   txt($('notice'),'完整清單暫時讀取失敗，以下僅有前50名，不能據此判斷股票沒有行情。'+err.message);
  }
  draw();
 }catch(e){txt($('asof'),'載入失敗');txt($('notice'),'讀取 report.json 失敗：'+e.message+'。請透過 GitHub Pages 瀏覽本頁，確認JSON已發布。');$('rows').replaceChildren();}
}
['q','market','sort'].forEach(id=>$(id).addEventListener(id==='q'?'input':'change',draw));load();
</script></body></html>'''