const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('index.html','utf8');
const start=html.indexOf('function officialUiCheck(t)'),end=html.indexOf('loadOfficialUi();',start);
const data=JSON.parse(fs.readFileSync('resultados/selae-interfaz.json','utf8'));
const sandbox={OFFICIAL_DRAWS_UI:data.games,ticketEntries:t=>t.entries,
reviewNumbers062:(v,count,max)=>{
 const a=Array.isArray(v)?v.map(Number):String(v??'').match(/\d+/g)?.map(Number)||[];
 return a.length===count&&new Set(a).size===count&&a.every(n=>Number.isInteger(n)&&n>=1&&n<=max)?a:null;
}};
vm.createContext(sandbox);vm.runInContext(html.slice(start,end),sandbox);
const check=t=>sandbox.officialUiCheck(t);
for(const game of ['BONO','LAPR']){
 const [date,draw]=Object.entries(data.games[game])[0],numbers=draw.result.numbers;
 const base={game:game==='BONO'?'bonoloto':'primitiva',date,entries:[numbers.join(' ')],extra:String(draw.result.reintegro)};
 const prize=check(base);
 assert.equal(prize.receiptVerified,false);
 if(game==='LAPR'){
  assert.notEqual(prize.state,'won','Special category should not be certified without full validation');
  assert(!prize.components?.some(c=>c.label.startsWith('Reintegro')),'Special reintegro must not be duplicated');
 }
 const altered=numbers.slice();altered[0]=draw.result.complementary;
 const five=check({...base,entries:[altered.join(' ')]});
 assert.equal(five.receiptVerified,false);
 assert(!five.components?.some(c=>c.label.includes('Especial')));
}
console.log('OK: official real draw reintegro and Primitiva special category safeguards');
