const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('index.html','utf8');
const code=html.slice(html.indexOf('const sampleTickets = ['),html.indexOf('// LotoScan 0.84'));
const key='lotoscan_tickets_v010',marker='lotoscan_demo_removed_v1';
function boot(initial){const store=new Map(Object.entries(initial));const ctx=vm.createContext({localStorage:{getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,v)},console:{warn(){},error(){}},alert(){}});vm.runInContext(code,ctx);return {store,tickets:JSON.parse(vm.runInContext('JSON.stringify(tickets)',ctx)),samples:JSON.parse(vm.runInContext('JSON.stringify(sampleTickets)',ctx))};}
const fresh=boot({});assert.deepEqual(fresh.tickets,[]);assert.equal(fresh.store.get(key),'[]');
const demos=fresh.samples,edited={...demos[0],price:21},personal={...demos[1],id:99},extra={...demos[2],note:'personal'};
const migrated=boot({[key]:JSON.stringify([...demos,edited,personal,extra])});assert.deepEqual(migrated.tickets,[edited,personal,extra]);assert.equal(migrated.store.get(marker),'1');
assert.deepEqual(boot({[key]:JSON.stringify([demos[0]]),[marker]:'1'}).tickets,[demos[0]]);
const corrupt=boot({[key]:'invalid'});assert.equal(corrupt.store.get(key),'invalid');assert.equal(corrupt.store.has(marker),false);
console.log('Migración: primera apertura, coincidencia exacta, conservación de editados, idempotencia y datos corruptos OK');
