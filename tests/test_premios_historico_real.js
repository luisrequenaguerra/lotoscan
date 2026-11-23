const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('index.html','utf8');
const start=html.indexOf('function officialUiCheck(t)'),end=html.indexOf('loadOfficialUi();',start);
assert(start>=0&&end>start);
const data=JSON.parse(fs.readFileSync('resultados/selae-interfaz.json','utf8'));
const sandbox={OFFICIAL_DRAWS_UI:data.games,
 ticketEntries:t=>t.entries,
 reviewNumbers062:(v,count,max)=>{
  const a=Array.isArray(v)?v.map(Number):String(v??'').match(/\d+/g)?.map(Number)||[];
  return a.length===count&&new Set(a).size===count&&a.every(n=>Number.isInteger(n)&&n>=1&&n<=max)?a:null;
 }};
vm.createContext(sandbox);vm.runInContext(html.slice(start,end),sandbox);
const check=t=>sandbox.officialUiCheck({...t,modality:'simple'});
function first(game){const [date,draw]=Object.entries(data.games[game])[0];assert(draw,game+' missing');return {date,draw}}
{
 const {date,draw}=first('ELGR'),winning=draw.result.numbers;
 const noKey=sandbox.officialUiCheck({game:'gordo',date,entries:[winning.join(' ')],extra:String(draw.result.key_number)});
 assert(['won','pending','matched_unpaid'].includes(noKey.state));
 const copy=JSON.parse(JSON.stringify(draw)),old=data.games.ELGR[date];
 copy.result.key_number=0;copy.prizes[0].amount_eur='1000';copy.prizes[0].winners='1';
 data.games.ELGR[date]=copy;
 const zero=check({game:'gordo',date,entries:[winning.join(' ')],extra:'0'});
 assert.equal(zero.state,'won');assert.equal(zero.prize,1000);
 data.games.ELGR[date]=old;
}
{
 const {date,draw}=first('EDMS'),winning=draw.result.numbers;
 const copy=JSON.parse(JSON.stringify(draw)),old=data.games.EDMS[date];
 copy.prizes[0].amount_eur='20000';copy.prizes[0].winners='1';
 data.games.EDMS[date]=copy;
 const annuity=check({game:'eurodreams',date,entries:[winning.join(' ')],extra:String(draw.result.dream)});
 assert.equal(annuity.state,'pending');
 assert.match(annuity.message,/periódico/);
 data.games.EDMS[date]=old;
}
{
 const {date,draw}=first('LAQU');
 const t={game:'quiniela',date,entries:[draw.result.quiniela_signs.join('')],extra:draw.result.pleno_15,elige8:[0,1,2,3,4,5,6,7]};
 const result=check(t);
 assert.equal(result.state,'won');assert.equal(result.prize>0,true);
}
{
 const {date,draw}=first('QGOL');
 const result=check({game:'quinigol',date,entries:[draw.result.quinigol_scores.map(x=>x[0]+'-'+x[1]).join(', ')]});
 assert(['won','lost','pending','matched_unpaid'].includes(result.state));
 assert.equal(result.receiptVerified,false);
}
{
 const {date,draw}=first('QUPL');
 const result=check({game:'quintuple_plus',date,racePicks:[...draw.result.races,draw.result.second_fifth_race]});
 const firstPrize=draw.prizes.find(r=>r.product==='QUPL'&&Number(r.category_code)===2);
 if(firstPrize&&String(firstPrize.winners)==='0'&&Number(firstPrize.amount_eur)===0){
  assert.equal(result.state,'matched_unpaid');
  assert.equal(result.prize,0);
 }else assert.equal(result.state,'pending');
}
console.log('OK: real archived SELAE draws and Gordo zero / EuroDreams periodic prize safeguards');

for(const [key,game] of [['BONO','bonoloto'],['LAPR','primitiva'],['EMIL','euromillones'],['ELGR','gordo'],['EDMS','eurodreams'],['LAQU','quiniela'],['QGOL','quinigol'],['LOTU','lototurf'],['QUPL','quintuple_plus']]){
 const {date,draw}=first(key),copy=JSON.parse(JSON.stringify(draw)),r=copy.result;
 const t={game,date,entries:[(r.numbers||[]).join(' ')],extra:String((Number(r.reintegro)+1)%10)};
 let cat=1;
 if(key==='LAPR')cat=2;
 if(key==='EMIL'){t.extra=r.stars.join(' ');t.elMillon=r.millon.combinacion==='ZZZ99999'?'AAA00000':'ZZZ99999'}
 if(key==='ELGR')t.extra=String(r.key_number);
 if(key==='EDMS')t.extra=String(r.dream);
 if(key==='LAQU'){t.entries=[r.quiniela_signs.join('')];t.extra=r.pleno_15}
 if(key==='QGOL')t.entries=[r.quinigol_scores.map(x=>String(x).replace('-','').split('').join('-')).join(', ')];
 if(key==='LOTU'){t.horse=String(r.complementary);t.reintegro=t.extra}
 if(key==='QUPL'){cat=2;t.racePicks=[...r.races,r.second_fifth_race]}
 const row=copy.prizes.find(x=>x.product===key&&Number(x.category_code)===cat);
 assert(row,key+' category missing');
 row.amount_eur='0';row.winners='0';data.games[key][date]=copy;
 assert.equal(check(t).state,'matched_unpaid',key+' zero winners');
 row.winners=null;
 assert.equal(check(t).state,'pending',key+' unknown winners');
 data.games[key][date]=draw;
}
const real=data.games.BONO['2026-11-23'];
if(real){
 const result=check({game:'bonoloto',date:'2026-11-23',entries:['08 15 16 21 34 36'],extra:'05'});
 assert.equal(result.state,'matched_unpaid');
}
