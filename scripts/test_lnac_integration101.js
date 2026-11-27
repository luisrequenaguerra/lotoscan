const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('index.html','utf8');
const scripts=[...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)].map(x=>x[1]);
for(const s of scripts)new vm.Script(s);
const source=scripts.join('\n');
function extract(name){const start=source.indexOf('function '+name+'(');assert(start>=0,name);const end=source.indexOf('\nfunction ',start+1);return source.slice(start,end<0?undefined:end).split('\nconst LNAC_TESTS_066=')[0];}
const ctx=vm.createContext({console,LNAC_FIXTURES_066:[]});
const names=['prepare113','calc113','lnacDrawName','prepare105','prepare101','calcLNAC82','calcLNAC112','calcLNAC066','registerLNAC066','checkLNAC067'];
// Extract function declarations by using a parser available in Node's bundled tooling only via syntax checks; delimit at next top-level declaration.
for(const name of names){const start=source.indexOf('function '+name+'(');assert(start>=0,name);const tail=source.slice(start);const first=tail.split('\n')[0];const match=first.endsWith('}')?[first]:tail.match(/^function [\s\S]*?\n}/);assert(match,name);vm.runInContext(match[0],ctx);}
vm.runInContext('const LNAC_DRAWS_066={};',ctx);
const start108=source.indexOf('const rules108='),end108=source.indexOf('function registerLNAC066(',start108);assert(start108>=0&&end108>start108);vm.runInContext(source.slice(start108,end108),ctx);
const manifest=JSON.parse(fs.readFileSync('resultados/lnac/manifest.json'));
let count=0;
for(const item of manifest.draws){const d=JSON.parse(fs.readFileSync(item.file));ctx.d=d;ctx.date=item.date;assert.equal(vm.runInContext('registerLNAC066(d)',ctx),item.date);const first=vm.runInContext('checkLNAC067({date,number:d.primerPremio.decimo,series:1,fraction:1})',ctx);assert.equal(first.state,'won',item.date+JSON.stringify(first));count++;}
ctx.date='2026-10-12';
for(const [number,series,fraction,state,prize] of [['77265',4,10,'won',15000000],['77265',1,1,'won',130000],['77265',null,null,'pending',null],['00000',null,null,'lost',0],['00996',null,null,'won',150]]){ctx.ticket={date:ctx.date,number,series,fraction};const result=vm.runInContext('checkLNAC067(ticket)',ctx);assert.equal(result.state,state,JSON.stringify(result));if(prize!==null)assert.equal(result.prize,prize);}
console.log('Integración LNAC OK: '+count+' sorteos registrados y casos modelo 82 superados');

const rows=(s,prize)=>s.split(' ').map(decimo=>({decimo,prize}));
const d={modelDraw:101,precioDecimo:12,premioEspecial:null,primerPremio:{decimo:'58451',prize:10000000},segundoPremio:{decimo:'64780',prize:2500000},tercerosPremios:[{decimo:'09224',prize:501200}],cuartosPremios:[],quintosPremios:[],extraccionesDeCincoCifras:[],extraccionesDeCuatroCifras:rows('1204 5649 7616 8840 9675',30000),extraccionesDeTresCifras:rows('010 086 137 198 385 411 514 585 727 753 995',6000),extraccionesDeDosCifras:rows('00 07 40 65 65 67 72 74 90',2400),reintegros:rows('1 4 3',1200)};
ctx.d={...d,fechaSorteo:'2026-01-17'};assert.equal(vm.runInContext('registerLNAC066(d)',ctx),'2026-01-17');
for(const [number,prize] of Object.entries({'58451':100000,'09224':5012,'09265':108,'00002':0})){ctx.ticket={date:'2026-01-17',number};const r=vm.runInContext('checkLNAC067(ticket)',ctx);assert.equal(r.prize,prize,JSON.stringify(r));assert.equal(r.state,prize?'won':'lost');}
ctx.d={...ctx.d,reintegros:[]};assert.throws(()=>vm.runInContext('registerLNAC066(d)',ctx));ctx.ticket={date:'2025-01-18',number:'12345'};assert.equal(vm.runInContext('checkLNAC067(ticket)',ctx).state,'pending');
console.log('Model 101 integration OK');
