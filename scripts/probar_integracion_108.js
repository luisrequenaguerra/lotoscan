const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const scripts=[...fs.readFileSync('index.html','utf8').matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)].map(m=>m[1]);
scripts.forEach((s,i)=>new vm.Script(s,{filename:'inline-'+i+'.js'}));
const source=scripts.join('\n');
function extract(name){
 const pos=source.indexOf('function '+name+'(');assert(pos>=0,name);
 const tail=source.slice(pos); const first=tail.split('\n')[0]; if(first.endsWith('}'))return first; const close=tail.indexOf('\n}'); assert(close>=0,name); return tail.slice(0,close+2);
}
const start=source.indexOf('const rules108='),end=source.indexOf('function registerLNAC066(',start);
assert(start>=0&&end>start);
const names=['prepare113','calc113','registerLNAC066','calcLNAC066','lnacDrawName','prepare105','prepare101','calcLNAC82','calcLNAC112','checkLNAC067'];
const ctx=vm.createContext({console,LNAC_FIXTURES_066:[]});
vm.runInContext('const LNAC_DRAWS_066={};\n'+source.slice(start,end)+'\n'+names.map(extract).join('\n'),ctx);
const dir=process.argv[2];
for(const year of [2024,2025]){
 ctx.d=JSON.parse(fs.readFileSync(path.join(dir,year+'.lnac108.normalizado.json')));
 assert.equal(vm.runInContext('registerLNAC066(d)',ctx),year+'-12-22');
 const calc=vm.runInContext('(n)=>calcLNAC066(d,n,null,null)',ctx);
 const label=vm.runInContext('label108',ctx);
 const rows=fs.readFileSync(path.join(dir,year+'.motor-108.jsonl'),'utf8').trim().split('\n');
 assert.equal(rows.length,100000);
 const canon=a=>a.map(x=>JSON.stringify(x)).sort().join('|');
 for(const line of rows){const r=JSON.parse(line),v=calc(r.n);assert.equal(Math.round(v.amount*100),r.cents,r.n);assert.equal(canon(v.components),canon(r.parts.map(([c,v])=>({label:label(c),amount:v/100}))),r.n);}
 console.log('INTERFAZ_108',year,rows.length,'OK');
}
const manifest=JSON.parse(fs.readFileSync('resultados/lnac/manifest.json'));
assert.equal(new Set(manifest.draws.map(x=>x.date)).size,manifest.draws.length);
for(const row of manifest.draws){ctx.d=JSON.parse(fs.readFileSync(row.file));assert.equal(vm.runInContext('registerLNAC066(d)',ctx),row.date);ctx.n=ctx.d.primerPremio.decimo;assert(vm.runInContext('calcLNAC066(d,n,1,1)',ctx).amount>0,row.date);}
console.log('REGRESION_LNAC',manifest.draws.length,'OK');

vm.runInContext(source.slice(source.indexOf('const DRAW_WEEKDAYS39='),source.indexOf('function configureDrawDate39(')),ctx);
assert(vm.runInContext("dateAllowed39('loteria_nacional','2026-12-22')",ctx));
assert(vm.runInContext("dateAllowed39('loteria_nacional','2027-12-22')",ctx));
assert(!vm.runInContext("dateAllowed39('loteria_nacional','2026-12-23')",ctx));
assert.equal(vm.runInContext("lnacDrawName('2026-12-22')",ctx),'Sorteo Extraordinario de Navidad');
for(const year of [2024,2025]){
 const rows=fs.readFileSync(path.join(dir,year+'.motor-108.jsonl'),'utf8').trim().split('\n').map(JSON.parse);
 for(const r of [rows.find(x=>x.cents===0),rows.find(x=>x.parts.some(p=>p[0]==='pedrea')),rows.find(x=>x.parts.length>1),rows.find(x=>x.n.startsWith('0')&&x.cents>0)]){
  ctx.t={date:year+'-12-22',number:r.n};
  const v=vm.runInContext('checkLNAC067(t)',ctx);
  assert.equal(v.state,r.cents?'won':'lost');assert.equal(Math.round(v.prize*100),r.cents);
 }
}
ctx.t={date:'2026-12-22',number:'12345'};
assert.equal(vm.runInContext('checkLNAC067(t)',ctx).state,'pending');
console.log('CALENDARIO_ESTADOS_108 OK');
