const {prepare105,calc105}=require('../../../scripts/lnac_modelo105');
const assert=require('node:assert/strict');
for(const year of [2025,2026]){
 const {raw,expected}=require('./'+year+'.json');const calc=prepare105(raw),s=raw.premioEspecial;let mismatch=0,total=0,winners=0;
 for(let i=0;i<100000;i++){
  const n=String(i).padStart(5,'0');const ref=expected[n]??expected[n.slice(-3)]??expected[n.slice(-2)]??expected[n.slice(-1)]??0;
  const actual=calc(n).cents;total+=actual;if(actual)winners++;if(actual!==ref){if(mismatch<5)console.log(n,ref,actual);mismatch++;}
 }
 for(let a=1;a<=10;a++)for(let b=1;b<=10;b++){
  assert.equal(calc(s.numero,a,b).cents,a===s.serie&&b===s.fraccion?2000000000:20000000);assert.equal(calc(s.numero,a,b).specialPending,false);
 }
 assert.equal(calc(s.numero).specialPending,true);assert.equal(calc(s.numero,s.serie,null).specialPending,true);assert.equal(calc(s.numero,null,s.fraccion).specialPending,true);
 assert.equal(calc(s.numero,s.serie%10+1,null).specialPending,false);assert.equal(calc(s.numero,null,s.fraccion%10+1).specialPending,false);
 assert.equal(calc(s.numero,0,1),null);assert.equal(calc(s.numero,1,11),null);assert.equal(calc('1234'),null);
 assert.equal(calc105({...raw,premioEspecial:null},s.numero),null);assert.equal(calc105({...raw,extraccionesDeTresCifras:[]},s.numero),null);
 assert.equal(calc(raw.segundoPremio.decimo,s.serie,s.fraccion).cents,raw.segundoPremio.prize);
 console.log(JSON.stringify({year,checked:100000,mismatch,winners,nonwinners:100000-winners,ordinaryEurosPerSeries:total/10,specialCombinations:100,additionalAssertions:11}));assert.equal(mismatch,0);
 assert.equal(total/10,12020000);
}
