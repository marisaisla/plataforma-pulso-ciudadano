# Dashboard de las 45 variables

API 0.19.0. Pantalla **Dashboard de indicadores**, dentro del bloque de diagnóstico.
Requiere iniciar sesión con usuario administrador; se conserva el mismo control Bearer
del motor. La pantalla Streamlit consulta FastAPI por HTTP y no accede a PostgreSQL.
No hay migración nueva, escrituras de negocio ni modelo OLAP.

## Uso

1. Ejecutar FastAPI y Streamlit como indica el README. Si ya estaban ejecutándose,
   recargar los procesos para cargar las rutas y la pantalla nuevas.
2. Abrir **Dashboard de indicadores**. Las 45 tarjetas aparecen sin inventar valores.
3. En **Filtros electorales**, seleccionar un lote y opcionalmente una clave de unidad.
   Consultar datos electorales. La cobertura corresponde únicamente a ese lote/nivel.
4. IT01 muestra lista nominal reportada e IT05 porcentaje de nulos, cuando los insumos
   lo permiten. IT03/IT04 solo se muestran tras activar explícitamente la aproximación
   con votos emitidos. No es conteo censal de personas que votaron.
5. En **Filtros INEGI**, elegir entidad, componente IT10–IT13, serie, periodo, fuente y
   opcionalmente municipio. Consultar INEGI. Los valores individuales aparecen en la tabla
   y, cuando tienen una misma unidad conocida, en una gráfica de la página actual.
6. Las tarjetas INEGI indican el número de observaciones de la consulta, claramente
   diferenciado de un valor agregado del indicador. No se suman ni promedian porcentajes.
7. En **Encuestas y expediente**, seleccionar un perfil y pulsar **Consultar encuestas y
   expediente**. Elegir una medición para las tarjetas IC05 (preferencia reportada) e IC07
   (indecisión reportada), cuando sus metadatos y clasificación lo permiten. Aprobación de
   gestión, referencias excluidas o registros sin clasificación no alimentan esas tarjetas.
8. Debajo de las tarjetas aparecen las mediciones del perfil, cargos, documentos, evidencias
   y escenarios existentes. Las referencias temáticas también se muestran en las tarjetas
   relacionadas: IC01, IC02, IC04, IC05, IC07–IC12 e IP06, si el perfil tiene registros.

Ejemplo comprobado: **Eliseo Fernández Montúfar (#10)**, medición **#38 · CE Research ·
careo 1 gubernatura · agosto 2026**. IC05 muestra **38,5 %** e IC07 **9,7 %**, ambos como
porcentajes reportados del mismo reactivo, no pronóstico ni comprobación independiente.
Sus metadatos tienen que seguir coincidiendo con la revisión para alimentar las tarjetas.

Los filtros electorales e INEGI son independientes. Una elección no cambia automáticamente
el corte de población. Cambiar filtros oculta resultados anteriores hasta consultar de nuevo.
Los lotes sustituidos no se calculan aquí; seleccionar su revisión vigente en el motor.
Los datos electorales son exploratorios y conservan advertencias, huellas, cobertura y fuentes.
La tabla electoral muestra hasta 100 unidades y el resumen usa toda la selección; puede
filtrarse una unidad concreta. INEGI ofrece cursor para páginas posteriores.

## Contrato HTTP

Todas las rutas requieren `Authorization: Bearer <access_token>` de administrador.

| Método y ruta | Respuesta |
|---|---|
| GET `/api/v1/indicators/dashboard/cards` | `reviewed_on`, `note`, 45 `items` con código, nombre, familia, unidad, fórmula, disponibilidad, evidencia, presentación admisible, faltantes y soporte del motor. |
| GET `/api/v1/indicators/dashboard/inegi/options` | Entidades, series homologadas, periodos y fuentes disponibles; municipios vacíos hasta seleccionar entidad. |
| GET `/api/v1/indicators/dashboard/inegi/options?state=Chihuahua` | Opciones disponibles para esa entidad. |
| GET `/api/v1/indicators/dashboard/inegi` | Observaciones municipales individuales y su fuente, unidad, periodo, fecha de recuperación, estado y cursor. |
| GET `/api/v1/indicators/dashboard/research?profile_id=10` | Perfil, mediciones clasificadas, cargos, documentos, evidencias con relaciones temáticas, escenarios, totales y advertencias. |

`/research` requiere `profile_id` entero positivo. Perfil inexistente: 404; entrada inválida:
422; sin sesión válida: 401; rol no autorizado: 403. El administrador puede consultar perfiles
inactivos, visibles en la pantalla al activar esa opción. Las consultas se filtran por perfil;
no se mezclan expedientes. Se devuelven hasta 500 registros por categoría con totales y bandera
`truncated` si se supera el límite. No se ofrecen descargas de archivos ni rutas físicas aquí.

Cada encuesta conserva nombre, encuestadora, territorio, fecha, muestra, metodología, resultado
original, enlace y notas. Añade `kind`, `classification_status`, `fingerprint`,
`metadata_missing`, `review_note` e `indicators.IC05/IC07` con valor, estado, motivo y campo de
origen. `reported` significa transcrito de la fuente registrada, no validado externamente.

La clasificación revisada en `dashboard_survey_review.json` corresponde al contenido exacto
de los 37 registros revisados el 22 de octubre. Su huella incluye perfil, nombre, fuente,
notas y metadatos. Un registro nuevo o modificado queda `unreviewed_or_changed`, conserva
su información original en la tabla y no genera valores de tarjeta hasta revisar su tipo.
No se usan palabras clave como clasificador automático. Una migración de identificadores
de perfil puede exigir nueva revisión de las huellas. La revisión no se guarda en tablas
nuevas ni modifica la encuesta original.

Para mostrar porcentajes en tarjetas se requiere tipo de preferencia revisado, ausencia de
exclusión, valor finito 0–100 y metadatos mínimos (encuestadora, territorio, fecha, muestra
positiva, metodología y fuente). Campos no vacíos no prueban por sí solos validez estadística.
IC07 se extrae de categorías de indecisión explícitamente revisadas; no suma «ninguno» o
«no sabe». Los reactivos 34 y 38 pertenecen al mismo levantamiento y no se cuentan como
estudios independientes. Las puntuaciones de `viability_electoral_scores` no se consultan.

Parámetros de `/inegi`:

- Obligatorios: `state`, `period`, `source`, `family` (IT10, IT11, IT12 o IT13).
- Opcionales: `municipality_code`, `indicator_id`, `after` (ID, mínimo 0), `limit` (1–500, por defecto 100).
- Respuesta: `total` (coincidencias de filtros, sin cursor), `items`, `next_after`, `scope`.
- Una combinación sin datos devuelve `total: 0`, `items: []`; nunca rellena con ceros.
- Un valor nulo o no finito se entrega como `value: null`, `value_status: missing_or_nonfinite`.
  Cero válido conserva `value: 0`, `value_status: reported`.
- La correspondencia de series a IT10–IT13 es explícita en `indicator_dashboard.INEGI`.
  Solo aparecen las series actualmente mapeadas; datos territoriales ajenos a esos componentes
  permanecen en sus visores. El mapa no certifica la metodología de origen.
- Los filtros usan parámetros SQL. Las consultas son SELECT y no modifican las tablas originales.

El dashboard reutiliza GET `/indicators/datasets` y POST `/indicators/evaluate` para los
cuatro indicadores exploratorios, con las reglas del [motor](INDICATORS.md).
La [colección Postman del dashboard](postman/Go2Win-dashboard.postman_collection.json)
incluye las consultas de prueba del dashboard y de encuestas/expedientes. Completar `access_token` con el token del login;
elegir entidad, serie, periodo y fuente a partir de las respuestas de opciones.
Las 45 fichas proceden del catálogo y `indicator_availability.json`, corte 2026-10-22.
El estado de inventario es una revisión versionada, no un conteo dinámico de datos ni una
certificación. Su [matriz de referencia](AVAILABILITY_MATRIX.md) distingue 4 exploratorias,
17 parciales, 12 bloqueadas y 12 pendientes. No se migró el catálogo a tablas PostgreSQL.

## Límites de presentación

IT10 muestra componentes de población, no un cruce completo edad×sexo. IT11 puede mostrar
escolaridad promedio sin afirmar que sea una distribución educativa. IT12 no construye un
índice de pobreza a partir de empleo; IT13 distingue conteos y porcentajes de servicios.
Cuando no hay unidad documentada se conserva el valor en tabla y se omite la gráfica.
No se extrapolan valores municipales a secciones ni se suman elecciones, fuentes o versiones.
Las variables documentales muestran referencias, cargos declarados y metadatos de documentos,
sin convertir puntuaciones de viabilidad ni apreciaciones del expediente en porcentajes.
IC06 no calcula evolución automáticamente: una secuencia de registros no garantiza igual
pregunta, universo, método o escenario. IC03 no infiere opinión desfavorable de rechazo o
aprobación. IC04 no resta valores de estudios distintos. Riesgo reputacional no acredita
antecedentes jurídicos; nominación probable no equivale a candidatura registrada.

No se corrigieron los 1.070 registros electorales pendientes, ni se reconstruyeron perfiles,
expedientes o encuestas. Las otras tarjetas conservan su disponibilidad y requisitos; las
referencias temáticas no las convierten automáticamente en mediciones verificadas.

## Validación

Pruebas `test_indicator_dashboard.py` y `test_indicator_dashboard_ui.py`: 45 fichas,
filtros de fuente/periodo/territorio/familia, paginación, cero frente a ausentes/no finitos,
autenticación, proxy opcional y ocultamiento de resultados de filtros anteriores.
Las pruebas PostgreSQL usan una tabla temporal sin tocar datos ni secuencias públicas.
`test_dashboard_research.py` y `test_dashboard_research_ui.py` verifican aislamiento por
perfil, procedencia, aprobación frente a preferencia, exclusiones, cambios de huella,
faltantes, ceros, selección de medición y ocultamiento de datos del perfil anterior.
