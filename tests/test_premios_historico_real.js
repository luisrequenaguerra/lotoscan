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
 assert(['won','pending'].includes(noKey.state));
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
 assert(['won','lost','pending'].includes(result.state));
 assert.equal(result.receiptVerified,false);
}
{
 const {date,draw}=first('QUPL');
 const result=check({game:'quintuple_plus',date,racePicks:[...draw.result.races,draw.result.second_fifth_race]});
 assert.equal(result.state,'pending');
}
console.log('OK: real archived SELAE draws and Gordo zero / EuroDreams periodic prize safeguards');
