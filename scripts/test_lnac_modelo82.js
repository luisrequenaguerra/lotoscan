const assert=require('node:assert/strict');
const {calcLNAC82}=require('./lnac_modelo82');
const rows=(s,prize)=>s.split(' ').map(decimo=>({decimo,prize}));
const cases=[
['77265','43526',4,10,'0504 4880 5304 6938 9736','084 229 432 542 564 566 677 710 811 834 857 888 979 996 996','19 45','5 9 3','4880:3750 710:750 811:750 432:750 542:750 3:150 0504:3750 5304:3750 084:750 564:750 834:750 265:1650 45:450 65:900 5:150 9736:3750 566:750 996:1500 677:750 857:750 6938:3750 888:750 229:900 979:900 19:450 9:150',2500000],
['34302','73943',6,10,'0517 2146 4396 8174 8240','051 162 166 192 217 288 354 375 390 442 483 589 613 629 794','14 98','2 6 3','8240:3750 390:750 051:750 162:900 192:900 302:1650 442:900 02:900 2:150 483:900 613:900 3:150 8174:3750 354:750 794:750 14:300 375:750 2146:3900 4396:3900 166:900 6:150 0517:3750 217:750 288:750 98:300 589:750 629:750',2501500]
];
for(const [a,b,serie,fraccion,four,three,two,rein,table,second] of cases){
 const d={modelDraw:82,precioDecimo:15,primerPremio:{decimo:a,prize:13000000},segundoPremio:{decimo:b,prize:second},premioEspecial:{numero:a,serie,fraccion,premio:1500000000},tercerosPremios:[],cuartosPremios:[],quintosPremios:[],extraccionesDeCincoCifras:[],extraccionesDeCuatroCifras:rows(four,37500),extraccionesDeTresCifras:rows(three,7500),extraccionesDeDosCifras:rows(two,3000),reintegros:rows(rein,1500)};
 const suffix=new Map(table.split(' ').map(x=>{const [k,v]=x.split(':');return [k,Number(v)*10]}));
 let sum=0;
 for(let i=0;i<100000;i++){
  const n=String(i).padStart(5,'0');
  let expected=0;for(let k=4;k>=1;k--)if(suffix.has(n.slice(-k))){expected=suffix.get(n.slice(-k));break}
  for(const [x,v,p] of [[a,240000,13000000],[b,153250,second]]){
   if(n===x){expected=p;break}
   if(n.slice(0,3)===x.slice(0,3))expected+=7500;
   if(Math.abs(i-Number(x))===1)expected+=v;
  }
  const actual=Math.round(calcLNAC82(d,n,1,1).amount*100);
  assert.equal(actual,expected,n);sum+=actual;
 }
 // Total en céntimos por 100.000 décimos (sin premio especial), no por billetes de diez décimos.
 assert.equal(sum,90130000);
 for(let s=1;s<=10;s++)for(let f=1;f<=10;f++)assert.equal(calcLNAC82(d,a,s,f).amount,s===serie&&f===fraccion?15000000:130000);
 assert.throws(()=>calcLNAC82(d,a));
 console.log(a,'100000 números y 100 series/fracciones OK');
}
