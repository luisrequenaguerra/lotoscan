const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('index.html','utf8');
const start=html.indexOf('function officialUiCheck(t)'),end=html.indexOf('loadOfficialUi();',start);
assert(start>=0&&end>start);
const src=html.slice(start,end);
function draw(game,numbers,extra,amounts){
 return {result:{numbers,...(game==='ELGR'?{key_number:extra}:{dream:extra})},
  prizes:amounts.map((amount,i)=>({product:game,category_code:i+1,category_label:'Cat '+(i+1),amount_eur:String(amount)}))};
}
const sandbox={OFFICIAL_DRAWS_UI:{
 ELGR:{'2026-11-22':draw('ELGR',[9,13,16,19,45],6,[0,82537.77,714.61,132.14,30.2,11.08,5.45,3,1.5])},
 EDMS:{'2026-11-23':draw('EDMS',[5,8,18,24,27,39],2,[0,120000,421.85,28.53,4.49,2.5])}},
 ticketEntries:t=>t.entries,
 reviewNumbers062:(v,count,max)=>{const a=String(v??'').match(/\d+/g)?.map(Number)||[];return a.length===count&&new Set(a).size===count&&a.every(n=>Number.isInteger(n)&&n>=1&&n<=max)?a:null}};
vm.createContext(sandbox);vm.runInContext(src,sandbox);
const gordo=sandbox.officialUiCheck({game:'gordo',date:'2026-11-22',entries:['09 13 16 19 45'],extra:'3'});
assert.equal(gordo.state,'won');assert.equal(gordo.prize,82537.77);assert.equal(gordo.receiptVerified,false);
const dream=sandbox.officialUiCheck({game:'eurodreams',date:'2026-11-23',entries:['05 08 18 24 27 31'],extra:'4'});
assert.equal(dream.state,'won');assert.equal(dream.prize,421.85);
const missing=sandbox.officialUiCheck({game:'eurodreams',date:'2026-11-23',entries:['05 08 18 24 27 31'],extra:''});
assert.equal(missing.state,'pending');
const noPrize=sandbox.officialUiCheck({game:'eurodreams',date:'2026-11-23',entries:['01 02 03 04 06 07'],extra:'1'});
assert.equal(noPrize.state,'lost');
console.log('OK: Gordo and EuroDreams official prize checks');
