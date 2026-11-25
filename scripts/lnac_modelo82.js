function calcLNAC82(d,n,serie,fraccion){
 const require=(ok)=>{if(!ok)throw Error('Datos incompletos o incompatibles del modelo 82')};
 const num=(x,k)=>typeof x==='string'&&new RegExp('^[0-9]{'+k+'}$').test(x);
 require(d?.modelDraw===82&&d.precioDecimo===15&&num(n,5));
 const a=d.primerPremio.decimo,b=d.segundoPremio.decimo,e=d.premioEspecial;
 require(num(a,5)&&num(b,5)&&a!==b);
 require(['tercerosPremios','cuartosPremios','quintosPremios','extraccionesDeCincoCifras'].every(k=>Array.isArray(d[k])&&!d[k].length));
 const valid=x=>Number.isInteger(x)&&x>=1&&x<=10;
 require(e?.numero===a&&valid(e.serie)&&valid(e.fraccion));
 const groups=[['Cuatro',4,5,37500],['Tres',3,15,7500],['Dos',2,2,3000]];
 for(const [key,k,count,v] of groups){const rows=d['extraccionesDe'+key+'Cifras'];require(Array.isArray(rows)&&rows.length===count&&rows.every(x=>num(x.decimo,k)&&x.prize===v))}
 require(Array.isArray(d.reintegros)&&d.reintegros.length===3&&d.reintegros.every(x=>num(x.decimo,1)&&x.prize===1500)&&d.reintegros.some(x=>x.decimo===a.slice(-1)));
 function base(n){
  const hits=[];const add=(label,cents)=>{if(cents>0)hits.push({label,cents})};
  for(const [i,x] of [a,b].entries()){
   const label=i?'segundo':'primero';
   if(n===x)add(i?'Segundo premio':'Primer premio',i?2500000:13000000);
   if(n!==x&&n.slice(0,3)===x.slice(0,3))add('Centena '+label,7500);
   if([1,99999].includes((Number(n)-Number(x)+100000)%100000))add('Aproximación '+label,i?153250:240000);
  }
  for(const [key,k,count,v] of groups){const matches=d['extraccionesDe'+key+'Cifras'].filter(x=>x.decimo===n.slice(-k)).length;add('Extracción '+k+' cifras',matches*v)}
  for(const k of [2,3])if(n!==a&&n.slice(-k)===a.slice(-k))add('Terminación '+k+' cifras del primero',7500);
  add('Reintegro',1500*(d.reintegros.filter(x=>x.decimo===n.slice(-1)).length-(n===a?1:0)));
  return hits;
 }
 const total=h=>h.reduce((s,x)=>s+x.cents,0);
 require(total(base(a))===d.primerPremio.prize&&total(base(b))===d.segundoPremio.prize&&total(base(a))+1487000000===e.premio);
 const hits=base(n);
 if(n===a){if(!valid(serie)||!valid(fraccion))throw Error('Indica serie y fracción para comprobar el premio especial');if(serie===e.serie&&fraccion===e.fraccion)hits.push({label:'Premio especial',cents:1487000000})}
 return {amount:total(hits)/100,components:hits.map(x=>({label:x.label,amount:x.cents/100}))};
}
if(typeof module!=='undefined')module.exports={calcLNAC82};
