"""Catálogo maestro del modelo de inteligencia; disponibilidad no equivale a datos cargados."""
CATALOG_VERSION = '2026-10-22'
ENGINE_VERSION = '1.0.0'

SINGLE = {'IP01','IP02','IP05','IP11','IT01','IT03','IT04','IT05','IT06','IT09'}
COMPARISON = {'IP03','IP04','IP12','IT02','IT07','IT08'}

# Código, indicador, definición/fórmula operativa, unidad, insumo requerido.
ROWS = [
('IC01','Conocimiento del candidato','Personas que declaran conocer / respuestas aplicables × 100','porcentaje','Encuesta con ficha técnica'),
('IC02','Opinión favorable','Respuestas favorables / respuestas aplicables × 100','porcentaje','Encuesta con ficha técnica'),
('IC03','Opinión desfavorable','Respuestas desfavorables / respuestas aplicables × 100','porcentaje','Encuesta con ficha técnica'),
('IC04','Saldo de opinión','Opinión favorable − opinión desfavorable de la misma medición','puntos porcentuales','Encuesta comparable'),
('IC05','Preferencia declarada','Respuestas de preferencia / denominador explícito × 100','porcentaje','Encuesta y pregunta electoral'),
('IC06','Evolución de preferencia','Preferencia B − preferencia A, con metodología comparable','puntos porcentuales','Serie de encuestas comparables'),
('IC07','Indecisión declarada','Respuestas indecisas / denominador explícito × 100','porcentaje','Encuesta con pregunta y universo'),
('IC08','Experiencia pública','Cargos, funciones y periodos comprobados documentalmente','registro','Expediente y fuentes primarias'),
('IC09','Historial electoral','Candidaturas anteriores y sus resultados identificados','registro','Identidad de candidaturas acreditada'),
('IC10','Elegibilidad','Requisitos acreditados, pendientes o no verificables','estado','Normativa y expediente'),
('IC11','Situación de nominación','Registro y resoluciones de nominación documentados','estado','Documentos de partidos o autoridad'),
('IC12','Antecedentes jurídicos','Procedimientos públicos y estado procesal, sin presumir responsabilidad','registro','Expediente documental actualizado'),
('IC13','Declaraciones de intereses','Existencia, fecha y alcance de las declaraciones','registro','Registros públicos'),
('IC14','Propuestas públicas','Compromisos verificables por tema y fecha','registro','Documentos y publicaciones'),
('IC15','Cobertura mediática','Menciones por tema y periodo con universo documentado','conteo','Monitoreo con cobertura y deduplicación'),
('IP01','Votación absoluta','Votos atribuidos oficialmente al partido seleccionado','votos','Base party y opción explícita'),
('IP02','Porcentaje de votación','Votos del partido / denominador seleccionado × 100','porcentaje','Base party, componentes completos y denominador'),
('IP03','Variación de votos','Votos del partido B − votos del partido A','votos','Elecciones comparables y equivalencia de opciones'),
('IP04','Variación porcentual','(Votos B / votos A − 1) × 100; A > 0','porcentaje','Elecciones comparables y equivalencia de opciones'),
('IP05','Presencia electoral','Unidades observadas con votos del partido > 0','unidades','Opción conocida en todas las unidades del lote'),
('IP06','Participación en coaliciones','Convenios y elecciones de participación comprobados','registro','Convenios y catálogo de coaliciones'),
('IP07','Votación de coaliciones','Votos atribuidos según las reglas oficiales de cada proceso','votos','Atribución oficial y miembros de coalición'),
('IP08','Representación legislativa','Escaños adjudicados por elección','escaños','Declaraciones de asignación de escaños'),
('IP09','Gobiernos obtenidos','Cargos ejecutivos adjudicados históricamente','cargos','Declaraciones de validez y cargos'),
('IP10','Alternancia','Cambio documentado del partido o coalición gobernante','estado','Identidad de gobiernos y coaliciones'),
('IP11','Concentración geográfica del voto','Distribución: votos del partido en unidad / votos del partido en cobertura observada × 100','porcentaje','Base party completa en el lote; no es porcentaje electoral'),
('IP12','Volatilidad partidista','0.5 × suma de diferencias absolutas entre cuotas partidistas A y B','puntos porcentuales','Partidos homologados, cobertura y denominador compatibles'),
('IP13','Identificación partidista','Identificación declarada / respuestas aplicables × 100','porcentaje','Encuesta y denominador explícito'),
('IP14','Estructura institucional','Órganos y dirigencias acreditados a una fecha','registro','Registros partidistas'),
('IP15','Financiamiento público','Montos asignados y ejercicio reportado por periodo','moneda','Acuerdos e informes financieros'),
('IT01','Lista nominal','Electores de la lista nominal reportada, conservando corte y cobertura','electores','Lista nominal y fecha de corte'),
('IT02','Crecimiento de lista nominal','(Lista B / lista A − 1) × 100; A > 0','porcentaje','Cortes temporales y geografía compatibles'),
('IT03','Participación electoral','Votantes / lista nominal aplicable × 100','porcentaje','Votantes medidos; proxy con votos emitidos solo por elección explícita'),
('IT04','Abstencionismo','100 − participación del mismo universo y corte','porcentaje','Participación válida o proxy identificado'),
('IT05','Votos nulos','Votos nulos / votos emitidos × 100','porcentaje','Total emitido > 0 y nulos entre 0 y total'),
('IT06','Margen electoral','Votos de primera candidatura − segunda; puntos sobre votos válidos de candidaturas','votos','Base candidacy consolidada, completa y al menos dos opciones'),
('IT07','Cambio de ganador territorial','Ganador de B distinto del ganador de A tras homologación; empate sin ganador único','booleano','Candidaturas homologadas y elecciones comparables; no acredita cambio de gobierno'),
('IT08','Volatilidad electoral','0.5 × suma de diferencias absolutas entre cuotas partidistas A y B','puntos porcentuales','Base party con universo de opciones homologado completo'),
('IT09','Concentración del voto','HHI = suma de cuadrados de cuotas partidistas (escala 0–1)','índice 0–1','Base party completa y votos válidos > 0'),
('IT10','Población por edad y sexo','Habitantes por grupo, periodo y territorio de la fuente','habitantes','Datos INEGI y correspondencias territoriales verificadas'),
('IT11','Escolaridad','Niveles educativos según universo de la fuente','distribución','INEGI con definición y cobertura'),
('IT12','Condiciones socioeconómicas','Empleo, pobreza y variables con metodología identificada','según fuente','INEGI/CONEVAL, periodos y cobertura'),
('IT13','Acceso a servicios','Viviendas o población con servicio / universo aplicable × 100','porcentaje','INEGI y correspondencias territoriales'),
('IT14','Ruralidad y dispersión','Población por tipo de localidad y distribución espacial','según fuente','INEGI y cartografía compatible'),
('IT15','Características geográficas','Superficie, límites, localidades y accesibilidad documentados','según fuente','Cartografía histórica y metodología'),
]


def catalog():
    return [dict(code=c, family=c[:2], name=n, definition=f, formula=f, unit=u, required_inputs=r,
                 engine_support='single' if c in SINGLE else 'comparison' if c in COMPARISON else 'pending_inputs',
                 version=CATALOG_VERSION, geographic_levels=['entity','municipality','federal_district','local_district','section'],
                 periodicity='Según publicación, proceso o medición; conservar corte y versión',
                 source_type='Encuesta o evidencia documental' if c.startswith('IC') else r)
            for c,n,f,u,r in ROWS]
