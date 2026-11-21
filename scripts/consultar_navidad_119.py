#!/usr/bin/env python3
"""LotoScan 1.19: consulta de premios documentados, sin publicar totales no certificados.
Requiere scripts/auditar_integracion_navidad_117.py. SELAE JSON histórico integrado
solo para regresión; sorteos nuevos: --pdf y --json oficiales descargados de SELAE.
"""
import argparse,base64,collections,datetime,hashlib,importlib.util,json,pathlib,re,sys,zlib
JSON_HISTORICO={2024: 'c-rll-)`GB6vkgg@PJ*VHbqgElU*56(h11o!8VGm!%#5Nu}eS}JxWU26n&rF>?!(U<Dvghmd!S<FY8=6=X^Y*e&4Z8pHH1iEagP13S{TX>)dxPyhi9X6rgyHnJH#wkiO?uO$lYMeEN#gDH&V^<cg3kA>=Jeb5Y^a+np7kI#A-mOfEz*mmZ~F23{so0gDF(_z%{^^(i+(Q7@pF!v#uvMhxXj+uKT^K<T6|GXBvBV@S0IlvUKI5OZE+z%NYL;}1||HP?Dn%=5i-VGSj>H6CAhpwC*HDgKmX7L-rJOGYkzV)klgCt_X;C@R><1}F>KvY}QeA=O6Zqsm8BA#w8<a=Y7PG@jm!yqiC!<Kbu=C-=i~GV<aZ?|%3uiH9*RTPj!xc~dSS6~^GA&T|tN3sAqCtT9Y;5DQZ_qHI7+fAEK#+a)~bcmx|*Ti+<Ma^2UCtb<#F{dLIt=$DlaiD$6J`9J^kfshCOi#Op)aO;;%*t(Cqb<qx~GAM3^Ikb;$Y+stx`t{Q6dgU>)`rCx2AD70S*I2%MFQ0B@o<XKVGoF`#JCrcj?I#a%)8%}23O9P-DOdDp(Wckb?l7b-hSbS$TfNPYT86a2kTw|VCOydTt(&2K_!N{ZSI597|Er17_Xq5x_6wXCgS{pUTo?lv#=wa&P~VSHL!<{N{^_9jH$GC$Rpq3p-@^1Hip)uoRc(sQMUlBEGAG4t^)|)8QVbdtg9b%<nBuR_UflWEi=zJE2P8(0AclSSPb~^}-v!Yi>YqX}bW#kz{M*JDx-f<=jG+^wE#KzIEJxPh$Qm5`2QeluYCINF8lI6Ihm3{iE;|ZYpY&HZ;4`w9B8%uC49>`oLdK$Ka7K0%ve0MeE;|a@WfZXUH|95x;av?rREnpmkOh=6T-Ur(@><LkH}|%E#Z*E0wR|jFX$AT+2y?Z65j^R~$9PlL8nX$3HD(Mm{bStvkyOuhUOhv@iJd}^JB9cHifVss&~MBQ`pv;XzjbYH``~}Yhg#)#qO5o(M>DY=#B_SIUM_Lm!^>VKQ=B*Hdv)&)V_*K`-aSX`Jn!YWw8R<IYMN8_CcnMAOD5Cd=r*}dhIic|PNcdMpV00yo8dtgGJ`x;{0Wav1}0K!E7cpli}9~gHQ4aAEJ`si%$7FU>K{?0t@hCe(%E?9Iwf85`G0*R^hN', 2025: 'c-rll+iu%95Qbkx@B(|4+9Y+bon9GH(i%wP!ZwQC7K;TVjU58C=q073P0{z+n|+GD*lOqlWyLb;`m*+wJo9rn`u<76@M|j<OEpnC2i3atT6e7ruM&C#8E7ssGsVmdk_Yb8jIi((Wv>{UlHR3HE(vK9LO!BYiX4~T?5z0O0)q=>k%93T^HT6qkqB7aYrrp95mzT1WvP&*(p;djW3^yb(#}>187kkYEahLUFovYmfOd)k72M<?;Q=y!VKW}Thb%34xdcUXx$bM-7S_;eTjTM^`uSE$Q_Y`-se?pWKkSn}C3c@`b|U75fGmf#EMh40>#{+q&_d}=u@F@hRhh!gV~}pQ$!I*i9(mV)Ovi)KI3C^&#>0^pUwe0h55ss6<FciOg;3XK35l@gW`&eCE*7BQ+pIOK#2^;7Y_}iyw*Q>pOYW9%$*~0&SleDHvT~f3hOC2Id+9plY@{YHL*f~nZ}j)yJ`-}!Uwad-1$SP#gsc0wTNmw6I)&^;*rq9tuzR$r_4Cs1dg%pZ_1T1`UzXOMH(1_0sHYnxQ%K9uj7tN!gMoRGrD{JnLW15Y+}NJCT+w4$onBSD!;m#GWQ`2B)$0tIW5_BDS%o2G;a-Lxn;DibpMX|o)ds%#rz*xiiTeI282v_!{)-{>n=txK82v_!zW#ZP;r>bdvw`AY_(}!Wc_T$u{^~es7=uQNL0+dAG*JwiC<cubx7F(ueMix+Q1mMl*?x*|8)tFn$F~=ByJuntiQ(M+Q;6)q-1(HA^v5G?q!@nxw~jGv!WcGT3>z`J@^y}Z;}}#p1{IDGVS6wRe`xSn7@UzEhm7{3sQ)V>BR`ESpj{fBksX69B2jRjvg43ZKRQp@QOLU8E)CDfjzQKBSl2%zJB$p^YVbMNJV}Jgz{GG>@La1aG1J_h+g>WB8qA@5tZHcu<zW!!de1@d6o1B>vd)-I2%Irvn3eyGJ3of`b0PC*s5r4x=y9hIUqF_>yf%m`_Xbh*;vlLWo9jN%13na5-U^fRRE=h0eG${@%sNuxbq_b4R3!!WqfF-(W8eSd-W^BmTy`WbHFyWLy3H}2$-BRAhm+}GbThmf4sP26ypd{8C}HhoI>Sa5Dg_y9{)DZQo{gB&O8ueS#rl`)0$lh?Wk$?1yQNFk=0{{nZG6gx%51!Gosl;A_CHtS^9c'}

def leer_json(anio, ruta):
    if ruta: return json.loads(pathlib.Path(ruta).read_text(encoding='utf8'))
    if anio not in JSON_HISTORICO: raise ValueError('Para un año nuevo se necesita --json de SELAE')
    return json.loads(zlib.decompress(base64.b85decode(JSON_HISTORICO[anio])))

def premios_mayores(j):
    grupos={'primerPremio':'primer_premio','segundoPremio':'segundo_premio','tercerosPremios':'tercer_premio','cuartosPremios':'cuarto_premio','quintosPremios':'quinto_premio'}
    premios=collections.defaultdict(list)
    for key,cat in grupos.items():
        vals=j.get(key)
        if vals is None: raise ValueError('Falta campo oficial: '+key)
        for item in vals if isinstance(vals,list) else [vals]:
            n=str(item['decimo']).zfill(5); raw=item['prize']
            if not re.fullmatch(r'\d{5}',n) or isinstance(raw,bool) or not isinstance(raw,(int,float)) or raw<0:raise ValueError('Premio mayor mal formado')
            # SELAE JSON prize expresa centimos por decimo en los historicos revisados.
            premios[n].append({'categoria':cat,'euros_decimo_json':round(raw/100,2),'prize_raw':raw,'fuente':'json_selae'})
    if sum(map(len,premios.values()))!=13:raise ValueError('Esperados 13 premios mayores; revisar formato')
    return premios

def main():
    p=argparse.ArgumentParser(description='Consulta documental LotoScan 1.19')
    p.add_argument('--anio',type=int,required=True);p.add_argument('--pdf');p.add_argument('--json');p.add_argument('--numero');p.add_argument('--salida',default='salida_119')
    a=p.parse_args(); out=pathlib.Path(a.salida);out.mkdir(parents=True,exist_ok=True)
    if a.anio not in (2024,2025) and not (a.pdf and a.json):p.error('Sorteo nuevo: proporcionar --pdf y --json oficiales')
    j=leer_json(a.anio,a.json)
    if str(a.anio) not in str(j.get('fechaSorteo',''))[:4]:raise ValueError('Año JSON no coincide')
    if 'NAVIDAD' not in str(j.get('nombreDelSorteo','')).upper():raise ValueError('El JSON no es Navidad')
    path=pathlib.Path(__file__).resolve().parent/'auditar_integracion_navidad_117.py'
    if not path.exists():raise SystemExit('Falta scripts/auditar_integracion_navidad_117.py')
    spec=importlib.util.spec_from_file_location('lector117',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    class Args: pass
    x=Args();x.historico=a.anio if not a.pdf else None;x.pdf=a.pdf;x.url=None
    pdf=m.load(x);rows,pages=m.scan(pdf);mayores=premios_mayores(j)
    comps=collections.defaultdict(list);issues=[];counts=collections.Counter()
    for r in rows:
        n=r['numero'];amt=r['importe_euros_billete'];mark=r['marca']
        if r['estado']!='asociacion_univoca' or amt is None or amt%10:
            issues.append({'tipo':'FILA_NO_CONCILIABLE','fila':r});continue
        cat={'t':'terminacion','c':'centena','a':'aproximacion',None:'pedrea_candidata'}.get(mark)
        if cat is None:issues.append({'tipo':'MARCA_NO_RECONOCIDA','fila':r});continue
        comps[n].append({'categoria':cat,'euros_decimo':amt//10,'pagina':r['pagina'],'columna':r['columna'],'y':r['y'],'fuente':'pdf_selae'})
        counts[cat]+=1
    if len(rows)!=5292 and a.anio in (2024,2025):issues.append({'tipo':'RECUENTO_HISTORICO_INESPERADO','filas':len(rows)})
    if any(p['advertencias'] for p in pages):issues.append({'tipo':'ADVERTENCIA_GEOMETRIA','paginas':pages})
    # Reintegro: regla identificada a partir de primer premio. Es derivado, no fila PDF.
    primero=next(n for n,v in mayores.items() if any(c['categoria']=='primer_premio' for c in v))
    reintegro_digito=primero[-1]
    tabla=[]
    for i in range(100000):
        n=f'{i:05d}';ordinarios=comps.get(n,[]);grandes=mayores.get(n,[])
        subtotal=sum(c['euros_decimo'] for c in ordinarios)
        # No sumar automaticamente JSON mayor + filas: algunos premios JSON ya incluyen reintegro.
        # Las reglas de compatibilidad y excepciones requieren cierre documental.
        tiene_reintegro=n[-1]==reintegro_digito
        if grandes:
            estado='PREMIO_MAYOR_PENDIENTE_CONCILIAR_ACUMULACIONES'
            total=None
        elif tiene_reintegro:
            estado='REINTEGRO_Y_ACUMULACIONES_PENDIENTES'
            total=None
        else:
            estado='COMPONENTES_PDF_NO_CERTIFICADOS' if ordinarios else 'SIN_PREMIO_DOCUMENTADO_NO_CERTIFICADO'
            total=None
        tabla.append({'numero':n,'estado':estado,'euros_decimo_confirmados_pdf_ordinario':subtotal,
            'premios_pdf':ordinarios,'premios_mayores_json':grandes,
            'reintegro_potencial_20_euros':tiene_reintegro,
            'euros_decimo_definitivos':total})
    sha=hashlib.sha256(pdf).hexdigest(); report={'version':'1.19','anio':a.anio,'sorteo':j.get('nombreDelSorteo'),
        'fecha_sorteo':j.get('fechaSorteo'),'draw_id':j.get('drawIdSorteo'),'sha256_pdf':sha,
        'filas_ordinarias':len(rows),'categorias':dict(counts),'premios_mayores':sum(map(len,mayores.values())),
        'numero_reintegro_derivado':reintegro_digito,'incidencias':len(issues),
        'numeros_generados':len(tabla),'numeros_con_premio_definitivo':0,
        'motor_validado':False,'publicable':False,
        'limites':['JSON de SELAE de premios mayores no es tabla completa de premios por numero',
          'Los importes JSON de premios mayores pueden incluir reintegros; no sumar sin conciliacion',
          'Las 17 anclas fuera de columnas y compatibilidad de premios no estan cerradas',
          'Los importes de filas PDF no son todavia un premio total pagadero']}
    (out/f'informe_{a.anio}_119.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    (out/f'incidencias_{a.anio}_119.json').write_text(json.dumps(issues,ensure_ascii=False,indent=2))
    with (out/f'tabla_{a.anio}_119.jsonl').open('w',encoding='utf8') as f:
        for r in tabla:f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
    if a.numero:
        if not re.fullmatch(r'\d{5}',a.numero):p.error('--numero requiere exactamente cinco cifras')
        print(json.dumps(tabla[int(a.numero)],ensure_ascii=False,indent=2))
        (out/f'consulta_{a.numero}_{a.anio}_119.json').write_text(json.dumps(tabla[int(a.numero)],ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
