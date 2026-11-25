const assert=require('node:assert/strict');
const {prepare101,calc101}=require('./lnac_modelo101');
const rows=(s,prize)=>s.split(' ').map(decimo=>({decimo,prize}));
const d={modelDraw:101,precioDecimo:12,premioEspecial:null,primerPremio:{decimo:'58451',prize:10000000},segundoPremio:{decimo:'64780',prize:2500000},tercerosPremios:[{decimo:'09224',prize:501200}],cuartosPremios:[],quintosPremios:[],extraccionesDeCincoCifras:[],extraccionesDeCuatroCifras:rows('1204 5649 7616 8840 9675',30000),extraccionesDeTresCifras:rows('010 086 137 198 385 411 514 585 727 753 995',6000),extraccionesDeDosCifras:rows('00 07 40 65 65 67 72 74 90',2400),reintegros:rows('1 4 3',1200)};
const calc=prepare101(d);
for(const [n,c] of Object.entries({'58451':10000000,'64780':2500000,'09224':501200,'09265':10800,'64779':96800,'58411':13200}))assert.equal(calc(n).cents,c,n);
let total=0,hits=0,winning=0;
for(let i=0;i<100000;i++){const r=calc(String(i).padStart(5,'0'));total+=r.cents;hits+=r.hits.length;winning+=r.cents>0;}
assert.equal(total,84000000);assert.equal(hits,41551);
assert.equal(calc('9224'),null);
assert.equal(calc101({...d,modelDraw:82},'09224'),null);
assert.equal(calc101({...d,reintegros:[]},'09224'),null);
assert.equal(calc101({...d,extraccionesDeDosCifras:d.extraccionesDeDosCifras.slice(1)},'09224'),null);
console.log({total,hits,winning});
