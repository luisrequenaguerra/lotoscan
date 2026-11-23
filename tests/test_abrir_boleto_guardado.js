const fs=require('fs'),assert=require('assert');
const html=fs.readFileSync('index.html','utf8');
const sources=[
 ['QR Euromillones','function saveQRReview()','async function tryRecognizeQR()'],
 ['OCR Lotería Nacional','function saveRecognizedTicket()','function resetScanner()'],
 ['Manual Lotería Nacional','function saveManualTicket(e)','function saveGameEntry(e)'],
 ['Manual demás juegos','function saveGameEntry(e)','// Mantener exactamente la iconografía']
];
for(const [name,startToken,endToken] of sources){
 const start=html.indexOf(startToken),end=html.indexOf(endToken,start+startToken.length);
 assert(start!==-1&&end>start,name+': función no encontrada');
 const body=html.slice(start,end);
 assert(body.includes('openTicket(t.id)'),name+': debe abrir el boleto guardado');
 assert(!body.includes("go('tickets')"),name+': no debe redirigir al listado');
 assert(body.includes('persistTickets()'),name+': debe persistir antes de abrir');
 assert(body.indexOf('persistTickets()')<body.lastIndexOf('openTicket(t.id)'),name+': navegación posterior a persistencia');
}
const open=html.slice(html.indexOf('function openTicket(id)'),html.indexOf('function editCurrentTicket()'));
assert(open.includes("go('ticketDetail')"),'La ficha debe mostrarse en pantalla');
assert(open.includes('detailContent(t)'),'La ficha debe mostrar el resultado calculado');
console.log('OK: QR, OCR y entradas manuales abren la ficha del boleto tras guardar');
