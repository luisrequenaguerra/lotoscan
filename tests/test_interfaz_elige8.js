const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('index.html','utf8');
const start=html.indexOf('function officialUiCheck(t)'),end=html.indexOf('loadOfficialUi();',start);
assert(start>=0&&end>start);
const signs=['2','X','2','2','1','X','1','2','2','2','X','X','2','1'];
const prizes=(product,amounts)=>amounts.map((n,i)=>({product,category_code:i+1,category_label:'Cat '+(i+1),amount_eur:String(n)}));
const sandbox={OFFICIAL_DRAWS_UI:{LAQU:{'2026-11-08':{
 result:{quiniela_signs:signs,pleno_15:'12',elige8:{activo:'1',gameid:'ELG8'}},
 prizes:[...prizes('LAQU',[1647986.55,90099,1369.75,110.13,14.48,3.41]),...prizes('ELIGE8',[214.66])]
}}},ticketEntries:t=>t.entries,reviewNumbers062:()=>null};
vm.createContext(sandbox);vm.runInContext(html.slice(start,end),sandbox);
const base={game:'quiniela',date:'2026-11-08',entries:[signs.join('')],extra:'1-2',modality:'simple'};
const winning=sandbox.officialUiCheck({...base,elige8:[0,1,2,3,4,5,6,7]});
assert.equal(winning.state,'won');assert.equal(winning.prize,1648201.21);
assert.equal(winning.components.length,2);
const missing=sandbox.officialUiCheck({...base,elige8:[0,1,2]});
assert.equal(missing.state,'pending');
const noElige=sandbox.officialUiCheck(base);
assert.equal(noElige.prize,1647986.55);
const modified=signs.slice();modified[0]='1';
const partial=sandbox.officialUiCheck({...base,entries:[modified.join('')],elige8:[0,1,2,3,4,5,6,7]});
assert.equal(partial.state,'won');assert.equal(partial.prize,90099);
console.log('OK: Elige8 eight-hit prize, no duplicate, incomplete guard');
