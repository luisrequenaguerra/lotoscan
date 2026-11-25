'use strict';
function prepare101(d){
 const valid=(x,k)=>typeof x?.decimo==='string'&&new RegExp('^\\d{'+k+'}$').test(x.decimo);
 if(d?.modelDraw!==101||d.precioDecimo!==12||d.premioEspecial!==null||!Array.isArray(d.tercerosPremios)||d.tercerosPremios.length!==1)throw Error('Modelo incompleto');
 const p=[d.primerPremio,d.segundoPremio,d.tercerosPremios[0]];
 if(!p.every(x=>valid(x,5))||new Set(p.map(x=>x.decimo)).size!==3)throw Error('Premios principales');
 for(const k of ['cuartosPremios','quintosPremios','extraccionesDeCincoCifras'])if(!Array.isArray(d[k])||d[k].length)throw Error(k);
 const groups=[['extraccionesDeCuatroCifras',4,5,30000],['extraccionesDeTresCifras',3,11,6000],['extraccionesDeDosCifras',2,9,2400],['reintegros',1,3,1200]];
 for(const [k,w,count,amount] of groups)if(!Array.isArray(d[k])||d[k].length!==count||!d[k].every(x=>valid(x,w)&&x.prize===amount))throw Error(k);
 const nums=p.map(x=>x.decimo), first=nums[0], refunds=d.reintegros.map(x=>x.decimo); const idx=refunds.indexOf(first.slice(-1));if(idx<0)throw Error('Reintegro primero');refunds.splice(idx,1);
 function calc(n){if(typeof n!=='string'||!/^\d{5}$/.test(n))return null;const hits=[];const add=(label,cents)=>hits.push({label,cents});
 nums.forEach((v,i)=>{if(n===v)add('Premio '+(i+1),[10000000,2500000,500000][i]);else {if(n.slice(0,3)===v.slice(0,3))add('Centena '+(i+1),6000);if(i<2&&[1,99999].includes((Number(n)-Number(v)+100000)%100000))add('Aproximación '+(i+1),[173000,90800][i]);}});
 if(n!==first)for(const [w,a] of [[3,6000],[2,2400],[1,1200]])if(n.slice(-w)===first.slice(-w))add('Terminación primero '+w,a);
 for(const [k,w,,a] of groups.slice(0,3))for(const x of d[k])if(n.endsWith(x.decimo))add('Extracción '+w,a);
 for(const r of refunds)if(n.endsWith(r))add('Reintegro adicional',1200);
 return {cents:hits.reduce((s,h)=>s+h.cents,0),hits};}
 if(p.some(x=>calc(x.decimo).cents!==x.prize))throw Error('Importes principales incoherentes');return calc;
}
function calc101(d,n){try{return prepare101(d)(n)}catch{return null}}
if(typeof module!=='undefined')module.exports={prepare101,calc101};
