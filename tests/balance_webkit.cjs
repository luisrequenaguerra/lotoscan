const {webkit}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{const browser=await webkit.launch();try{
for(const width of [320,375,390,430]){
 const page=await browser.newPage({viewport:{width,height:844},isMobile:true,hasTouch:true});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8765/',{waitUntil:'networkidle'});
 await page.locator('button[data-tab="results"]').click();
 await page.locator('#balanceContent .balance-value').waitFor();
 assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem('lotoscan_tickets_v010')).length),0);
 for(const period of ['month','year','all']){
  await page.locator('.balance-filters [data-period="'+period+'"]').click();
  assert.equal(await page.locator('.balance-filters [data-period="'+period+'"]').getAttribute('aria-pressed'),'true');
  assert.match(await page.locator('.balance-value').innerText(),/0,00/);
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'overflow '+width);
 }
 await page.evaluate(()=>{localStorage.setItem('lotoscan_tickets_v010',JSON.stringify([{id:999,game:'bonoloto',date:'2026-11-27',number:'03 09 12 15 39 41',price:1}]));});
 await page.reload({waitUntil:'networkidle'});
 await page.locator('button[data-tab="results"]').click();
 await page.locator('.balance-filters [data-period="all"]').click();
 assert.match(await page.locator('.balance-pair').innerText(),/1,00/);
 assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem('lotoscan_tickets_v010')).length),1);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.deepEqual(errors,[]);
 console.log('WebKit '+width+'px: primera apertura, filtros, boleto conservado, balance y anchura OK');
 await page.close();
}
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
