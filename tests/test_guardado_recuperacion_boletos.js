const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('index.html','utf8');
const start=html.indexOf('function saveGameEntry(e)'),end=html.indexOf('// Mantener exactamente la iconografía',start);
assert(start>=0&&end>start);
const storage=new Map(),alerts=[],opened=[];
const fields={entryMain:{value:''},entryExtra:{value:''},entryJoker:{value:''},gameEntryDate:{value:''},gameEntryPrice:{value:''},gameFilter:{value:'all'}};
const document={getElementById:id=>fields[id]||null};
const defs={
 quiniela:{kind:'quiniela',label:'La Quiniela'},quinigol:{kind:'quinigol',label:'Quinigol'},
 lototurf:{kind:'balls',count:6,max:31,extraCount:1,extraMax:20,label:'Lototurf'},
 quintuple_plus:{kind:'horses',label:'Quíntuple Plus'},
 primitiva:{kind:'balls',count:6,max:49,extraCount:1,extraMax:9,label:'Primitiva'}
};
const sandbox={document,alert:m=>alerts.push(m),Date,Number,String,Array,Set,
 GAME_DEFS:defs,selectedGame:'quiniela',sportsPicks:Array(14).fill('1'),sportsPleno:['1','0'],sportsElige8:[0,1,2,3,4,5,6,7],
 turfNumbers:[1,2,3,4,5,6],turfHorse:2,turfRefund:4,quintuplePicks:[1,2,3,4,5,6],
 VISUAL_GAMES:[],visualMain:[],visualExtra:[],tickets:[],
 parseNumbers:(line,count,max)=>{const n=line.trim().split(/\s+/).map(Number);return n.length===count&&new Set(n).size===count&&n.every(x=>Number.isInteger(x)&&x>=1&&x<=max)?n.map(x=>String(x).padStart(2,'0')).join(' '):null},
 validateDrawDate39:()=>true,renderTickets:()=>{},go:()=>{},renderSportsBoard:()=>{},
 openTicket:id=>{assert(storage.has('tickets'),'Must persist before opening ticket');opened.push(id)},
 persistTickets:()=>{storage.set('tickets',JSON.stringify(sandbox.tickets));return true}
};
vm.createContext(sandbox);vm.runInContext(html.slice(start,end),sandbox);
function save(game,main,extra,opts={}){
 sandbox.selectedGame=game;if(game==='quinigol')sandbox.sportsPicks=Array.from({length:6},()=>['1','0']);fields.entryMain.value=main;fields.entryExtra.value=extra;
 fields.entryJoker.value=opts.joker||'';fields.gameEntryDate.value='2026-11-08';fields.gameEntryPrice.value='';
 const before=sandbox.tickets.length;
 sandbox.saveGameEntry({preventDefault(){},target:{reset(){}}});
 assert.equal(sandbox.tickets.length,before+1,game+': '+alerts.join('; '));
 const saved=JSON.parse(storage.get('tickets'))[0];
 assert.equal(saved.game,game);
 assert.equal(saved.date,'2026-11-08');
 assert.equal(opened.at(-1),saved.id,game+': should open the ticket that was just saved');
 return saved;
}
const q=save('quiniela','11111111111111','1-0');
assert.deepEqual(Array.from(q.elige8),[0,1,2,3,4,5,6,7]);
assert.equal(q.entries[0],'11111111111111');
const g=save('quinigol','1-0, 1-0, 1-0, 1-0, 1-0, 1-0','');
assert.equal(g.entries[0].split(',').length,6);
const l=save('lototurf','1 2 3 4 5 6','2');
assert.equal(l.horse,'2');assert.equal(l.reintegro,'4');
const h=save('quintuple_plus','1 2 3 4 5 6','6');
assert.deepEqual(Array.from(h.racePicks),[1,2,3,4,5,6]);
const p=save('primitiva','1 2 3 4 5 6','2',{joker:'0123456'});
assert.equal(p.joker,'0123456');
const recovered=JSON.parse(storage.get('tickets'));
assert.equal(recovered.length,5);
assert.deepEqual(recovered.map(t=>t.game),['primitiva','quintuple_plus','lototurf','quinigol','quiniela']);
assert.equal(recovered[4].elige8.length,8);
assert.equal(recovered[2].reintegro,'4');
assert.equal(recovered[0].joker,'0123456');
console.log('OK: five games saved, serialized and recovered without losing special fields');
