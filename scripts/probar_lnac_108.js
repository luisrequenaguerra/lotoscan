"use strict";
const fs=require("fs"),path=require("path"),assert=require("assert/strict");
const {prepare108,calc108}=require("./lnac_modelo108");
const dir=process.argv[2];
let failed=false;
for(const year of [2024,2025]){
 const read=s=>JSON.parse(fs.readFileSync(path.join(dir,year+s),"utf8"));
 const majors=read(".mayores.json"),pedreas=read(".extracciones.json").pedreas;
 const prepared=prepare108(majors,pedreas);
 const rows=fs.readFileSync(path.join(dir,year+".motor-108.jsonl"),"utf8").trim().split("\n");
 const canon=p=>p.map(x=>JSON.stringify(x)).sort().join("|");
 let total=0,amountErrors=0,partErrors=0;const examples=[];
 assert.equal(rows.length,100000);
 rows.forEach((line,i)=>{
  const r=JSON.parse(line);assert.equal(r.n,String(i).padStart(5,"0"));
  const j=calc108(prepared,r.n);total+=j.cents;
  const a=j.cents!==r.cents,b=canon(j.parts)!==canon(r.parts);
  amountErrors+=Number(a);partErrors+=Number(b);
  if((a||b)&&examples.length<30)examples.push({n:r.n,python:r,js:j});
 });
 for(const n of ["","1234","123456","abcde",12345,null])assert.throws(()=>calc108(prepared,n));
 assert.throws(()=>prepare108(majors,pedreas.slice(1)));
 assert.throws(()=>prepare108(majors,[...pedreas.slice(1),pedreas[1]]));
 assert.throws(()=>prepare108(majors,[...pedreas.slice(1),Object.keys(majors)[0]]));
 const report={year,numbers:rows.length,total_cents:total,amountErrors,partErrors,invalid_input_tests:9,examples,pass:total===140000000&&!amountErrors&&!partErrors};
 fs.writeFileSync(path.join(dir,year+".js-contraste.json"),JSON.stringify(report,null,2));
 console.log("JS_CONTRASTE "+JSON.stringify(report));failed ||= !report.pass;
}
if(failed)process.exitCode=1;
