const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const scripts=[...fs.readFileSync('index.html','utf8').matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)].map(m=>m[1]);
scripts.forEach((s,i)=>new vm.Script(s,{filename:'inline-'+i+'.js'}));
const source=scripts.join('\n');
function extract(name){
 const pos=source.indexOf('function '+name+'(');assert(pos>=0,name);
 const next=source.indexOf('\nfunction ',pos+1);assert(next>pos,name);
 const chunk=source.slice(pos,next),close=chunk.lastIndexOf('\n}');
 return close>=0?chunk.slice(0,close+2):chunk.split('\n')[0];
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
