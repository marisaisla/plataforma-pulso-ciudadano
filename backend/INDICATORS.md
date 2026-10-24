# Fase 2 — Motor de indicadores electorales

API **0.19.0**, motor **1.0.0**, catálogo **2026-10-22**. La fase implementa definiciones,
cálculos reproducibles, controles de calidad, pruebas y visualización sobre la base histórica.
No modifica resultados, perfiles, cargas heredadas, INEGI ni las consultas de los visores actuales.
No requiere una migración SQL adicional a las de la Fase 1.

La [matriz de disponibilidad de las 45 variables](AVAILABILITY_MATRIX.md) documenta
el inventario real revisado el 22 de octubre de 2026, los bloqueos y el trabajo
necesario para integrarlas en un dashboard. Soporte de cálculo no implica datos disponibles.
El [dashboard de las 45 variables](DASHBOARD.md) integra sus estados y observaciones INEGI
en una pantalla adicional, conservando este motor para el análisis y las comparaciones.

## Alcance del catálogo

El catálogo contiene los 45 indicadores IC/IP/IT del modelo integral. Cada ficha tiene
código, familia, nombre, definición, fórmula/criterio, unidad, insumos, niveles, periodicidad
y versión. La cobertura y la evidencia efectiva pertenecen a cada observación, no a la ficha.

El motor implementa **16 indicadores electorales**, sujetos a disponibilidad y calidad de
los datos. Los otros 29 conservan su definición con estado `pending_inputs`: requieren
encuestas con metodología, expedientes, adjudicación de cargos, convenios, datos financieros
o correspondencias territoriales de INEGI. No se generan números para completar el catálogo
ni se reutilizan las encuestas operativas de campo como si fueran encuestas electorales.

| Código | Cálculo implementado |
| --- | --- |
| IP01 | Votos del partido seleccionado |
| IP02 | Votos del partido / votos válidos o emitidos, según selección, × 100 |
| IP03 | Votos B − votos A del partido homologado |
| IP04 | (Votos B / votos A − 1) × 100, con A > 0 |
| IP05 | Número de unidades observadas con votos del partido > 0 |
| IP11 | Distribución territorial: votos del partido en la unidad / votos de ese partido en la cobertura × 100 |
| IP12, IT08 | Volatilidad: mitad de la suma de diferencias absolutas entre cuotas partidistas comparables |
| IT01 | Lista nominal reportada, con fuente, corte y cobertura |
| IT02 | (Lista B / lista A − 1) × 100, con A > 0 y cortes ordenados |
| IT03 | Disponible como proxy explícito: votos emitidos / lista nominal × 100 |
| IT04 | 100 − participación del mismo universo; proxy si IT03 es proxy |
| IT05 | Votos nulos / emitidos × 100 |
| IT06 | Diferencia entre primera y segunda candidatura; incluye margen en puntos sobre válidos de candidaturas |
| IT07 | Cambio de ganador territorial homologado, sin inferir cambio de gobierno |
| IT09 | HHI: suma de cuadrados de cuotas partidistas, escala 0–1 |

Los conteos de personas que votaron y los votos emitidos no son intercambiables sin
documentar su universo. El [INE describe los conteos censales](https://portal.ine.mx/transparencia/datos-abiertos/visualizacion-datos/conteos-censales-participacion/)
basados en la participación de la ciudadanía. Como Fase 1 no incorpora un campo de conteo
censal de votantes, IT03/IT04 quedan sin calcular por defecto. Solo al seleccionar
`participation_proxy=true` se muestra la aproximación con votos emitidos, identificada
como `proxy`. No se imputa ni se presenta como participación oficial medida en personas.

La volatilidad emplea diferencias de cuotas agregadas, conforme a la formulación estudiada
en [On the measurement of electoral volatility](https://www.sciencedirect.com/science/article/pii/S0165489623000872).
No identifica transferencias individuales de voto. IP11 describe distribución espacial
observada; no es una probabilidad ni una puntuación de oportunidad electoral.

## Denominadores y calidad

`valid_votes = total_votes − null_votes − unregistered_votes`.
Para cuotas partidistas y HHI se exige que las opciones conocidas concilien completamente
con esos válidos. IP02 permite elegir `valid_votes` o `emitted_votes`, dejando explícitos
numerador y denominador. La volatilidad usa cuotas sobre válidos de partidos.

- Un dato ausente permanece null; una opción ausente no representa cero.
- Denominador cero, componentes incompletos o incoherentes producen `unavailable`, con motivo.
- Una participación proxy mayor a 100% queda sin calcular; no se recorta a 100%.
- Los agregados usan sumas de numeradores y denominadores completos; nunca el promedio
  simple de porcentajes territoriales. Si falta un total requerido, no se presenta una
  suma parcial como si fuera la cobertura completa.
- IP05 e IP11 requieren conocer la opción del partido en todas las unidades observadas.
- IT06 requiere `candidacy`, al menos dos opciones y composición conciliada. Un empate
  conserva margen cero y no se elige un ganador por orden alfabético.
- No se declara ganador global sumando distritos o municipios con cargos distintos.
- HHI y cuotas partidistas requieren `party`; `ballot_combination` no sustituye una
  candidatura ni votos oficialmente atribuidos a partidos.

El resumen usa toda la cobertura seleccionada. La tabla y gráfica se paginan; se indica
que representan la página actual. `metric_coverage` informa cuántas unidades tienen un
valor calculable por indicador. No se consolida automáticamente más de un lote, nivel,
base de votos o versión. Un lote parcial no se presenta como toda una entidad.

## Fuentes estructuradas y exploración heredada

`mode=validated` es el valor por defecto. Exige una carga con estructura oficial declarada,
fecha de elección y vigencia geográfica; rechaza `legacy_snapshot` y `legacy_reported`.
El nombre de este modo no implica certificación externa de un documento ni revisión humana
automática: las comprobaciones son sobre metadatos y aritmética.

`mode=exploratory` permite leer expresamente las cargas heredadas conservadas. No modifica
sus etiquetas ni sus datos. Se pueden consultar lista nominal reportada, nulos y proxies
cuando tienen insumos suficientes. Las cuotas partidistas, ganadores, márgenes y HHI no
se deducen de columnas de atribución desconocida. La respuesta y la pantalla muestran una
advertencia de acreditación pendiente.

Los 1.070 originales pendientes de normalización no se incorporan al motor. Las 3.899
observaciones de conciliación de cargas anteriores tampoco se corrigen para producir
indicadores. Las reglas se evalúan sobre cada valor; no se promueve un lote a oficial.

Un lote sustituido por una revisión se rechaza por defecto. `allow_superseded=true` permite
reproducir explícitamente esa versión histórica, conservando su advertencia.

## Comparaciones

El periodo A debe preceder a B y las jornadas deben ser conocidas. Se exige el mismo cargo,
ámbito, principio, tipo de proceso, entidad, versión geográfica, nivel, base y denominador.
Se bloquean procesos/principios desconocidos y comparaciones de cargas heredadas sin
acreditación, incluso en modo exploratorio.

La igualdad de códigos entre versiones geográficas diferentes no acredita continuidad:
el motor exige el mismo `geography_id`. Una correspondencia entre demarcaciones necesita
preparación y evidencia antes de una futura ampliación; no se inventa automáticamente.

`coverage_mode=exact` exige las mismas unidades. `intersection` acepta explícitamente solo
las comunes e informa cuántas quedan fuera en A y B. Los agregados comparativos se
calculan sobre esa misma intersección, no sobre coberturas distintas.

Para opciones se exige una equivalencia uno a uno con `option_a`, `option_b`, `evidence_url`
HTTPS y `note` no vacía. No se homologa por nombres parecidos. IP03/IP04 requieren la
equivalencia del partido seleccionado; volatilidad y cambio de ganador requieren una
equivalencia exhaustiva de todas las opciones de cada unidad. No se reparten coaliciones,
se asumen miembros o se asignan ceros a opciones desaparecidas. La URL no se descarga ni
certifica automáticamente; el responsable debe revisar la equivalencia.

Una comparación incompatible devuelve HTTP 200 con `comparability.comparable=false`,
motivos y métricas `blocked`; no devuelve cifras comparativas engañosas.

## API y Postman

Todas las rutas requieren Bearer de administrador, con contraseña definitiva:

| Método | Ruta |
| --- | --- |
| GET | `/api/v1/indicators/catalog` |
| GET | `/api/v1/indicators/datasets` |
| GET | `/api/v1/indicators/datasets/{import_id}/options` |
| POST | `/api/v1/indicators/evaluate` |
| POST | `/api/v1/indicators/compare` |

Las dos peticiones POST son de cálculo, **sin escrituras**. `datasets` acepta `election_id`,
`after` y `limit` (máximo 100). No elige un lote automáticamente por nombre o año.

Ejemplo de evaluación exploratoria de un ID existente:

```json
{
  "import_id": 1,
  "mode": "exploratory",
  "option_code": null,
  "denominator": "valid_votes",
  "participation_proxy": false,
  "entity_code": null,
  "unit_code": null,
  "after": "",
  "limit": 100,
  "allow_superseded": false
}
```

`after` y `next_after` paginan unidades por clave; máximo 500. No cambian el resumen.
La comparación recibe `a` y `b` con ese mismo esquema, `coverage_mode` y `option_mapping`.
El cursor/límite de B controlan la página comparativa. Los de A se conservan como parte
de la petición reproducible pero no limitan su universo de cálculo.

Cada respuesta contiene versión del motor y catálogo, petición, fuente, fechas, huellas
del CSV y datos, cobertura, fórmulas identificadas por código y métricas con
`value/status/numerator/denominator/reason/details`. La evaluación incluye una huella del
cálculo. Los estados son `computed`, `proxy`, `unavailable`, `blocked` y `series`.
Repetir los mismos datos, parámetros y versión produce los mismos resultados.

HTTP 401/403: sesión/acceso; 404: ID ausente; 409: lote heredado sin reconocimiento,
revisión sustituida o fechas no acreditadas; 422: petición o equivalencias inválidas;
503: PostgreSQL/configuración. Los motivos de una métrica no disponible no son errores 500.

Importar [Go2Win-indicators.postman_collection.json](postman/Go2Win-indicators.postman_collection.json).
Completar usuario/contraseña en la colección, hacer login, listar lotes y seleccionar un ID.
Para las cargas migradas actuales elegir `mode=exploratory`; no basta con que su fila esté
normalizada. Consultar `/docs` para los contratos completos.

## Pantalla y pruebas

Reiniciar FastAPI y Streamlit y abrir **Motor de indicadores**, dentro del bloque de diagnóstico.
La pantalla consulta exclusivamente la API, muestra resumen, tabla, gráfica, catálogo y
proveniencia, y distingue los bloqueos. No muestra cálculos antiguos como si correspondieran
a una nueva selección que falló. No modifica el visor electoral anterior.

```powershell
$env:API_TEST_POSTGRES = '1'
try {
    .\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p 'test_indicators*.py' -v
} finally {
    Remove-Item Env:API_TEST_POSTGRES -ErrorAction SilentlyContinue
}
```

Las pruebas incluyen ejemplos matemáticos sintéticos, denominadores cero, faltantes,
ponderación, empates, HHI, volatilidad, cronología, homologación, filtros, paginación,
reproducibilidad, permisos, versiones y renderizado de la pantalla. Las integraciones
PostgreSQL usan tablas/esquemas temporales y reversión; no insertan cifras de prueba en la BD real.

## Límites

No hay estimación de preferencias individuales, probabilidad de victoria, homologación
automática de coaliciones/cartografía ni acreditación automática de fuentes. Los cruces
INEGI requieren correspondencias verificadas; la Fase 2 no resuelve los pendientes de la
migración ni altera la información anterior. Los resultados se reproducen por versión del
código y parámetros; no se crea una tabla de ejecuciones analíticas persistentes en esta fase.
