#!/usr/bin/env python3
"""LotoScan 1.22 - cierre de excepciones documentales, sin certificar premios.
Reutiliza 1.21 y sus dependencias. Las referencias 2024/25 son SOLO regresion.
Para nuevos sorteos no se supone que haya 17 anclas ni se infieren premios.
"""
import argparse,base64,collections,json,pathlib,re,tempfile,zlib
from conciliar_navidad_121 import ejecutar as conciliar
from consultar_navidad_119 import leer_json,premios_mayores
HISTORICAS='c-qxjO>f&c5dABL&IZBxAcxG&XuCjxHU(1jR4feF(Pp)qTCL*%yD0kKm-^}|<y3}m%)$0SezxAcnc<t!w+bzCb@lOEb$I+-AKU7x0tjrYb@gR;*Bo}$6|Ad&(t8ZX#dY;>b>%!8AJ)~W{kuMF+hfyx?|z2tFFb5->tntDGyTHH3W(U6bg6rt#?S5r)^-T+XxUW1udCZ;cXwzXPR+i%m(BHyH=FHmA70&Twl808U%Y$s;qCS2{r26>%h%VNo7bE734CZz=})TbcC|Yln@^9;akbx_>brDjyVXN;Sl!qAQ+r(9)~iqV?bpZpVb!ko?Wz8&UA2ES`zGD|_w_6SBtd)@0T12?_Yoj*#wh`qfLQ<vAqMDdF0D^&sON=9hN7nI2+Wmb0AVvz^e1JRBJlsp7ZM1z7B~-tOR~xk2|^RJ9G{R{Byi4Div;^(a{O#6NHCTzOa(%}lnQK1Oa+JNvOoxfp&=E7tP#{wVMLZ%?d;h3C1xSXMNVZlAd6)dEau58!5Zv|MNHKT8nF>rDlu<8;*1#f#L&W6m7LBX)*AE#ER`5q`=s3r#3*ogj&`Z&f)Rz+gv+~)q(tUflPRX52&OE{sV37Te&FhZ0k4pqkP2Cr{>sAflH$R`SDuOF5t7-!%QWZ6XT#uxo}53$q(yL)g@bK0c4%6VnwIEkF(6B=?UbAnmYAifz*wyvPsn1KIpAf@EQs+cwGmn@H4(3f7GggDbVrRP<JEK=k$HIrYtMD5K+vC4#gt_fVwc510-6Xzn{tLVA3Om|5;*;Jn&;h5^L+3=W@ZUfAO4|qa!ab!ACbkH3If248KE<AuuG9sI&0NAA&X_^SYzhJa2Q&ubtY)lIU&ns=4?=y{cuOW^zIWf?>p#O;=<sGks=k-aTo-Y?NTzpIB1LPjHuJgh%9(|;h6POfW&M#F1<&?ppP$Ha;Nb?-Y+qWjD2b5%tqvMSqY9VJx!bpqb;>2%0-JHff(tGO?Q@{NSkgg=e`I7^egW!9%Kz`W6Ok8;^BrX#V-GH(Ph|#ULrc$z)BB(B03TlIkJm@TlV>A@E2wnO5OoVNF$cQ%=f-%m|#+BtNA=a6{#b;IMZ>j_<Rum47L%R9M$+#OFS9N7p)_Ljh>cMK9Cfe@{uXuG%||`!+J&pjnk%r38}<`WXy}_B6{e?_i&l$X>vF#dKmkCVWLOtW4_OrJ@$&J&#61P37N+u5_z{Ak5nb2A1EabjFQJ;_GAQ@3~EnCCS*}l|M&j@6_cgY'
BASE={'primer_premio':400000,'segundo_premio':125000,'tercer_premio':50000,'cuarto_premio':20000,'quinto_premio':6000}

def ejecutar(anio,pdf=None,json_path=None,numero=None,salida='salida_122'):
    out=pathlib.Path(salida);out.mkdir(parents=True,exist_ok=True)
    if numero is not None and not re.fullmatch(r'\d{5}',numero):raise ValueError('Numero debe tener 5 cifras')
    with tempfile.TemporaryDirectory(prefix='lotoscan122_') as temp:
        rep=conciliar(anio,pdf,json_path,numero,temp)
        j=leer_json(anio,json_path);mayores=premios_mayores(j)
        referencias=json.loads(zlib.decompress(base64.b85decode(HISTORICAS)))
        excluidas=referencias.get(str(anio))
        anclas=[];no_clasificadas=[]
        if excluidas is not None:
            for a in excluidas:
                n=a['numero']
                if n in mayores:
                    clase='PREMIO_MAYOR_CONFIRMADO_JSON'
                else:
                    clase='ELEMENTO_NO_CLASIFICADO_NO_CONVERTIR_EN_PREMIO'
                entry={'numero':n,'pagina':a['pagina'],'x':a['x'],'y':a['y'],
                       'token_original':a['token_original'],'clasificacion':clase,
                       'premios_mayores_json':mayores.get(n,[]),
                       'observacion':'Ancla fuera de columnas en diagnostico historico 1.16; no es necesariamente una fila de premio'}
                anclas.append(entry)
                if clase.startswith('ELEMENTO'):no_clasificadas.append(entry)
        incidencias=[];cuenta=collections.Counter();solapamientos=[];total=0;consulta=None
        tabla=out/f'tabla_{anio}_122.jsonl'
        with (pathlib.Path(temp)/f'tabla_{anio}_121.jsonl').open(encoding='utf8') as fin,tabla.open('w',encoding='utf8') as fout:
            for linea in fin:
                r=json.loads(linea);n=r['numero'];total+=1
                comps=r['componentes_pdf'];maj=r['premios_mayores_json']
                ordinario=sum(x['euros_decimo'] for x in comps)
                reintegro=r['reintegro_derivado_euros']
                if maj:
                    valor=r['euros_decimo_calculados']
                    bases=sum(BASE[x['categoria']] for x in maj)
                    diferencia=round(valor-bases,2)
                    estado='MAYOR_PENDIENTE_REGLAS_ACUMULACION'
                    if ordinario or reintegro:
                        solapamientos.append({'numero':n,'euros_json':valor,'base_premios_mayores':bases,
                         'diferencia_json_base':diferencia,'componentes_ordinarios':comps,
                         'reintegro_potencial':reintegro,'motivo':'No sumar automaticamente sin verificar compatibilidad'})
                else:
                    estado='ORDINARIO_CALCULADO_NO_CERTIFICADO'
                cuenta[estado]+=1
                r['version']='1.22';r['estado_revision']=estado
                r['importe_certificado']=False
                r['euros_decimo_definitivos']=None
                r['desglose_explicito']={'componentes_pdf_euros':ordinario,'reintegro_derivado_euros':reintegro,
                    'premios_mayores_json_euros':sum(x['euros_decimo_json'] for x in maj)}
                fout.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
                if n==numero:consulta=r
        if total!=100000:incidencias.append({'tipo':'NUMEROS_INCOMPLETOS','cantidad':total})
        if rep['errores_control']:incidencias.append({'tipo':'ERRORES_121','cantidad':rep['errores_control']})
        if rep['incidencias_extraccion']:incidencias.append({'tipo':'INCIDENCIAS_EXTRACCION','cantidad':rep['incidencias_extraccion']})
        if excluidas is None:incidencias.append({'tipo':'SIN_REFERENCIA_ANCLAS_HISTORICAS','detalle':'Para este sorteo nuevo es necesario auditar bloques destacados sin presuponer el formato antiguo'})
        if no_clasificadas:incidencias.append({'tipo':'ANCLAS_SIN_CLASIFICAR','cantidad':len(no_clasificadas)})
        if solapamientos:incidencias.append({'tipo':'ACUMULACIONES_MAYORES_PENDIENTES','cantidad':len(solapamientos)})
        informe={'version':'1.22','anio':anio,'fuente':'PDF y JSON SELAE','sha256_pdf':rep['sha256_pdf'],
          'numeros':total,'filas_pedrea_candidata':rep['pedreas_candidatas'],
          'premios_mayores':rep['premios_mayores'],'estados':dict(cuenta),
          'anclas_historicas':len(anclas),'anclas_confirmadas_como_premios_mayores':len(anclas)-len(no_clasificadas),
          'anclas_no_clasificadas':len(no_clasificadas),'solapamientos_mayores_por_revisar':len(solapamientos),
          'incidencias':len(incidencias),'motor_validado':False,'publicable':False,
          'criterio':'El origen SELAE es oficial; la suma de componentes no queda certificada hasta resolver excepciones y reglas de acumulacion.',
          'siguiente_paso':'Revisar anclas no clasificadas y compatibilidad de componentes en premios mayores; no inventar categorias'}
        for filename,obj in [(f'informe_{anio}_122.json',informe),(f'anclas_{anio}_122.json',anclas),
           (f'solapamientos_{anio}_122.json',solapamientos),(f'incidencias_{anio}_122.json',incidencias)]:
            (out/filename).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf8')
        if consulta is not None:
            (out/f'consulta_{numero}_{anio}_122.json').write_text(json.dumps(consulta,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps(informe,ensure_ascii=False,indent=2));return informe

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--anio',type=int,required=True);p.add_argument('--pdf');p.add_argument('--json');p.add_argument('--numero');p.add_argument('--salida',default='salida_122');a=p.parse_args()
    if a.anio not in (2024,2025) and not(a.pdf and a.json):p.error('Año nuevo requiere PDF y JSON oficiales')
    ejecutar(a.anio,a.pdf,a.json,a.numero,a.salida)
