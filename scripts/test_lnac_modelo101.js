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

const d25={...d,primerPremio:{decimo:'73496',prize:10000000},segundoPremio:{decimo:'85051',prize:2507200},tercerosPremios:[{decimo:'74925',prize:502400}],extraccionesDeCuatroCifras:rows('0154 1011 3510 7218 9429',30000),extraccionesDeTresCifras:rows('051 169 424 551 610 618 677 715 868 879 896',6000),extraccionesDeDosCifras:rows('25 27 41 47 52 57 69 75 93',2400),reintegros:rows('6 0 1',1200)};
const c25=prepare101(d25);
for(const [n,c] of Object.entries({'73496':10000000,'85051':2507200,'74925':502400,'73495':179000,'85052':99200,'73424':12000}))assert.equal(c25(n).cents,c,n);
let total25=0,hits25=0,winning25=0;
for(let i=0;i<100000;i++){const r=c25(String(i).padStart(5,'0'));total25+=r.cents;hits25+=r.hits.length;winning25+=r.cents>0;}
assert.equal(total25,84000000);assert.equal(hits25,41551);
console.log({year:2025,total25,hits25,winning25});
