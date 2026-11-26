'use strict';
function prepare105(d){
 const valid=(x,w)=>typeof x?.decimo==='string'&&new RegExp('^\\d{'+w+'}$').test(x.decimo);
 if(d?.modelDraw!==105||d.precioDecimo!==20||!Array.isArray(d.tercerosPremios)||d.tercerosPremios.length!==1)throw Error('Modelo incompleto');
 const p=[d.primerPremio,d.segundoPremio,d.tercerosPremios[0]];
 if(!p.every(x=>valid(x,5))||new Set(p.map(x=>x.decimo)).size!==3)throw Error('Premios principales');
 for(const k of ['cuartosPremios','quintosPremios','extraccionesDeCincoCifras','extraccionesDeCuatroCifras'])if(!Array.isArray(d[k])||d[k].length)throw Error(k);
 const groups=[['extraccionesDeTresCifras',3,8,10000],['extraccionesDeDosCifras',2,4,4000],['reintegros',1,3,2000]];
 for(const [k,w,count,a] of groups)if(!Array.isArray(d[k])||d[k].length!==count||!d[k].every(x=>valid(x,w)&&x.prize===a))throw Error(k);
 const nums=p.map(x=>x.decimo),first=nums[0],refunds=d.reintegros.map(x=>x.decimo);
 const idx=refunds.indexOf(first.slice(-1));if(idx<0)throw Error('Reintegro primero');refunds.splice(idx,1);
 // SELAE resultados2 special prize: numero, serie, fraccion, premio (total cents).
 const special=d.premioEspecial;
 if(special?.numero!==first||special.premio!==2000000000||!Number.isInteger(special.serie)||special.serie<1||special.serie>10||!Number.isInteger(special.fraccion)||special.fraccion<1||special.fraccion>10)throw Error('Premio especial incompleto');
 function calc(n,serie=null,fraccion=null){
 if(typeof n!=='string'||!/^\d{5}$/.test(n))return null;
 const hits=[],add=(label,cents)=>hits.push({label,cents});
 nums.forEach((v,i)=>{
 if(n===v)add('Premio '+(i+1),[20000000,6000000,2000000][i]);
 else {
 if(n.slice(0,3)===v.slice(0,3))add('Centena '+(i+1),[10000,5000,5000][i]);
 if(i<2&&[1,99999].includes((Number(n)-Number(v)+100000)%100000))add('Aproximación '+(i+1),[80000,43000][i]);
 if(i<2&&n.slice(-3)===v.slice(-3))add('Terminación '+(i+1)+' 3',10000);
 }});
 if(n!==first)for(const [w,a] of [[2,4000],[1,2000]])if(n.slice(-w)===first.slice(-w))add('Terminación primero '+w,a);
 for(const [k,w,,a] of groups.slice(0,2))for(const x of d[k])if(n.endsWith(x.decimo))add('Extracción '+w,a);
 for(const r of refunds)if(n.endsWith(r))add('Reintegro adicional',2000);
 const validPart=x=>Number.isInteger(x)&&x>=1&&x<=10;
 if((serie!==null&&!validPart(serie))||(fraccion!==null&&!validPart(fraccion)))return null;
 const specialPending=n===first&&(serie===null||fraccion===null)&&(serie===null||serie===special.serie)&&(fraccion===null||fraccion===special.fraccion);
 if(n===first&&serie===special.serie&&fraccion===special.fraccion)add('Premio especial',special.premio-20000000);
 return {cents:hits.reduce((s,h)=>s+h.cents,0),hits,specialPending};
 }
 if(p.some(x=>calc(x.decimo).cents!==x.prize))throw Error('Importes principales incoherentes');
 return calc;
}
function calc105(d,n,serie=null,fraccion=null){try{return prepare105(d)(n,serie,fraccion)}catch{return null}}
if(typeof module!=='undefined')module.exports={prepare105,calc105};
