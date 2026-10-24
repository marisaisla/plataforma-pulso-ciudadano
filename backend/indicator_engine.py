"""Cálculos puros sobre un solo lote; no escribe ni imputa valores faltantes."""
from fractions import Fraction
import hashlib
import json

from backend.indicator_catalog import ENGINE_VERSION, CATALOG_VERSION


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=str,
                                     separators=(',',':')).encode()).hexdigest()


def unavailable(reason, status='unavailable'):
    return dict(value=None,status=status,reason=reason,numerator=None,denominator=None,details={})


def measured(value, numerator=None, denominator=None, status='computed', **details):
    if isinstance(value,Fraction):
        value=round(float(value),6)
    return dict(value=value,status=status,reason=None,numerator=numerator,denominator=denominator,details=details)


def ratio(numerator,denominator,status='computed'):
    if numerator is None or denominator is None:
        return unavailable('Falta numerador o denominador; no se sustituye por cero.')
    if denominator<=0:
        return unavailable('El denominador debe ser mayor que cero.')
    if numerator<0 or numerator>denominator:
        return unavailable('El numerador está fuera del universo del denominador.')
    return measured(Fraction(numerator*100,denominator),numerator,denominator,status)


def composition(row):
    totals=[row.get(k) for k in ('total_votes','null_votes','unregistered_votes')]
    votes=row['options']
    if any(v is None for v in totals) or not votes or any(v['votes'] is None for v in votes):
        return None,'Faltan componentes u opciones para conciliar votos válidos.'
    valid=totals[0]-totals[1]-totals[2]
    if valid<0 or sum(v['votes'] for v in votes)!=valid:
        return None,'Las opciones, nulos y no registrados no concilian con el total.'
    if valid==0:
        return None,'No hay votos válidos para calcular cuotas.'
    return valid,None


def unit_metrics(row, selection, basis):
    metrics,warnings={},[]
    nominal=row.get('nominal_list')
    metrics['IT01']=measured(nominal) if nominal is not None else unavailable('Lista nominal no disponible.')
    proxy=selection['participation_proxy']
    if proxy:
        metrics['IT03']=ratio(row.get('total_votes'),nominal,'proxy')
        metrics['IT03']['details']['definition']='Votos emitidos / lista nominal; no es conteo censal de votantes.'
        value=metrics['IT03']['value']
        metrics['IT04']=measured(round(100-value,6),status='proxy') if value is not None else unavailable(metrics['IT03']['reason'])
    else:
        reason='Falta conteo de votantes. El proxy con votos emitidos requiere selección explícita.'
        metrics['IT03']=unavailable(reason)
        metrics['IT04']=unavailable(reason)
    metrics['IT05']=ratio(row.get('null_votes'),row.get('total_votes'))
    valid,reason=composition(row)
    if reason:
        warnings.append(reason)
    options={o['option_code']:o for o in row['options']}
    selected=options.get(selection.get('option_code'))
    if basis!='party':
        party_reason='Requiere votos atribuidos por partido; no inferirlos de candidaturas o columnas heredadas.'
        metrics['IP01']=unavailable(party_reason)
        metrics['IP02']=unavailable(party_reason)
        metrics['IP05']=unavailable(party_reason)
        metrics['IT09']=unavailable(party_reason)
    else:
        votes=selected['votes'] if selected else None
        impossible=votes is not None and row.get('total_votes') is not None and votes>row['total_votes']
        metrics['IP01']=measured(votes) if votes is not None and not impossible else unavailable('Seleccionar un partido con votos conocidos y compatibles con el total; opción ausente no significa cero.')
        metrics['IP05']=measured(int(votes>0)) if votes is not None and not impossible else unavailable('Falta votación compatible del partido en esta unidad.')
        denom=valid if selection['denominator']=='valid_votes' else row.get('total_votes')
        metrics['IP02']=unavailable(reason) if reason else ratio(votes,denom)
        if reason:
            metrics['IT09']=unavailable(reason)
        else:
            hhi=sum((Fraction(o['votes'],valid)**2 for o in row['options']),Fraction())
            metrics['IT09']=measured(hhi,denominator=valid,scale='0–1')
    if basis!='candidacy':
        metrics['IT06']=unavailable('Requiere candidaturas consolidadas; no ordenar partidos o combinaciones como si fueran candidaturas.')
    elif reason:
        metrics['IT06']=unavailable(reason)
    elif len(options)<2:
        metrics['IT06']=unavailable('Se requieren al menos dos candidaturas.')
    else:
        ranked=sorted(options.values(),key=lambda o:(-o['votes'],o['option_code']))
        margin=ranked[0]['votes']-ranked[1]['votes']
        metrics['IT06']=measured(margin,margin,valid,
            margin_pp=round(float(Fraction(100*margin,valid)),6),
            winner=ranked[0]['option_code'] if margin else None,tie=margin==0,
            runner_up=ranked[1]['option_code'] if margin and sum(v['votes']==ranked[1]['votes'] for v in ranked)==1 else None,
            runner_up_candidates=[v['option_code'] for v in ranked if v['votes']==ranked[1]['votes']])
    return metrics,warnings


def combine(rows):
    """Totales ponderados sobre cobertura completa; no promediar porcentajes."""
    combined=dict(unit_code='coverage',name='Cobertura observada')
    for field in ('nominal_list','total_votes','null_votes','unregistered_votes'):
        values=[r.get(field) for r in rows]
        combined[field]=sum(values) if values and all(v is not None for v in values) else None
    codes=sorted({v['option_code'] for r in rows for v in r['options']})
    lookup=[{v['option_code']:v for v in r['options']} for r in rows]
    combined['options']=[]
    for code in codes:
        values=[group.get(code,{}).get('votes') for group in lookup]
        combined['options'].append(dict(option_code=code,option_name=code,
            votes=sum(values) if all(v is not None for v in values) else None))
    return combined


def provenance(dataset):
    meta=dataset['metadata']
    return dict(import_id=meta['id'],election=dataset['election'],geography=dataset['geography'],
        level=meta['level'],vote_basis=meta['vote_basis'],source=meta['source'],
        content_sha256=meta['content_sha256'],fingerprint=meta['fingerprint'],
        superseded_by=meta.get('superseded_by'),coverage_note=meta['coverage_note'],
        data_sha256=fingerprint(dataset))


def evaluate(dataset, selection):
    meta=dataset['metadata']
    rows=[r for r in dataset['rows'] if (not selection.get('entity_code') or r['entity_code']==selection['entity_code'])
          and (not selection.get('unit_code') or r['unit_code']==selection['unit_code'])]
    result_rows=[]
    for row in rows:
        metrics,warnings=unit_metrics(row,selection,meta['vote_basis'])
        result_rows.append(dict(unit_code=row['unit_code'],name=row['name'],metrics=metrics,
                                warnings=warnings,reported_options=row['options']))
    if rows:
        summary,_=unit_metrics(combine(rows),selection,meta['vote_basis'])
        if any(composition(row)[1] for row in rows):
            for code in ('IP02','IT09'):
                summary[code]=unavailable('Alguna composición territorial es incompleta o no concilia; un agregado no debe ocultarlo.')
        if selection['participation_proxy'] and any(r['metrics']['IT03']['value'] is None for r in result_rows):
            for code in ('IT03','IT04'):
                summary[code]=unavailable('Alguna unidad carece de un universo compatible para participación; no se oculta agregando.')
        if any(r['metrics']['IP01']['value'] is None for r in result_rows):
            summary['IP01']=unavailable('Falta votación partidista compatible en alguna unidad.')
        if len(rows)>1:
            summary['IT06']=unavailable('No se atribuye un ganador global sumando unidades de representación distintas.')
    else:
        summary={c:unavailable('No hay unidades para estos filtros.') for c in ('IT01','IT03','IT04','IT05','IT06','IT09','IP01','IP02')}
    selected=selection.get('option_code')
    counts=[next((v['votes'] for v in row['options'] if v['option_code']==selected),None) for row in rows]
    complete=bool(rows) and all(v is not None for v in counts) and meta['vote_basis']=='party' and all(r['metrics']['IP01']['value'] is not None for r in result_rows)
    summary['IP05']=measured(sum(v>0 for v in counts),units_observed=len(rows)) if complete else unavailable('Se requiere un partido conocido en todas las unidades observadas.')
    party_total=sum(counts) if complete else None
    for output,count in zip(result_rows,counts):
        output['metrics']['IP11']=ratio(count,party_total) if complete else unavailable('Falta votación del partido en alguna unidad o la atribución no es party.')
    summary['IP11']=dict(value=None,status='series',numerator=None,denominator=party_total,
        reason='Consultar distribución por unidad; el denominador son votos del partido dentro de este lote.',details={}) if complete and party_total>0 else unavailable('Distribución territorial no disponible.')
    warnings=['Cobertura limitada al lote y filtros seleccionados; no sumar otros lotes, niveles o revisiones.',
              'La verificación es estructural y aritmética; no certifica externamente la fuente.']
    if meta['source']['stage']=='legacy_snapshot' or meta['vote_basis']=='legacy_reported':
        warnings.append('EXPLORATORIO: carga heredada pendiente de acreditación; sin atribución partidista o de candidaturas asumida.')
    if selection['participation_proxy']:
        warnings.append('Participación y abstención son proxies basados en votos emitidos, no conteos de personas.')
    if meta.get('superseded_by'):
        warnings.append('Este lote fue sustituido por otra revisión; se reproduce la versión elegida.')
    page=[r for r in result_rows if r['unit_code']>selection['after']]
    items=page[:selection['limit']]
    return dict(engine_version=ENGINE_VERSION,catalog_version=CATALOG_VERSION,request=selection,
        provenance={**provenance(dataset), 'calculation_sha256':fingerprint(dict(engine=ENGINE_VERSION,catalog=CATALOG_VERSION,data=fingerprint(dataset),selection=selection))},
        coverage=dict(units_observed=len(rows),units_returned=len(items),
            metric_coverage={c:dict(available=sum(r['metrics'].get(c,{}).get('value') is not None for r in result_rows),total=len(rows)) for c in summary},
            pending_rows_included=0,scope='Un lote y un nivel; no representa por sí solo toda la entidad'),
        warnings=warnings,summary=summary,items=items,
        next_after=items[-1]['unit_code'] if len(page)>len(items) else None)


def comparability(a,b,request):
    reasons=[]
    ma,mb=a['metadata'],b['metadata']
    ea,eb=a['election'],b['election']
    for field in ('jurisdiction','office','principle','process','entity_code'):
        if ea.get(field)!=eb.get(field) or (field in ('principle','process') and ea.get(field) in (None,'unknown')):
            reasons.append('Elecciones incompatibles o sin acreditar: '+field)
    if not ea.get('election_date') or not eb.get('election_date') or str(ea['election_date'])>=str(eb['election_date']):
        reasons.append('Se requieren jornadas conocidas y A anterior a B.')
    for field in ('geography_id','level','vote_basis'):
        if ma[field]!=mb[field]: reasons.append('No coincide '+field+'; no se homologa automáticamente.')
    if ma['vote_basis']=='legacy_reported' or any(d['metadata']['source']['stage']=='legacy_snapshot' for d in (a,b)):
        reasons.append('Las cargas heredadas no tienen comparabilidad acreditada.')
    if not a['geography'].get('valid_on') or not b['geography'].get('valid_on'):
        reasons.append('Falta vigencia geográfica acreditada.')
    def selected(dataset,selection):
        return {r['unit_code']:r for r in dataset['rows'] if
            (not selection.get('entity_code') or r['entity_code']==selection['entity_code']) and
            (not selection.get('unit_code') or r['unit_code']==selection['unit_code'])}
    ra,rb=selected(a,request['a']),selected(b,request['b'])
    common=sorted(ra.keys() & rb.keys())
    if not common: reasons.append('No hay unidades comunes.')
    if ra.keys()!=rb.keys() and request['coverage_mode']=='exact':
        reasons.append('Coberturas distintas; se requiere igualdad o selección explícita de intersección.')
    if request['a']['denominator']!=request['b']['denominator']:
        reasons.append('Los denominadores seleccionados son distintos.')
    return ra,rb,common,dict(comparable=not reasons,reasons=reasons,coverage_mode=request['coverage_mode'],
        units_a=len(ra),units_b=len(rb),units_common=len(common),
        excluded_only_a=len(ra.keys()-rb.keys()),excluded_only_b=len(rb.keys()-ra.keys()),
        warning='Compatibilidad técnica de metadatos; la evidencia de las equivalencias no se verifica automáticamente.')


def compare_unit(ra,rb,a,b,request):
    metrics={}
    sa,sb=a['metadata']['source'],b['metadata']['source']
    na,nb=ra.get('nominal_list'),rb.get('nominal_list')
    if not sa.get('cutoff_on') or not sb.get('cutoff_on') or sa['cutoff_on']>=sb['cutoff_on']:
        metrics['IT02']=unavailable('Los cortes de lista nominal deben estar identificados y ordenados.')
    elif na is None or nb is None or na<=0:
        metrics['IT02']=unavailable('Lista nominal faltante o base A igual a cero.')
    else:
        metrics['IT02']=measured(Fraction((nb-na)*100,na),nb-na,na)
    va={v['option_code']:v['votes'] for v in ra['options']}
    vb={v['option_code']:v['votes'] for v in rb['options']}
    mapping={m['option_a']:m['option_b'] for m in request['option_mapping']}
    selected=request['a'].get('option_code')
    target=request['b'].get('option_code')
    party=a['metadata']['vote_basis']=='party'
    if not party or not selected or mapping.get(selected)!=target or target is None:
        reason='Variaciones partidistas requieren base party y partido seleccionado con equivalencia documentada.'
        metrics['IP03']=unavailable(reason); metrics['IP04']=unavailable(reason)
    elif va.get(selected) is None or vb.get(target) is None or any(
            row.get('total_votes') is not None and value>row['total_votes']
            for row,value in ((ra,va.get(selected)),(rb,vb.get(target)))):
        metrics['IP03']=unavailable('Falta la votación en A o B; no se imputa cero.')
        metrics['IP04']=unavailable('Falta la votación en A o B; no se imputa cero.')
    else:
        x,y=va[selected],vb[target]
        metrics['IP03']=measured(y-x,y-x)
        metrics['IP04']=measured(Fraction((y-x)*100,x),y-x,x) if x>0 else unavailable('La votación base A es cero; la variación porcentual no está definida.')
    valid_a,reason_a=composition(ra); valid_b,reason_b=composition(rb)
    complete=(set(mapping)==set(va) and set(mapping.values())==set(vb))
    if party and complete and not reason_a and not reason_b:
        if request['a']['denominator']=='valid_votes':
            da,db=valid_a,valid_b
            volatility=sum((abs(Fraction(va[k]*100,da)-Fraction(vb[v]*100,db)) for k,v in mapping.items()),Fraction())/2
            metrics['IT08']=measured(volatility,denominator=None)
            metrics['IP12']=dict(metrics['IT08'])
        else:
            metrics['IT08']=unavailable('Volatilidad requiere cuotas sobre votos válidos de partidos, no sobre emitidos.')
            metrics['IP12']=dict(metrics['IT08'])
    else:
        reason='Volatilidad requiere base party, componentes completos y homologación exhaustiva uno a uno; no se asignan ceros a opciones ausentes.'
        metrics['IT08']=unavailable(reason); metrics['IP12']=unavailable(reason)
    if a['metadata']['vote_basis']=='candidacy' and complete and not reason_a and not reason_b and len(va)>=2 and len(vb)>=2:
        wa=[k for k,v in va.items() if v==max(va.values())]
        wb=[k for k,v in vb.items() if v==max(vb.values())]
        metrics['IT07']=measured(mapping[wa[0]]!=wb[0],winner_a=wa[0],winner_b=wb[0]) if len(wa)==len(wb)==1 else unavailable('Empate: no hay ganador único en alguna elección.')
    else:
        metrics['IT07']=unavailable('Se requieren candidaturas completas y homologadas; no es un indicador de cambio de gobierno.')
    return metrics


def compare(a,b,request):
    ra,rb,codes,compat=comparability(a,b,request)
    items=[]
    blocked={c:unavailable('; '.join(compat['reasons']),'blocked') for c in ('IP03','IP04','IP12','IT02','IT07','IT08')}
    if compat['comparable']:
        items=[dict(unit_code=c,name=rb[c]['name'],metrics=compare_unit(ra[c],rb[c],a,b,request)) for c in codes]
        summary=compare_unit(combine([ra[c] for c in codes]),combine([rb[c] for c in codes]),a,b,request)
        for code in ('IT08','IP12'):
            if any(item['metrics'][code]['value'] is None for item in items):
                summary[code]=unavailable('Alguna unidad no tiene composición y homologación completas; el agregado no debe ocultarlo.')
        if any(item['metrics']['IP03']['value'] is None for item in items):
            for code in ('IP03','IP04'):
                summary[code]=unavailable('Falta votación partidista compatible en alguna unidad de la cobertura común.')
        summary['IT07']=unavailable('Consultar cambio de ganador por unidad; no se agrega como un cambio de gobierno.')
    else:
        summary=blocked
    page=[r for r in items if r['unit_code']>request['b']['after']]
    returned=page[:request['b']['limit']]
    return dict(engine_version=ENGINE_VERSION,catalog_version=CATALOG_VERSION,request=request,
        provenance=dict(a=provenance(a),b=provenance(b)),comparability=compat,summary=summary,items=returned,
        next_after=returned[-1]['unit_code'] if len(page)>len(returned) else None)
