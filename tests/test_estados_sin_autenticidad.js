const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('index.html','utf8'),start=html.indexOf('function officialUiCheck(t)'),end=html.indexOf('loadOfficialUi();',start);
assert(start>=0&&end>start);
const data=JSON.parse(fs.readFileSync('resultados/selae-interfaz.json','utf8'));
const sandbox={OFFICIAL_DRAWS_UI:data.games,ticketEntries:t=>t.entries,reviewNumbers062:(v,count,max)=>{
 const a=Array.isArray(v)?v.map(Number):String(v??'').match(/\\d+/g)?.map(Number)||[];
 return a.length===count&&new Set(a).size===count&&a.every(n=>Number.isInteger(n)&&n>=1&&n<=max)?a:null;
}};
vm.createContext(sandbox);vm.runInContext(html.slice(start,end),sandbox);
const check=t=>sandbox.officialUiCheck(t);
const ticket=(game,date,draw)=>{
 const win=draw.result.numbers;
 const nums=Array.from({length:49},(_,i)=>i+1).filter(n=>!win.includes(n)&&n!==draw.result.complementary).slice(0,6);
 assert.equal(nums.length,6);
 const rein=String((Number(draw.result.reintegro)+1)%10);
 return {game,date,entries:[nums.join(' ')],extra:rein};
};
for(const [key,game] of [['BONO','bonoloto'],['LAPR','primitiva']]){
 const item=Object.entries(data.games[key]).find(([date,draw])=>Array.isArray(draw.result.numbers)&&Number.isInteger(draw.result.reintegro)&&draw.prizes?.length);
 assert(item,key+' fixture missing');
 const [date,draw]=item;
 const base=ticket(game,date,draw);
 const none=check(base);
 assert.equal(none.state,'lost',key+' losing ticket should be complete');
 assert(!/autentic|resguardo|participaci[oó]n/i.test(none.message),key+' should not show authentication warning');
 const withRefund=check({...base,extra:String(draw.result.reintegro)});
 assert.equal(withRefund.receiptVerified,false);
 assert(withRefund.components?.some(c=>c.label.startsWith('Reintegro')),key+' refund must be computed');
 assert.equal(withRefund.state,'won',key+' single bet with matching refund should be won');
 if(key==='LAPR'){
  const winner=String(draw.result.joker?.combinacion??'').padStart(7,'0');
  if(/^\\d{7}$/.test(winner)){
   const first=String((Number(winner[0])+1)%10),last=String((Number(winner[6])+1)%10);
   const noJoker=check({...base,joker:first+'00000'+last});
   assert.equal(noJoker.state,'lost','Nonmatching Joker should not create pending state');
   const yesJoker=check({...base,joker:winner});
   assert.equal(yesJoker.state,'won','Winning Joker should be calculable');
  }
 }
}
console.log('OK: losing, refund and Joker states independent of ticket authentication');
