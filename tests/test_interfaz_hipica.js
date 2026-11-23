const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('index.html','utf8');
const start=html.indexOf('function officialUiCheck(t)'),end=html.indexOf('loadOfficialUi();',start);
assert(start>=0&&end>start);
const src=html.slice(start,end);
function draw(game,result,amounts){
 return {result,prizes:amounts.map((a,i)=>({product:game,category_code:i+1,category_label:'Categoría '+(i+1),amount_eur:String(a)}))};
}
const sandbox={OFFICIAL_DRAWS_UI:{
 LOTU:{'2026-11-22':draw('LOTU',{numbers:[14,16,19,22,28,30],complementary:2,reintegro:6},[0,0,964,257.07,31.61,8.14,4.69,1])},
 QUPL:{'2026-11-22':draw('QUPL',{races:[4,2,10,2,11],second_fifth_race:7},[0,0,0,0,781.97])}},
 ticketEntries:t=>t.entries,
 reviewNumbers062:(v,count,max)=>{const a=String(v??'').match(/\d+/g)?.map(Number)||[];return a.length===count&&new Set(a).size===count&&a.every(n=>Number.isInteger(n)&&n>=1&&n<=max)?a:null}};
vm.createContext(sandbox);vm.runInContext(src,sandbox);
const lotu=sandbox.officialUiCheck({game:'lototurf',date:'2026-11-22',entries:['14 16 19 22 28 01'],horse:'2',reintegro:'6',modality:'simple'});
assert.equal(lotu.state,'won');assert.equal(lotu.prize,965);assert.equal(lotu.receiptVerified,false);
const refund=sandbox.officialUiCheck({game:'lototurf',date:'2026-11-22',entries:['01 03 05 07 09 11'],horse:'4',reintegro:'6',modality:'simple'});
assert.equal(refund.state,'won');assert.equal(refund.prize,1);
const missing=sandbox.officialUiCheck({game:'lototurf',date:'2026-11-22',entries:['01 03 05 07 09 11'],horse:'4',modality:'simple'});
assert.equal(missing.state,'pending');
const quintuple=sandbox.officialUiCheck({game:'quintuple_plus',date:'2026-11-22',racePicks:[4,2,10,2,3,6],modality:'simple'});
assert.equal(quintuple.state,'won');assert.equal(quintuple.prize,781.97);
const special=sandbox.officialUiCheck({game:'quintuple_plus',date:'2026-11-22',racePicks:[4,2,10,2,11,7],modality:'simple'});
assert.equal(special.state,'pending');
console.log('OK: Lototurf and Quintuple Plus conservative prize checks');
