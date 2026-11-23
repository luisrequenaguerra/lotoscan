const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('index.html','utf8');
const start=html.indexOf('function officialUiCheck(t)'),end=html.indexOf('loadOfficialUi();',start);
assert(start>=0&&end>start);
const data=JSON.parse(fs.readFileSync('resultados/selae-interfaz.json','utf8'));
const sandbox={OFFICIAL_DRAWS_UI:data.games,ticketEntries:t=>t.entries,
reviewNumbers062:(v,count,max)=>{
 const a=Array.isArray(v)?v.map(Number):String(v??'').match(/\d+/g)?.map(Number)||[];
 return a.length===count&&new Set(a).size===count&&a.every(n=>Number.isInteger(n)&&n>=1&&n<=max)?a:null;
}};
vm.createContext(sandbox);vm.runInContext(html.slice(start,end),sandbox);
const check=t=>sandbox.officialUiCheck(t);
const categoryPairs=[[5,2],[5,1],[5,0],[4,2],[4,1],[3,2],[4,0],[2,2],[3,1],[3,0],[1,2],[2,1],[2,0]];
for(const [date,draw] of Object.entries(data.games.EMIL)){
 const win=draw.result.numbers,stars=draw.result.stars;
 const other=Array.from({length:50},(_,i)=>i+1).filter(n=>!win.includes(n));
 const otherStars=Array.from({length:12},(_,i)=>i+1).filter(n=>!stars.includes(n));
 assert.equal(draw.prizes.filter(x=>x.product==='EMIL').length,13);
 categoryPairs.forEach(([hits,starHits],i)=>{
  const nums=[...win.slice(0,hits),...other.slice(0,5-hits)];
  const picks=[...stars.slice(0,starHits),...otherStars.slice(0,2-starHits)];
  const expected=Number(draw.prizes.filter(x=>x.product==='EMIL')[i].amount_eur);
  const t={game:'euromillones',date,entries:[nums.join(' ')],extra:picks.join(' '),elMillon:'ZZZ99999'};
  const result=check(t),component=result.components?.find(x=>x.label.startsWith('Apuesta 1'));
  assert(component,'Missing prize category '+(i+1)+' on '+date);
  assert.equal(component.amount,expected,'Incorrect prize for '+(i+1)+' on '+date);
  assert.equal(result.receiptVerified,false);
  if(expected>0)assert(['won','candidate'].includes(result.state));
 });
 const lose=check({game:'euromillones',date,entries:[other.slice(0,5).join(' ')],extra:otherStars.slice(0,2).join(' '),elMillon:'ZZZ99999'});
 assert(!lose.components?.some(x=>x.label.startsWith('Apuesta 1')),'False positive on '+date);
}
console.log('OK: all 13 Euromillones categories across '+Object.keys(data.games.EMIL).length+' official draws; negative controls');
