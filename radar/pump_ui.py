"""Attach new rally-detection UI to the existing, independently tested V2 dashboard.

Kept separate to preserve all earlier stock search and technical score breakdowns.
"""
CSS = r"""
.pv-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin:16px 0}
.pv-mini{background:#0c1b2d;border:1px solid #30455d;border-radius:12px;padding:12px}
.pv-mini strong{display:block;font-size:26px;margin-top:6px}
.pv-head{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.pv-note{font-size:12px;line-height:1.7;color:#b0c1d7}
.pv-stage{display:inline-block;border-radius:8px;padding:5px 9px;background:#284158;color:#c7d8ee;font-size:12px;font-weight:650}
.pv-stage.START{background:#1d5b49;color:#8df1c2}
.pv-stage.EARLY{background:#224f6b;color:#a8e2ff}
.pv-stage.PREP{background:#164b5c;color:#98dfec}
.pv-stage.FOLLOW{background:#37446b;color:#c4c7ff}
.pv-stage.HOT{background:#694021;color:#ffca99}
.pv-stage.WATCH{background:#4b4852;color:#d4d4e8}
.pv-stage.NONE{background:#28384b;color:#abbfd3}
.pv-detail{margin-top:20px;background:#101e30;padding:15px;border:1px solid #30435b;border-radius:13px}
.pv-chart{overflow-x:auto;background:#081321;padding:8px;border-radius:12px;border:1px solid #334357}
.pv-chart svg{width:100%;min-width:660px;height:auto;display:block}
.pv-row:hover{background:#213a57;cursor:pointer}
.pv-stage-cell{text-align:left!important}
@media(max-width:650px){.pv-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
"""
PANEL = r"""
<section class="card" id="pv-panel" style="margin-bottom:18px">
<div class="pv-head"><h2>疑似主力拉抬・起漲雷達</h2><span class="tag">價量推升偵測｜未驗證主力身份</span></div>
<p class="pv-note">結合價量突破、成交量比、收盤強弱、均線、RSI與短期過熱檢查；找早期的起漲訊號，也把已大漲的股票另外列出，不會把所有放量股都當成買點。</p>
<div class="pv-grid">
<div class="pv-mini"><span class="muted">當日疑似啟動</span><strong id="pv-start">—</strong></div>
<div class="pv-mini"><span class="muted">初期／低量前兆</span><strong id="pv-early">—</strong></div>
<div class="pv-mini"><span class="muted">3個交易日內曾啟動</span><strong id="pv-recent">—</strong></div>
<div class="pv-mini"><span class="muted">短線過熱警示</span><strong id="pv-hot">—</strong></div>
</div>
<div class="toolbar"><select id="pv-filter" aria-label="量價推升訊號篩選">
<option value="NEW">啟動＋初期＋低量前兆</option>
<option value="PREP">低量突破前兆（較低確認度）</option>
<option value="FOLLOW">拉抬延續</option>
<option value="WATCH">觀察訊號</option>
<option value="HOT">過熱警示（非推薦）</option>
<option value="ALL">全部訊號</option>
</select></div>
<div class="scroll"><table class="stock-table"><thead><tr><th>股票</th><th>偵測階段</th><th>型態強度</th><th>量比</th><th>近5日漲幅</th><th>首次訊號日</th></tr></thead>
<tbody id="pv-list"><tr><td colspan="6">載入偵測清單中…</td></tr></tbody></table></div>
<div id="pv-msg" class="pv-note" style="margin-top:12px"></div>
</section>
"""
DETAIL = r"""
<section class="pv-detail">
<div class="pv-head"><h2>量價拉抬型態分析</h2><span id="pv-stage" class="pv-stage NONE">尚無訊號</span></div>
<p id="pv-reason" class="pv-note">選取股票後顯示判讀原因。</p>
<p id="pv-numbers" class="pv-note"></p>
<div class="pv-head"><h2>最近65根日K線與量能</h2><span class="tag">紅漲／綠跌</span></div>
<div id="pv-chart-status" class="pv-note">正在準備資料…</div>
<div class="pv-chart"><svg id="pv-chart" role="img" aria-label="價量K線及疑似拉抬訊號時間點" viewBox="0 0 1000 500"></svg></div>
<p class="pv-note">紅線：MA5｜藍線：MA20｜<span style="color:#7fe8bd">▲</span>放量啟動／初期｜<span style="color:#90d6ff">▲</span>低量突破前兆｜<span style="color:#fac178">◆</span>過熱。所有標記只採用當天及以前的行情，不是模仿圖片中無法驗證的私有指標。</p>
</section>
"""
JS = r"""
// OHLCV impulse module. JS modifies visualization, not the Python signal logic.
const PV_STAGE = {START:'疑似拉抬啟動',EARLY:'起漲初期觀察',PREP:'低量突破前兆',
 FOLLOW:'量價推升延續',WATCH:'量價異動觀察',HOT:'短線過熱勿追',NONE:'尚無訊號'};
const pvCache = new Map();
let pvFeed = {summary:{},candidates:[],overheated:[]};
let pvRequest = 0;
function pvStage(el,key){
 const stage=Object.hasOwn(PV_STAGE,String(key))?String(key):'NONE';
 el.className='pv-stage '+stage;el.textContent=PV_STAGE[stage];
}
function pvEl(tag,attrs={},textValue){
 const node=document.createElementNS('http://www.w3.org/2000/svg',tag);
 for(const [name,v] of Object.entries(attrs))node.setAttribute(name,String(v));
 if(textValue!==undefined)node.textContent=String(textValue);
 return node;
}
function pvSelectStock(x){
 const found=stocks.find(s=>String(s.code)===String(x.code)&&s.market===x.market);
 if(found)showDetail(found);
 else txt($('pv-msg'),'完整股票資料還沒載入；請稍後再點一次。');
}
function pvList(){
 const s=pvFeed.summary||{};
 for(const [id,value] of [['pv-start',s.new_start_count],['pv-early',(Number(s.new_early_count||0)+Number(s.prep_count||0))],
     ['pv-recent',s.recent_3bar_events],['pv-hot',s.hot_count]]){
   txt($(id),value===undefined?'—':num(value,0));
 }
 const filter=$('pv-filter').value;
 let items=(pvFeed.candidates||[]).concat(pvFeed.overheated||[]);
 if(filter==='NEW')items=items.filter(x=>['START','EARLY','PREP'].includes(x.impulse_signal));
 else if(filter!=='ALL')items=items.filter(x=>x.impulse_signal===filter);
 items=items.slice(0,65);
 const body=$('pv-list');body.replaceChildren();
 if(!items.length){const tr=document.createElement('tr');cell(tr,'此類別目前沒有可顯示的偵測訊號');body.append(tr);}
 for(const x of items){
  const tr=document.createElement('tr');tr.className='pv-row';tr.tabIndex=0;
  cell(tr,x.name+' ('+x.code+')');
  const td=document.createElement('td');td.className='pv-stage-cell';
  const stage=document.createElement('span');pvStage(stage,x.impulse_signal);
  td.append(stage);tr.append(td);
  cell(tr,num(x.impulse_strength,0)+'/100');
  cell(tr,num(x.impulse_volume_ratio)+'×');
  cell(tr,num(x.impulse_return5_pct)+'%');
  cell(tr,x.impulse_last_event_date||'—');
  tr.addEventListener('click',()=>pvSelectStock(x));
  tr.addEventListener('keydown',e=>{if(e.key==='Enter')pvSelectStock(x)});
  body.append(tr);
 }
 txt($('pv-msg'),'顯示 '+items.length+' 檔。低量前兆尚無量能確認；型態分數不是漲幅機率；「過熱」為風險訊號，非追價清單。');
}
function pvDrawChart(bars){
 const svg=$('pv-chart');svg.replaceChildren();
 if(!Array.isArray(bars)||bars.length<10){txt($('pv-chart-status'),'沒有足夠K線資料。');return;}
 const left=60,right=86,top=34,bottom=310,vTop=352,vBottom=453,W=1000;
 const highs=bars.map(b=>Number(b[2])).filter(Number.isFinite);
 const lows=bars.map(b=>Number(b[3])).filter(Number.isFinite);
 if(!highs.length||!lows.length){txt($('pv-chart-status'),'高低價缺漏，無法畫K線。');return;}
 const max=Math.max(...highs),min=Math.min(...lows);
 const pad=Math.max(.3,(max-min)*.075),lo=min-pad,hi=max+pad;
 const y=p=>bottom-(Number(p)-lo)/(hi-lo)*(bottom-top);
 const spacing=(W-left-right)/bars.length;
 const vmax=Math.max(1,...bars.map(b=>Number(b[5])||0));
 svg.append(pvEl('rect',{x:0,y:0,width:1000,height:500,fill:'#081321'}));
 for(let i=0;i<5;i++){
   const val=lo+(hi-lo)*i/4,Y=y(val);
   svg.append(pvEl('line',{x1:left,y1:Y,x2:W-right,y2:Y,stroke:'#294056','stroke-width':1}));
   svg.append(pvEl('text',{x:W-right+10,y:Y+5,fill:'#afc2d8','font-size':14},num(val,1)));
 }
 for(let i=0;i<bars.length;i++){
  const b=bars[i],x=left+(i+.5)*spacing;
  const [date,open,high,low,close,volume,ma5,ma20,stage,event,ratio]=b;
  if([open,high,low,close].some(v=>v===null))continue;
  const red=Number(close)>=Number(open),color=red?'#f56c79':'#4ac9a2';
  svg.append(pvEl('line',{x1:x,y1:y(high),x2:x,y2:y(low),stroke:color,'stroke-width':1.3}));
  svg.append(pvEl('rect',{x:x-Math.max(spacing*.55,2)/2,y:Math.min(y(open),y(close)),
   width:Math.max(2,spacing*.55),height:Math.max(2,Math.abs(y(open)-y(close))),fill:color}));
  const vh=(Number(volume)||0)/vmax*(vBottom-vTop),bar=pvEl('rect',{
   x:x-Math.max(spacing*.56,2)/2,y:vBottom-vh,width:Math.max(2,spacing*.56),
   height:Math.max(1,vh),fill:color,opacity:.75
  });
  bar.append(pvEl('title',{},date+' 開 '+num(open)+' 高 '+num(high)+
    ' 低 '+num(low)+' 收 '+num(close)+' 量比 '+num(ratio)));
  svg.append(bar);
  if(event===true)svg.append(pvEl('text',{x:x,y:Math.min(bottom-4,y(low)+17),
     fill:stage==='PREP'?'#90d6ff':'#8cf2c8','text-anchor':'middle','font-size':17},'▲'));
  else if(stage==='HOT')svg.append(pvEl('text',{x:x,y:Math.max(top+14,y(high)-12),
     fill:'#ffc178','text-anchor':'middle','font-size':16},'◆'));
  if(i===0||i===bars.length-1||i%10===0)
   svg.append(pvEl('text',{x:x,y:479,fill:'#9aacc2','text-anchor':'middle','font-size':12},date.slice(5)));
 }
 svg.append(pvEl('line',{x1:left,y1:vBottom+1,x2:W-right,y2:vBottom+1,stroke:'#536981'}));
 for(const [column,color] of [[6,'#fe7582'],[7,'#50c1e2']]){
   // Split line when MA is missing: no invented connection across gaps.
   let points=[];
   const flush=()=>{if(points.length>=2)svg.append(
     pvEl('polyline',{points:points.join(' '),fill:'none',stroke:color,
       'stroke-width':2.1,'stroke-linejoin':'round'}));points=[]};
   bars.forEach((b,i)=>{
     if(b[column]===null){flush();return;}
     points.push((left+(i+.5)*spacing).toFixed(1)+','+y(b[column]).toFixed(1));
   });
   flush();
 }
 svg.append(pvEl('text',{x:left,y:22,fill:'#b3c5dc','font-size':15},
   '日K圖｜近'+bars.length+'個交易日'));
 svg.append(pvEl('text',{x:W-right+8,y:vBottom,fill:'#9aacc2','font-size':13},
   num(vmax/1e6,1)+'M'));
}
async function pvChart(x){
 const req=++pvRequest;
 const svg=$('pv-chart');svg.replaceChildren();
 txt($('pv-chart-status'),'正在讀取 '+x.name+' 的歷史K線…');
 if(!/^\d{4}$/.test(String(x.code))||!['TWSE','TPEX'].includes(String(x.market))){
  txt($('pv-chart-status'),'股票代號或市場暫不支援歷史K線。');return;
 }
 const shard=String(x.market)+'-'+String(x.code).slice(0,1);
 try{
   let json=pvCache.get(shard);
   if(!json){
     const res=await fetch('charts/'+shard+'.json',{cache:'no-store'});
     if(!res.ok)throw new Error('HTTP '+res.status);
     json=await res.json();pvCache.set(shard,json);
   }
   if(req!==pvRequest)return;
   const bars=json.stocks?.[String(x.code)];
   if(!bars){txt($('pv-chart-status'),'該股票尚未輸出K線圖，請等下一次掃描。');return;}
   txt($('pv-chart-status'),'行情截至 '+json.latest_data_date+
     '｜'+bars.length+'根日K；三角形為當日疑似推升起點，菱形為短線過熱。');
   pvDrawChart(bars);
 }catch(err){
   if(req===pvRequest)txt($('pv-chart-status'),'讀取K線失敗：'+err.message);
 }
}
function pvShowDetail(x){
 pvStage($('pv-stage'),x.impulse_signal);
 txt($('pv-reason'),(x.impulse_reason||'本股票目前尚無量價異動說明。')+
    (x.impulse_risk_flags?' 風險：'+x.impulse_risk_flags+'。':''));
 txt($('pv-numbers'),'推升型態強度 '+num(x.impulse_strength,0)+'/100（非勝率）'+
    '｜當日漲幅 '+num(x.impulse_return1_pct)+'%'+
    '｜5日漲幅 '+num(x.impulse_return5_pct)+'%'+
    '｜量比 '+num(x.impulse_volume_ratio)+'×'+
    '｜最近觸發 '+(x.impulse_last_event_date||'無')+
    '｜距離起點 '+(x.impulse_age_bars==null?'—':x.impulse_age_bars+'個交易日'));
 pvChart(x);
}
const _pvOriginalShowDetail=showDetail;
showDetail=function(x){_pvOriginalShowDetail(x);pvShowDetail(x)};
$('pv-filter').addEventListener('change',pvList);
(async()=>{
 try{
  const response=await fetch('impulse.json',{cache:'no-store'});
  if(!response.ok)throw new Error('HTTP '+response.status);
  pvFeed=await response.json();
  pvList();
 }catch(err){
  $('pv-list').replaceChildren();
  txt($('pv-msg'),'尚未載入本日量價型態分析：'+err.message);
 }
})();
"""

def augment_dashboard(html):
    assert "</style>" in html and "</script>" in html
    assert '<section class="card"><h2>技術起漲觀察榜' in html
    assert '<div class="score-heading"><h2>技術分數細項分析' in html
    html = html.replace("</style>", CSS + "\n</style>", 1)
    html = html.replace(
        '<section class="card"><h2>技術起漲觀察榜',
        PANEL + '\n<section class="card"><h2>技術起漲觀察榜', 1
    )
    html = html.replace(
        '<div class="score-heading"><h2>技術分數細項分析',
        DETAIL + '\n<div class="score-heading"><h2>技術分數細項分析', 1
    )
    html = html.replace("</script>", JS + "\n</script>", 1)
    html = html.replace("V2 技術 × 分點觀察", "V3 技術 × 疑似資金推升", 1)
    return html
