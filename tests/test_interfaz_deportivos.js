const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('index.html','utf8');
const start=html.indexOf('function officialUiCheck(t)'),end=html.indexOf('loadOfficialUi();',start);
assert(start>=0&&end>start);
const src=html.slice(start,end);
const signs=['2','X','2','2','1','X','1','2','2','2','X','X','2','1'];
const qScores=['12','11','0M','00','20','12'];
const prizes=(game,amounts)=>amounts.map((n,i)=>({product:game,category_code:i+1,category_label:'Cat '+(i+1),amount_eur:String(n)}));
const sandbox={OFFICIAL_DRAWS_UI:{
 LAQU:{'2026-11-08':{result:{quiniela_signs:signs,pleno_15:'12'},prizes:prizes('LAQU',[1647986.55,90099,1369.75,110.13,14.48,3.41])}},
 QGOL:{'2026-11-08':{result:{quinigol_scores:qScores},prizes:prizes('QGOL',[0,232.5,12.55,1.61,1.05])}}},
 ticketEntries:t=>t.entries,
 reviewNumbers062:()=>null};
vm.createContext(sandbox);vm.runInContext(src,sandbox);
const quiniela=sandbox.officialUiCheck({game:'quiniela',date:'2026-11-08',entries:[signs.join('')],extra:'1-2',modality:'simple'});
assert.equal(quiniela.state,'won');assert.equal(quiniela.prize,1647986.55);
const fourteen=sandbox.officialUiCheck({game:'quiniela',date:'2026-11-08',entries:[signs.join('')],extra:'2-M',modality:'simple'});
assert.equal(fourteen.prize,90099);
const elige=sandbox.officialUiCheck({game:'quiniela',date:'2026-11-08',entries:[signs.join('')],extra:'1-2',elige8:[0,1,2,3,4,5,6,7],modality:'simple'});
assert.equal(elige.state,'pending');
const quinigol=sandbox.officialUiCheck({game:'quinigol',date:'2026-11-08',entries:['1-2, 1-1, 0-M, 0-0, 2-0, 1-0'],modality:'simple'});
assert.equal(quinigol.state,'won');assert.equal(quinigol.prize,232.5);
const missing=sandbox.officialUiCheck({game:'quinigol',date:'2026-11-22',entries:['1-2, 1-1, 0-M, 0-0, 2-0, 1-0'],modality:'simple'});
assert.equal(missing.state,'pending');
console.log('OK: Quiniela and Quinigol official scrutiny; Elige8 remains pending');
