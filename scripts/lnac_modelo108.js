"use strict";
const rules={primer_premio:[1,40000000,200000],segundo_premio:[1,12500000,125000],tercer_premio:[1,5000000,96000],cuarto_premio:[2,2000000,0],quinto_premio:[8,600000,0]};
function prepare108(majors,pedreas){
 const keys=Object.keys(majors), valid=n=>typeof n==="string"&&/^[0-9]{5}$/.test(n);
 if(keys.length!==13||!Array.isArray(pedreas)||pedreas.length!==1794||new Set(pedreas).size!==1794||!keys.concat(pedreas).every(valid)||pedreas.some(n=>Object.hasOwn(majors,n)))throw Error("Extracciones inválidas");
 const counts={}, draws=keys.map(n=>{const a=majors[n];if(!Array.isArray(a)||a.length!==1||!Object.hasOwn(rules,a[0].categoria))throw Error("Categoría inválida");const c=a[0].categoria;counts[c]=(counts[c]||0)+1;return {n,i:Number(n),c};});
 for(const c of Object.keys(rules))if(counts[c]!==rules[c][0])throw Error("Recuento inválido");
 return {draws,pedreas:new Set(pedreas)};
}
function calc108(prepared,n){
 if(typeof n!=="string"||!/^[0-9]{5}$/.test(n))throw Error("Número inválido");
 const i=Number(n),parts=[];
 if(prepared.pedreas.has(n))parts.push(["pedrea",10000]);
 for(const d of prepared.draws){
  const [count,base,approx]=rules[d.c];
  if(i===d.i){parts.push([d.c,base]);continue;}
  if(approx){
   if((i+1)%100000===d.i||(i+99999)%100000===d.i)parts.push(["aproximacion_"+d.c,approx]);
   if(i%100===d.i%100)parts.push(["terminacion_"+d.c,10000]);
  }
  if(d.c!=="quinto_premio"&&Math.floor(i/100)===Math.floor(d.i/100))parts.push(["centena_"+d.c,10000]);
  if(d.c==="primer_premio"&&i%10===d.i%10)parts.push(["reintegro",2000]);
 }
 return {cents:parts.reduce((s,p)=>s+p[1],0),parts};
}
if(typeof module!=="undefined")module.exports={prepare108,calc108};
