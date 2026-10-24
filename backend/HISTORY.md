# Fase 1 — Base histórica electoral

Implementación del modelo **Go2Win Modelo Integral de Inteligencia Electoral**, versión 1.0,
octubre de 2026. Esta fase organiza entidades, municipios, distritos federales y locales,
secciones, elecciones y resultados con procedencia y versiones. No calcula los 45 indicadores
ni convierte resultados agregados en preferencias individuales.

## Qué está implementado

- Esquema PostgreSQL separado `electoral_history`; no modifica las cargas operativas anteriores.
- Catálogos geográficos inmutables con fecha de vigencia, fuente y relaciones de sección.
- Elecciones identificadas por proceso, jornada, ámbito, cargo, principio y entidad aplicable.
- Resultados por unidad y opción, con totales separados para evitar repetir lista nominal por partido.
- Importación CSV normalizada, validación previa sin escritura y guardado atómico.
- Fuente declarada, enlace, publicación, consulta, corte, versión, metodología, usuario y hash del CSV.
- Reimportación exacta idempotente y revisiones explícitas sin sobrescribir originales.
- API, contrato OpenAPI, colección Postman y pantalla **Base histórica electoral**.

La instalación crea la estructura vacía. **No incluye un acervo nacional cargado ni certifica
automáticamente una publicación como oficial**. El administrador debe obtener y revisar los
archivos de cada autoridad y normalizarlos según las reglas siguientes. Las cargas existentes
en otras tablas no se migran ni se declaran verificadas de forma automática.

La versión 0.16.0 incorpora una [migración explícita de cargas anteriores](LEGACY_MIGRATION.md)
con archivo íntegro y conciliación. Los datos copiados se identifican como `legacy_snapshot`
y `legacy_reported`; no se consideran hechos oficiales acreditados ni se incluyen en
`fact_votes`. En esos registros, las fechas desconocidas quedan en null y el proceso/principio
en `unknown`. La interfaz permite consultar los originales y los pendientes de normalización.

## Instalación y acceso

Con PostgreSQL y `.env` configurados, desde la raíz:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m backend.migrate_history
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

La migración [agregar_base_historica_postgresql.sql](../scripts/agregar_base_historica_postgresql.sql)
es aditiva y repetible; requiere permisos para crear esquema/tablas/vista en la BD elegida.
No se ejecuta al iniciar FastAPI y no contiene `DROP` ni cambios a tablas heredadas.
El rol que ejecuta la API debe tener acceso al esquema creado; usar el rol configurado del
proyecto o asignarle permisos mediante la administración de PostgreSQL.

Iniciar Streamlit como se indica en el README general. Entrar con una cuenta normal de
**administrador**, contraseña definitiva, y abrir **Base histórica electoral** en el menú
del bloque de visores. Todas las consultas y escrituras de esta pantalla pasan por HTTP.
Esta primera versión restringe también la lectura a administradores; no hereda los alcances
de perfiles ni permite acceso con claves provisionales o sesiones de desarrollo.

## Fuentes de partida

- [Resultados electorales del INE](https://www.ine.mx/voto-y-elecciones/resultados-electorales/).
- [SICEE](https://sicee.ine.mx/): consultar disponibilidad, año, cargo y desagregación de cada base.
- [Cómputos distritales del INE](https://portal.ine.mx/voto-y-elecciones/computos-distritales/).
- [SIGE del INE](https://cartografia.ine.mx/sige8/): marco geográfico y productos cartográficos.
- OPLE de la entidad correspondiente para elecciones locales y publicaciones modificadas por sentencia.

Usar el enlace específico de la publicación o archivo en la ficha de fuente, no únicamente
la portada institucional. Distinguir cómputos de PREP: este módulo admite cómputos oficiales
y revisiones por sentencia, no resultados preliminares. Registrar la denominación de la
autoridad y la etapa según el documento efectivamente revisado; seleccionar una etiqueta
en el formulario no equivale a una verificación externa.

Conservar los originales en `storage_path('data/...')`, dentro de `GO2WIN_FILES_ROOT`,
y describir su ubicación, versión y transformación en `source.methodology`. No guardar
insumos compartidos en el repositorio ni usar copias locales silenciosas si falla MARISA.
El módulo conserva en BD el **CSV normalizado recibido**; su hash SHA-256 corresponde a
ese texto UTF-8, no al XLSX/ZIP original ni a una descarga verificada de la URL.

## Flujo de carga

1. Obtener la geografía que corresponda al proceso, no asumir que la distritación actual
   describe una elección anterior. Documentar fecha y fuente de esa correspondencia.
2. Registrar el catálogo con las entidades, municipios y distritos referenciados por sus secciones.
3. Registrar la elección. Separar cargos, MR/RP, ordinaria/extraordinaria y ámbito.
4. Transformar el archivo oficial a CSV UTF-8 y documentar filtros, agregaciones y columnas.
5. Seleccionar nivel y base de votos; validar sin guardar. Resolver errores y revisar advertencias.
6. Guardar el mismo archivo y metadatos validados. Consultar lote, cifras y procedencia.
7. Si cambia una publicación, cargar una revisión con `supersedes_id`; el lote original permanece.

Cada archivo admite hasta 20.000 filas y 5 millones de caracteres; la pantalla limita también
el tamaño del archivo a 5 MB. Para geografía nacional, preparar catálogos por entidad con
nombres de versión explícitos. Para resultados mayores, dividir en lotes de cobertura
documentada sin partir las opciones de una misma unidad entre archivos.

## Catálogo geográfico

Encabezados exactos, en este orden, separados por comas:

```csv
level,code,name,entity_code,municipality_code,federal_district_code,local_district_code
```

| Nivel (`level`) | Clave compuesta | Ejemplo de formato |
| --- | --- | --- |
| `entity` | EE | `26` |
| `municipality` | EE + MMM | `26001` |
| `federal_district` | EE + DD | `2601` |
| `local_district` | EE + DD | `2602` |
| `section` | EE + SSSS | `260001` |

Los ejemplos ilustran formatos, no certifican relaciones geográficas. Las claves de entidad
van de 01 a 32. Mantener los ceros iniciales como texto; las claves municipales son las del
catálogo electoral utilizado, sin asumir equivalencia automática con INEGI.

Toda unidad requiere `name` y `entity_code`. Solo las secciones declaran
`municipality_code`, `federal_district_code` y `local_district_code`: el municipio es obligatorio;
los distritos pueden quedar vacíos cuando no se conoce una relación respaldada por fuente.
Incluir en el mismo archivo la entidad padre y todas las unidades referenciadas.
Un municipio puede abarcar varios distritos: no se modela como hijo de un distrito.

Una versión no se modifica: repetir exactamente contenido, fecha y fuente devuelve su ID;
un contenido distinto con la misma versión devuelve 409. Para otra demarcación o corrección,
crear una versión nueva. No hay correspondencia automática entre secciones de versiones
distintas ni geometrías/polígonos cargados en esta fase.

## Resultados

Encabezados exactos:

```csv
unit_code,nominal_list,total_votes,null_votes,unregistered_votes,option_code,option_name,votes
```

Grano de entrada: **una fila por unidad y opción de votación**.

- `unit_code`: clave completa del catálogo y nivel seleccionados.
- `nominal_list`, `total_votes`, `null_votes`, `unregistered_votes`: totales de esa unidad,
  repetidos sin variación en todas sus opciones.
- `option_code`, `option_name`: código estable dentro del lote y nombre publicado de la opción.
- `votes`: votación atribuida a esa opción, usando una sola base de atribución.

Las bases son `party` (partido con atribución oficial), `candidacy` (candidatura/coalición
consolidada) y `ballot_combination` (combinación de marcas de boleta). **No sumar entre esas
bases** ni cargar votos de coalición además de sus componentes en el mismo lote.
No se redistribuyen coaliciones ni se homologan partidos entre procesos automáticamente.

Los nulos y no registrados van en sus columnas, no como opciones adicionales.
Vacío se conserva como `null`; `0` significa cero explícito. Solo se aceptan enteros no
negativos sin separadores. Con componentes completos se exige:

```text
suma(votos de opciones) + votos nulos + no registrados = total de votos
```

Con faltantes, los componentes conocidos no pueden superar el total y se emite advertencia;
no se imputa el resto. Si los votos superan lista nominal se advierte, sin corregirlos ni
inventar un denominador: documentar casillas especiales y cobertura. No se calcula participación
ni ganador en esta fase.

La API comprueba existencia de unidad, nivel, versión y entidad de la elección; no verifica
que el CSV contenga todas las opciones publicadas ni consulta la URL remota. La metodología y
la revisión humana deben respaldar la integridad, agregación y atribución del archivo oficial.

## Versiones y cobertura

Un lote registra exactamente una elección, geografía, nivel, base, fuente y cobertura.
La huella del paquete completo evita duplicar una petición idéntica. Si cambian el CSV o
los metadatos se trata de otra carga; incluso los saltos de línea afectan el hash del CSV.

`supersedes_id` crea una revisión explícita que conserva elección, versión geográfica,
nivel, base y conjunto de unidades. Se impiden dos sucesores distintos del mismo lote.
El historial muestra `superseded_by`; las versiones previas siguen consultables.
Una nueva cobertura o geografía requiere un lote independiente, no sobrescribe lo anterior.

La consulta selecciona un lote explícito. **No sumar cargas superpuestas, distintos niveles
ni versiones**; tampoco tomar como cobertura nacional un lote parcial. No hay todavía un
consolidador que combine lotes de entidades o elija automáticamente la versión vigente.

## API y Postman

Prefijo `/api/v1/history`; todas las rutas requieren `Authorization: Bearer <access_token>`
de administrador. El token se obtiene en `/api/v1/auth/login`.

| Método | Ruta relativa | Uso |
| --- | --- | --- |
| GET | `/geographies` | Versiones y fuentes geográficas |
| POST | `/geographies` | Validar y guardar catálogo |
| GET | `/geographies/{geography_id}` | Fuente y CSV conservado del catálogo |
| GET | `/geographies/{geography_id}/units` | Unidades; filtros `level`, `entity_code`, `municipality_code`, cursor `after` |
| GET | `/elections` | Catálogo de elecciones |
| POST | `/elections` | Registrar elección sin sobrescribir un código existente |
| POST | `/imports/preview` | Validación completa sin escritura |
| POST | `/imports` | Validar otra vez y guardar atómicamente |
| GET | `/imports` | Historial; filtros `election_id`, `after`, `limit` |
| GET | `/imports/{import_id}` | Metadata y CSV original de la carga normalizada |
| GET | `/imports/{import_id}/results` | Totales y opciones; filtros `entity_code`, `unit_code`, cursor `after` |

Unidades/resultados devuelven `items` y `next_after`, con máximo 500 unidades por página.
El historial admite máximo 100 lotes por página; continuar con el último ID.
HTTP 401: sesión inválida; 403: acceso; 404: ID inexistente; 409: versión/conflicto;
422: entrada/geografía/conciliación; 503: PostgreSQL/configuración/esquema pendiente.
Una repetición idempotente de POST devuelve 201 con el ID previo y `duplicate=true`.

Importar [Go2Win-history.postman_collection.json](postman/Go2Win-history.postman_collection.json).
Completar sus variables sin exportar credenciales. Primero login, catálogo, elección,
preview y guardado; después consultar el lote. Las peticiones de escritura guardan datos
en la BD configurada. Los cuerpos deben usar fuentes efectivamente revisadas.

La fuente requiere `authority`, `url`, `title`, `published_on`, `retrieved_on`, `cutoff_on`,
`version`, `stage` y `methodology`. `csv_content` contiene el CSV como texto JSON escapado;
la colección prepara ese escape desde sus variables. Swagger contiene los esquemas completos.

## Modelo físico y pruebas

Tablas: `geographies`, `units`, `elections`, `imports`, `results`, `votes`, dentro de
`electoral_history`. `results` guarda los totales una sola vez por unidad; `votes` tiene
las observaciones por opción. La vista `fact_votes` expone dimensiones de elección,
geografía, base y opción para el futuro motor analítico. No incluye denominadores repetidos
ni agrega entre lotes. No hay endpoints para borrar o sobrescribir historia.

Pruebas de validación sin conexión y pruebas HTTP con PostgreSQL aislado:

```powershell
$env:API_TEST_POSTGRES = '1'
try {
    .\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p test_history.py -v
} finally {
    Remove-Item Env:API_TEST_POSTGRES -ErrorAction SilentlyContinue
}
```

Las pruebas crean un esquema de nombre único dentro de una transacción y revierten todo;
usan fixtures identificados como sintéticos, no cifras oficiales. Cubren permisos,
jerarquías, ceros/faltantes, conciliación, preview, idempotencia, versiones y revisiones.

## Siguientes fases

La adquisición y normalización de cada acervo oficial requiere trabajo por fuente y proceso;
no hay un descargador nacional ni un adaptador universal para los distintos XLSX/ZIP del INE
y OPLE. La [Fase 2 del motor de indicadores](INDICATORS.md) implementa fórmulas y controles
sobre estos lotes, sin acreditar cargas anteriores ni resolver las claves pendientes.
La homologación temporal/cartografía, catálogos maestros de actores/coaliciones, encuestas
y generación de productos quedan para sus siguientes etapas.
