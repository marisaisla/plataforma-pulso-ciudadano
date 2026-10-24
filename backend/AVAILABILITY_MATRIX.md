# Disponibilidad de las 45 variables para el dashboard

Corte: 22 de octubre de 2026. Catálogo y motor revisados: 2026-10-22 / 1.0.0.

## Resultado de la revisión

Esta es una matriz de preparación del dashboard, no una certificación de fuentes ni una implementación nueva. Se consultó PostgreSQL con transacciones READ ONLY, se revisaron esquema y código, metadatos y contenido textual de las 37 fichas de encuestas y 73 registros de evidencia. Se comprobó la existencia de los 36 archivos registrados; no se hizo lectura exhaustiva ni validación externa de cada documento. No se modificaron datos, cargas, perfiles, expedientes, servicios ni el motor.

Las 45 tarjetas pueden aparecer en el dashboard, pero no hay 45 mediciones verificadas listas para publicar. La disponibilidad depende del perfil, territorio, periodo y fuente seleccionados. Un estado «Parcial» no autoriza mostrar automáticamente un valor numérico.

- **Exploratorio:** el motor actual puede devolver valores para parte de las unidades heredadas, con advertencia y filtros. No es una medición oficialmente acreditada.
- **Parcial:** existen insumos relacionados aprovechables; faltan extracción, revisión o integración. Se pueden presentar referencias o componentes documentados, claramente identificados.
- **Bloqueado:** la fórmula ya está implementada, pero los lotes actuales no cumplen los requisitos para calcular este indicador.
- **Pendiente:** no se identificó el insumo específico estructurado suficiente en el inventario. Puede haber material dentro de documentos aún no extraído; no significa que deba rehacerse el expediente.

| Estado | Variables |
|---|---:|
| Exploratorio | 4 |
| Parcial | 17 |
| Bloqueado | 12 |
| Pendiente | 12 |

## Inventario confirmado

| Información existente | Registros | Observación |
|---|---:|---|
| Perfiles / cargos / relaciones territoriales | 11 / 11 / 650 | Reutilizar; no reconstruir expedientes. |
| Documentos de referencia | 36 | 36 archivos existentes; nueve dictámenes y 22 referencias de cartografía histórica. Existencia no acredita contenido. |
| Encuestas de viabilidad | 37 | 35 con resultado, 24 con muestra, 34 con fecha y 24 con URL. Texto en metodología en 37 no equivale a ficha completa. Son registros/reactivos; no 37 estudios independientes. |
| Evidencias / puntuaciones electorales | 73 / 68 | Códigos anteriores diferentes de IC/IP/IT; no hay correspondencia automática. Puntuación 0–100 no es porcentaje medido. |
| Evaluaciones de variables de viabilidad | 109 | Algunas tienen métricas propias de seguimiento; no son las 45 mediciones del catálogo. |
| Escenarios de coalición / estructura operativa | 13 / 51 | No acreditan convenios ni órganos institucionales de partidos. |
| Publicaciones / fuentes | 818 / 81 | Publicaciones de siete perfiles; 661 con fecha. No equivalen a universo de medios. |
| Observaciones territoriales INEGI y fuentes registradas | 4.756 | Diversos municipios, periodos, códigos y unidades; no cobertura homogénea de todos los territorios. |
| Cuestionarios operativos / respuestas | 1 / 1 | No sirven como encuesta electoral representativa por el hecho de estar capturados. |
| Cargas históricas / elecciones | 82 / 24 | Todos los lotes legacy_snapshot y legacy_reported. |
| Originales / normalizados / pendientes | 37.981 / 36.911 / 1.070 | No se corrigieron ni incluyeron pendientes en cálculos. |
| Filas de opciones de voto | 759.949 | No equivale a votos emitidos ni a opciones partidistas acreditadas. |

## Comprobación con el motor actual

Se recorrieron los 82 lotes con las reglas reales de unit_metrics en modo exploratorio y proxy activado, sin persistir resultados. Los conteos son observaciones unidad–lote, no territorios únicos ni electores únicos. No sumar elecciones, versiones ni niveles de cobertura.

| Variable | Observaciones con valor / 36.911 |
|---|---:|
| IT01 | 33,636 |
| IT03 | 33,535 |
| IT04 | 33,535 |
| IT05 | 36,851 |

Las otras variables electorales implementadas están bloqueadas por requisitos de atribución o comparabilidad con estos lotes. Los agregados de un lote pueden quedar sin valor aunque algunas unidades sí sean calculables. Los 16 cálculos implementados son cuatro explorables y doce bloqueados con los datos actuales; no son 16 tarjetas listas con valor validado.

## Matriz completa

La columna «Motor» describe soporte de código, no disponibilidad real. «No» significa que falta integrar/desarrollar la consulta o cálculo correspondiente; no que necesariamente falten todas sus fuentes.

| Código | Variable | Estado | Motor | Insumo comprobado | Qué se puede mostrar | Qué falta |
|---|---|---|---|---|---|---|
| IC01 | Conocimiento del candidato | Parcial | No | 3 evidencias name_recognition; mezclan una referencia porcentual, apreciaciones y puntuaciones. | Referencia del expediente, no porcentaje certificado. | Identificar reactivo, universo, fecha y ficha de la medición; extraer el valor sin convertir puntuaciones en porcentajes. |
| IC02 | Opinión favorable | Parcial | No | 3 evidencias favorable_opinion; incluyen saldo de opinión y una puntuación de rechazo. | Referencias con sus limitaciones. | Separar opinión favorable, desfavorable, aprobación y saldo; recuperar estudio y pregunta originales. |
| IC03 | Opinión desfavorable | Pendiente | No | No hay campo estructurado específico de opinión desfavorable en las encuestas inventariadas. | Sin medición validada. | Extraer o incorporar respuestas desfavorables, denominador, pregunta y ficha. |
| IC04 | Saldo de opinión | Parcial | No | Una nota de favorable_opinion cita un saldo; no hay componentes homogéneos estructurados. | Saldo citado como referencia documental, sin recalcularlo. | Obtener favorables y desfavorables del mismo estudio; implementar diferencia en puntos. |
| IC05 | Preferencia declarada | Parcial | No | 37 registros en viability_surveys; 35 con profile_result_pct, pero mezclan aprobación, internas y careos. | Mediciones individuales correctamente etiquetadas tras clasificación; nunca promedio indiscriminado. | Normalizar tipo de pregunta, escenario, universo y fuente; excluir estimaciones sin ficha y referencias no personales. |
| IC06 | Evolución de preferencia | Parcial | No | Hay cortes marzo/junio/julio para internas y careos; también cambian alianzas y métodos entre registros. | Serie de mediciones separadas; todavía sin evolución automática. | Acreditar pares con misma pregunta, escenario, universo y método; implementar diferencia en puntos. |
| IC07 | Indecisión declarada | Parcial | No | Hay porcentajes de indecisión en notes de careos y JSON; 3 evidencias undecided_voters no equivalen a resultados. | Dato reportado por pregunta, una vez extraído y revisado. | Separar no sabe, ninguno e indecisión; estructurar categoría, porcentaje, universo y fuente. |
| IC08 | Experiencia pública | Parcial | No | 11 profile_positions; 9 con inicio y 4 con término; expedientes existentes. | Trayectoria declarada y fechas disponibles. | Relacionar cada cargo con evidencia primaria y revisar periodos; exponer listado, no inventar índice. |
| IC09 | Historial electoral | Parcial | No | 4 evidencias electoral_experience y resultados históricos; una evidencia cita declaración de validez. | Antecedentes documentados de forma individual. | Vincular identidad del perfil con candidatura, elección, cargo y resultado; los nombres de columnas no bastan. |
| IC10 | Elegibilidad | Parcial | No | Expedientes y notas de riesgo mencionan elegibilidad; no hay evaluación de requisitos estructurada. | Pendiente de verificación, mostrando referencias existentes. | Registrar requisitos aplicables, fecha, documento y resultado de revisión; no inferir elegibilidad de una puntuación. |
| IC11 | Situación de nominación | Parcial | No | 4 evidencias nomination_probability; escenarios y preferencias internas, no acreditación de nominación. | Escenario o situación por verificar. | Vincular acuerdo o resolución de registro y vigencia; no confundir probabilidad o preferencia con nominación. |
| IC12 | Antecedentes jurídicos | Pendiente | No | 4 notas reputational_risk no acreditan procedimientos ni su estado procesal. | Sin antecedentes jurídicos verificados; ausencia de dato no significa ausencia de procedimientos. | Revisar expediente y estructurar únicamente documentos públicos de procedimientos, fechas y estado. |
| IC13 | Declaraciones de intereses | Pendiente | No | No se identificó registro específico de declaraciones de intereses en el inventario. | Sin información verificada. | Localizar declaraciones en los expedientes o incorporar fuente, fecha y alcance; no duplicar perfiles. |
| IC14 | Propuestas públicas | Pendiente | No | Hay documentos de referencia y publicaciones, pero no inventario acreditado de propuestas por perfil. | Documentos relacionados; sin conteo de compromisos todavía. | Extraer propuestas concretas, tema, autor, fecha y enlace; distinguir planes de gobierno de compromisos del perfil. |
| IC15 | Cobertura mediática | Parcial | No | 818 publicaciones de 7 perfiles, 661 con fecha y 818 con URL; 81 fuentes. | Conteo del material recopilado, no cobertura total de medios. | Delimitar corpus y periodo, deduplicar, clasificar medios/temas y construir agregación API. |
| IP01 | Votación absoluta | Bloqueado | Individual | Motor implementado; los 82 lotes son legacy_reported. | Opciones reportadas con etiqueta heredada, no voto oficial por partido. | Acreditar atribución party con fuente y reglas; preparar lote conciliado sin sobrescribir originales. |
| IP02 | Porcentaje de votación | Bloqueado | Individual | Motor implementado; falta atribución party acreditada y conciliación completa. | Sin porcentaje partidista calculado. | Resolver base partidista y denominador válido/emitido, componentes y cobertura. |
| IP03 | Variación de votos | Bloqueado | Comparativo | Motor comparativo implementado; elecciones 2021/2024 heredadas. | Sin variación automática. | Acreditar fechas, cargo, principio, proceso, misma geografía/cobertura y equivalencia de partido. |
| IP04 | Variación porcentual | Bloqueado | Comparativo | Motor implementado; mismas limitaciones de IP03. | Sin variación porcentual automática. | Resolver comparabilidad de IP03 y exigir votos iniciales mayores que cero. |
| IP05 | Presencia electoral | Bloqueado | Individual | Motor implementado; opciones heredadas sin identidad party acreditada. | Sin conteo de presencia partidista. | Conocer el partido y su votación en todas las unidades; ausente no equivale a cero. |
| IP06 | Participación en coaliciones | Parcial | No | 13 viability_coalition_scenarios y evidencias coalition_alliances; son escenarios, no convenios históricos. | Escenarios identificados como tales. | Relacionar convenios oficiales, integrantes, elección y vigencia; implementar registro consultable. |
| IP07 | Votación de coaliciones | Pendiente | No | Votos heredados y escenarios de coalición no contienen atribución oficial acreditada. | Sin votación oficial de coalición. | Incorporar convenios, combinaciones y reglas oficiales; desarrollar cálculo sin doble conteo. |
| IP08 | Representación legislativa | Pendiente | No | No se encontró catálogo estructurado de escaños adjudicados. | Sin información de representación completa. | Recuperar acuerdos de asignación, cargo, principio, partido y elección; no deducir de votos. |
| IP09 | Gobiernos obtenidos | Pendiente | No | Cargos de perfiles y evidencias aisladas no constituyen universo de gobiernos adjudicados. | Antecedentes individuales, sin total de gobiernos obtenidos. | Estructurar declaraciones de validez y cargos ejecutivos por elección y partido/coalición. |
| IP10 | Alternancia | Pendiente | No | No hay serie acreditada de partidos o coaliciones gobernantes. | Sin alternancia gubernamental calculada. | Relacionar gobiernos adjudicados entre periodos y homologar coaliciones; cambio de ganador no basta. |
| IP11 | Concentración geográfica del voto | Bloqueado | Individual | Motor implementado; falta atribución party y cobertura completa. | Sin distribución partidista acreditada. | Resolver IP01 y cobertura; calcular distribución dentro del lote, no porcentaje electoral. |
| IP12 | Volatilidad partidista | Bloqueado | Comparativo | Motor implementado; no hay pares acreditados con partidos homologados. | Sin volatilidad partidista. | Homologar todas las opciones, fechas, geografía, universo y denominador de dos elecciones. |
| IP13 | Identificación partidista | Pendiente | No | El inventario no identifica una pregunta estructurada de identificación partidista. | Sin medición disponible. | Revisar estudios existentes por pregunta específica; preferencia electoral no equivale a identificación. |
| IP14 | Estructura institucional | Pendiente | No | 51 viability_structure_records describen operación territorial, no órganos partidistas acreditados. | Sin estructura institucional partidista verificada. | Recuperar dirigencias y órganos oficiales con vigencia; no reutilizar personal de campo como sustituto. |
| IP15 | Financiamiento público | Pendiente | No | viability_resource_records tiene 0 registros; capacidades de campaña tampoco equivalen a financiamiento público. | Sin monto disponible. | Incorporar acuerdos e informes por partido, ejercicio, concepto y moneda; desarrollar consulta. |
| IT01 | Lista nominal | Exploratorio | Individual | 33.636 de 36.911 resultados normalizados tienen nominal_list. | Lista nominal reportada por unidad/lote con advertencia heredada. | Conservar fecha de corte, fuente y cobertura; impedir totales que dupliquen niveles o elecciones. |
| IT02 | Crecimiento de lista nominal | Bloqueado | Comparativo | Motor implementado; lista nominal histórica disponible parcialmente. | Sin crecimiento comparable automático. | Acreditar cortes y cartografía equivalentes; resolver faltantes y exigir base inicial positiva. |
| IT03 | Participación electoral | Exploratorio | Individual | Hay total_votes y nominal_list parcial; no conteo censal de votantes. | Solo proxy explícito votos emitidos/lista nominal en unidades compatibles. | Mostrar etiqueta proxy; para participación en personas incorporar conteo de votantes y corte aplicable. |
| IT04 | Abstencionismo | Exploratorio | Individual | Depende de IT03 y su mismo universo. | Solo complemento del proxy, identificado como aproximación. | Mantener mismo filtro y denominador; para indicador medido resolver insumos de IT03. |
| IT05 | Votos nulos | Exploratorio | Individual | 36.911 resultados tienen total_votes y null_votes; validar denominador en cada caso. | Nulos/emitidos cuando total>0 y nulos estén dentro del universo. | Mantener acreditación pendiente y cobertura; no sumar secciones, municipios y distritos entre sí. |
| IT06 | Margen electoral | Bloqueado | Individual | Motor implementado; los lotes no tienen base candidacy acreditada. | Sin margen de candidaturas calculado. | Consolidar candidaturas oficiales, al menos dos opciones y componentes conciliados; conservar empates. |
| IT07 | Cambio de ganador territorial | Bloqueado | Comparativo | Motor implementado; faltan candidaturas y pares acreditados. | Sin cambio de ganador calculado. | Acreditar comparabilidad y equivalencias; distinguir ganador electoral de gobierno obtenido. |
| IT08 | Volatilidad electoral | Bloqueado | Comparativo | Motor implementado; requiere mismos insumos de IP12. | Sin volatilidad electoral. | Preparar partidos homologados y dos universos completos; es misma fórmula que IP12, no evidencia independiente. |
| IT09 | Concentración del voto | Bloqueado | Individual | Motor HHI implementado; atribución party y composición completa no acreditadas. | Sin concentración oficial del voto. | Conciliar opciones partidistas y válidos; aplicar suma de cuadrados sin mezclar coaliciones y partidos. |
| IT10 | Población por edad y sexo | Parcial | No | territorial_indicators contiene totales por sexo y algunos grupos de edad (ITER y series locales). | Valores cargados por municipio, periodo y fuente; cobertura parcial. | Mapear códigos, unidades y grupos; no afirmar cruce edad×sexo completo ni repartir municipios entre secciones. |
| IT11 | Escolaridad | Parcial | No | Existen ITER_GRAPROES, chih_escolaridad_promedio, 1005000038 y analfabetismo. | Escolaridad promedio u observaciones existentes, con universo explícito. | Definir submedidas; una media no es distribución por nivel. Resolver duplicados de fuentes y desarrollar API. |
| IT12 | Condiciones socioeconómicas | Parcial | No | Hay PEA, población ocupada/desocupada y otras variables; no se identificó serie de pobreza CONEVAL en estas cargas. | Componentes socioeconómicos disponibles por separado. | Definir componentes y universos; incorporar pobreza si se requiere y no inventar un índice compuesto. |
| IT13 | Acceso a servicios | Parcial | No | Hay porcentajes y conteos de agua, drenaje, electricidad, internet y vivienda habitada. | Servicios individuales cuando fuente, unidad y denominador coincidan. | Mapear porcentajes vs conteos y denominadores de vivienda/población; sin promedio simple de porcentajes. |
| IT14 | Ruralidad y dispersión | Pendiente | No | El inventario municipal no identifica población por tipo/tamaño de localidad; cartografía no basta. | Sin ruralidad o dispersión calculada. | Revisar insumos cartográficos existentes e incorporar población por localidad y clasificación compatible; definir medida. |
| IT15 | Características geográficas | Parcial | No | 22 documentos de cartografía histórica y uno de revisión; existen geographies/units sin medidas de superficie o accesibilidad. | Versiones y referencias cartográficas, no índice geográfico completo. | Verificar capas, vigencia, geometrías, unidades y metodología; vincular a territorios sin convertir referencias en mediciones. |

## Hallazgos que afectan el diseño

1. **Encuestas:** profile_result_pct mezcla aprobación, internas y careos. Por ejemplo, los registros 22–24 son aprobación; no deben alimentar IC05. El registro 3 se describe como estimación sin ficha y con instrucción de exclusión cuantitativa. Los registros 34 y 38 se declaran reactivos del mismo levantamiento; no son dos encuestas independientes. Un valor numérico no implica que deba publicarse como medición validada.
2. **Puntuaciones heredadas:** hay notas de conocimiento o rechazo expresadas en puntos y otras en porcentajes. No convertir scores ni métricas de avance del expediente a resultados de encuesta. Los estados «Documentada» son estados de captura, no certificación automática.
3. **Temporalidad electoral:** todos los lotes actuales están pendientes de acreditación. El catálogo ofrece fórmulas de comparación, pero las fechas, geografía y opciones deben homologarse antes de activarlas. Las 3.899 observaciones de conciliación de la migración previa no se resuelven en esta revisión.
4. **INEGI:** ya hay escolaridad, grupos de edad, sexo, empleo, vivienda y servicios. Hace falta correspondencia de códigos, territorios, periodos y denominadores. Las cargas identifican la cobertura censal Calkiní/Dzitbalché; no redistribuir valores automáticamente a una división territorial distinta. Valores de distinto corte no se suman ni sustituyen entre sí.
5. **Tipos de tarjeta:** experiencia, nominación, elegibilidad o declaraciones se muestran como registros/estados con evidencia; no convertir las 45 variables en 45 porcentajes ni inventar puntuaciones globales.

## Orden propuesto para construir el dashboard

1. Crear la vista de las 45 fichas con filtros y estados, y conectar IT01/IT05 en modo exploratorio e IT03/IT04 únicamente como proxy explícito. Mostrar cobertura, corte y fuente por tarjeta.
2. Reutilizar INEGI para IT10–IT13 por componente y publicar referencias de cargos, expedientes y cartografía de IC08/IT15. Agregar adaptadores/API y verificación de unidades; no recargar todo ni rehacer perfiles.
3. Clasificar las encuestas existentes y estructurar sus reactivos para IC01/IC02/IC04–IC07 donde la fuente lo permita. Revisar comparabilidad antes de habilitar evolución y excluir referencias insuficientes.
4. Preparar lotes electorales acreditados para desbloquear los doce cálculos ya implementados. Este trabajo puede hacerse por elección/territorio, sin resolver necesariamente los 1.070 pendientes completos primero.
5. Incorporar únicamente los insumos documentales específicos aún no identificados para las variables pendientes. Integrar evidencias existentes antes de solicitar nuevas cargas.

Para el dashboard faltan contratos de respuesta por tarjeta, integración de estas fuentes, tratamiento de cobertura y una pantalla. La persistencia del catálogo y ejecuciones es otro trabajo pendiente, no realizado por esta auditoría. No se requiere ni se propone aquí crear un modelo OLAP.

## Reproducibilidad y límites

Inventario generado mediante consultas de conteo y metadatos en READ ONLY y reglas del código actual. Los conteos son un corte, no se actualizan automáticamente. No se efectuó revisión legal, estadística ni documental externa, ni lectura exhaustiva de los 36 archivos. No se afirma inexistencia absoluta de insumos dentro de PDFs o capas no extraídos. Una disponibilidad definitiva por perfil/territorio requiere revisar las fuentes concretas y no se desprende de estos conteos globales.
