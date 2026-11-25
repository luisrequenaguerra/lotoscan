const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('index.html','utf8');
const scripts=[...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)].map(x=>x[1]);
for(const s of scripts)new vm.Script(s);
const source=scripts.join('\n');
function extract(name){const start=source.indexOf('function '+name+'(');assert(start>=0,name);const end=source.indexOf('\nfunction ',start+1);return source.slice(start,end<0?undefined:end).split('\nconst LNAC_TESTS_066=')[0];}
const ctx=vm.createContext({console});
const names=['calcLNAC82','calcLNAC112','calcLNAC066','registerLNAC066','checkLNAC067'];
// Extract function declarations by using a parser available in Node's bundled tooling only via syntax checks; delimit at next top-level declaration.
for(const name of names){const start=source.indexOf('function '+name+'(');assert(start>=0,name);const tail=source.slice(start);const match=tail.match(/^function [\s\S]*?\n}/);assert(match,name);vm.runInContext(match[0],ctx);}
vm.runInContext('const LNAC_DRAWS_066={};',ctx);
const manifest=JSON.parse(fs.readFileSync('resultados/lnac/manifest.json'));
let count=0;
for(const item of manifest.draws){const d=JSON.parse(fs.readFileSync(item.file));ctx.d=d;ctx.date=item.date;assert.equal(vm.runInContext('registerLNAC066(d)',ctx),item.date);const first=vm.runInContext('checkLNAC067({date,number:d.primerPremio.decimo,series:1,fraction:1})',ctx);assert.equal(first.state,'won',item.date+JSON.stringify(first));count++;}
ctx.date='2026-10-12';
for(const [number,series,fraction,state,prize] of [['77265',4,10,'won',15000000],['77265',1,1,'won',130000],['77265',null,null,'pending',null],['00000',null,null,'lost',0],['00996',null,null,'won',150]]){ctx.ticket={date:ctx.date,number,series,fraction};const result=vm.runInContext('checkLNAC067(ticket)',ctx);assert.equal(result.state,state,JSON.stringify(result));if(prize!==null)assert.equal(result.prize,prize);}
console.log('Integración LNAC OK: '+count+' sorteos registrados y casos modelo 82 superados');
