function prepare113(d) {
  if (!d || d.modelDraw !== 113 || d.precioDecimo !== 20 || d.premioEspecial !== null) throw Error('Modelo 113 inválido');
  const digits=(n,k)=>typeof n==='string' && n.length===k && /^[0-9]+$/.test(n);
  function item(x,k,p){if(!x || !digits(x.decimo,k) || x.prize!==p) throw Error('Premio inválido');return x.decimo;}
  function group(key,k,p,count){const a=d[key];if(!Array.isArray(a)||a.length!==count)throw Error(key);const ns=a.map(x=>item(x,k,p));if(new Set(ns).size!==count)throw Error(key);return ns;}
  const a=item(d.primerPremio,5,20000000), b=item(d.segundoPremio,5,7500000), c=group('tercerosPremios',5,2500000,1)[0];
  if(new Set([a,b,c]).size!==3)throw Error('Duplicados');
  const groups=[['extraccionesDeCuatroCifras',4,35000,2,'Extracción de cuatro cifras'],['extraccionesDeTresCifras',3,10000,14,'Extracción de tres cifras'],['extraccionesDeDosCifras',2,4000,5,'Extracción de dos cifras'],['reintegros',1,2000,3,'Reintegro']].map(([key,k,p,count,label])=>[group(key,k,p,count),p,label]);
  if(!groups[3][0].includes(a.slice(-1))||['cuartosPremios','quintosPremios','extraccionesDeCincoCifras'].some(k=>!Array.isArray(d[k])||d[k].length))throw Error('Estructura inválida');
  return n=>{if(!digits(n,5))return null;const hits=[];const add=(label,cents)=>hits.push({label,cents});
    [[a,20000000,'primer'],[b,7500000,'segundo'],[c,2500000,'tercer']].forEach(([w,p,name],i)=>{if(n===w){add(name[0].toUpperCase()+name.slice(1)+' premio',p);return;}if(n.slice(0,3)===w.slice(0,3))add('Centena del '+name+' premio',10000);if(i<2&&[1,99999].includes((Number(n)-Number(w)+100000)%100000))add('Aproximación al '+name+' premio',i===0?120000:61000);if(i<2&&n.slice(-3)===w.slice(-3))add('Tres últimas cifras del '+name+' premio',10000);if(i===0&&n.slice(-2)===w.slice(-2))add('Dos últimas cifras del primer premio',10000);});
    for(const [ns,p,label] of groups)for(const s of ns)if(n.endsWith(s)&&!(label==='Reintegro'&&n===a&&s===a.slice(-1)))add(label,p);
    return {cents:hits.reduce((s,h)=>s+h.cents,0),hits,specialPending:false};};
}
function calc113(d,n){try{return prepare113(d)(n);}catch{return null;}}
if(typeof module!=='undefined')module.exports={prepare113,calc113};
