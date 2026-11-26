const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('index.html','utf8');
for(const m of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi))new vm.Script(m[1]);
const start=html.indexOf('const LNAC_FIXTURES_066='),end=html.indexOf('async function importLNAC066',start);
assert(start>=0&&end>start);
const ctx=vm.createContext({});vm.runInContext(html.slice(start,end),ctx);
const manifest=JSON.parse(fs.readFileSync('resultados/lnac/manifest.json'));
for(const item of manifest.draws){const d=JSON.parse(fs.readFileSync(item.file));ctx.d=d;assert.equal(vm.runInContext('registerLNAC066(d)',ctx),item.date);}
const date='2026-07-04';ctx.t={date,number:'70334',series:6,fraction:1};
const check=()=>vm.runInContext('checkLNAC067(t)',ctx);
assert.equal(check().prize,20000000);
ctx.t.fraction=2;assert.equal(check().prize,200000);
delete ctx.t.fraction;assert.equal(check().state,'pending');
ctx.t.number='61957';assert.equal(check().prize,60000);
ctx.t.number='45794';assert.equal(check().prize,20020);
console.log('Integration: scripts parse, '+manifest.draws.length+' manifest entries registered, model 105 special and ordinary checks passed');
