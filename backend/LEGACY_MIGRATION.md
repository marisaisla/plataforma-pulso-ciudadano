# Migración de cargas electorales anteriores

La migración copia las cargas existentes al esquema `electoral_history`, conservando los
originales. No cambia las consultas de los visores ni las tablas de perfiles, cartografía,
territorios o indicadores INEGI. No requiere recapturar resultados.

## Inventario y alcance

En la revisión del 21 de octubre de 2026 se encontraron 37.981 registros en PostgreSQL:

| Tabla de origen | Filas |
| --- | ---: |
| `public.territorial_election_results` | 1.175 |
| `public.territorial_district_results` | 351 |
| `public.territorial_section_results` | 36.455 |

Incluyen Campeche, Chihuahua, Estado de México, Guerrero, Nayarit, Querétaro, Sonora y
Yucatán, con elecciones de 2021 y 2024. La vista previa pudo normalizar 36.911 filas y
dejó 1.070 pendientes por claves ausentes/incompatibles o unidades repetidas. Esas cifras
son un inventario del estado encontrado, no una certificación de cobertura oficial.

Las tablas electorales anteriores ya son comunes por estado, año y tipo de elección;
los perfiles las consultan, pero no son propietarios de cada resultado. Se conserva esa
mecánica en los visores durante la transición.

La primera ejecución quedó confirmada como **run 1**: 37.981 originales archivados,
36.911 registros normalizados, 1.070 pendientes conservados, 82 lotes históricos y
759.949 filas de votación. La conciliación fue exacta y las huellas de perfiles,
territorios e indicadores INEGI permanecieron iguales. La acreditación de las fuentes
y la resolución de las observaciones siguen pendientes.

## Conservación y calidad

- Cada fila original completa se conserva en `legacy_records.original_row`, incluyendo el
  texto exacto del `payload`, notas adicionales, fuente e `imported_at`.
- Se guarda una relación entre tabla/ID original, hash, ejecución, lote nuevo y unidad.
- Los conteos enteros se trasladan sin redondear; los faltantes siguen siendo `null`.
- Si una clave no puede determinarse inequívocamente, la fila queda pendiente y se conserva íntegra.
- Las secciones repetidas no se suman ni se sobrescriben automáticamente.
- Las columnas de votos conservan sus nombres originales. No se redistribuyen coaliciones
  ni se eliminan columnas derivadas para forzar una conciliación.
- La revisión detectó 3.899 filas cuyos componentes no concilian con el total; sus números
  se conservan con observación. Normalizado significa copiado al modelo, no validado oficialmente.

La procedencia se marca como `legacy_snapshot`, y la base de votos como `legacy_reported`.
Estas cargas **no participan en `electoral_history.fact_votes`**, la vista destinada a
hechos oficiales con atribución documentada. Se pueden consultar explícitamente en la
pantalla y API sin confundirlas con una carga oficial nueva.

No se inventan fecha de publicación, corte, jornada electoral, vigencia cartográfica,
principio o proceso ordinario/extraordinario. Se conserva el año conocido y el resto queda
pendiente o `unknown`. La fecha de consulta del snapshot es la de la migración, no una
afirmación sobre cuándo se descargó originalmente el documento oficial.

Si un importador antiguo convirtió faltantes en ceros o sobrescribió una versión previa,
esta copia no puede recuperar esa información que ya no está en las tablas. Conserva el
estado disponible; recuperar versiones anteriores requiere revisar originales o respaldos.

## Vista previa

Desde la raíz, con las mismas variables PostgreSQL que usan los visores:

```powershell
.\.venv\Scripts\python.exe -m backend.migrate_legacy_history
```

Esta operación es de solo lectura. Informa cantidades, observaciones y huella del origen;
no crea catálogos ni inserta resultados. Se exige `DB_BACKEND=postgresql` para no migrar
un origen distinto al utilizado por las pantallas.

## Ejecución

El comando siguiente requiere un ID real de administrador activo, usado para auditoría.
La aplicación no toma una identidad al azar ni exige poner su contraseña en un script:

```powershell
.\.venv\Scripts\python.exe -m backend.migrate_legacy_history --apply --actor-id ID_ADMIN
```

El programa:

1. Aplica la extensión aditiva del esquema histórico.
2. Lee una fotografía consistente de los datos en transacción `REPEATABLE READ`.
3. Guarda un respaldo comprimido en `storage_path('data/history_migration/...')` y verifica
   su SHA-256 tras volver a leerlo. Si MARISA falla o falta configuración, se detiene sin
   usar un respaldo local como alternativa.
4. Archiva el 100% de las filas, normaliza las compatibles y conserva las demás pendientes.
5. Concilia cada total y cada opción contra el origen, incluyendo valores nulos; comprueba
   todos los originales archivados y las huellas de perfiles, territorios e INEGI.
6. Confirma la transacción solo si todas esas comprobaciones pasan. Un error revierte los
   registros de la migración, sin borrar el respaldo verificado.
7. Publica el informe JSON en `storage_path('output/history_migration/...')` después del commit.
   También conserva el informe dentro de `legacy_runs.report`.

La misma fotografía produce una sola ejecución: repetir el comando no duplica registros.
Una fotografía posterior diferente se conserva como otra ejecución; no se suman sus lotes
ni se decide automáticamente qué fila cambió de versión. Las cargas no quedan sincronizadas
continuamente con nuevas escrituras de los visores heredados.

## Consulta y trazabilidad

Abrir **Base histórica electoral → Cargas anteriores y conciliación**. Allí se muestran
el informe, pendientes, observaciones y cada fila original completa. Los registros
normalizados también aparecen en **Consulta y fuentes**, con una advertencia visible de
acreditación pendiente.

Rutas administrativas bajo `/api/v1/history`:

| Método | Ruta | Uso |
| --- | --- | --- |
| GET | `/legacy/runs` | Ejecuciones, informe y respaldo; `after` y `limit` |
| GET | `/legacy/runs/{run_id}` | Informe de una ejecución |
| GET | `/legacy/runs/{run_id}/records` | Filtrar `status=pending/normalized`, `state`, cursor `after` y `limit` |
| GET | `/legacy/runs/{run_id}/records/{source_table}/{source_id}` | Original completo y su correspondencia |

`next_after` permite continuar la lista sin omitir IDs. Las consultas requieren una sesión
Bearer de administrador. No existen endpoints para sobrescribir o borrar estos originales.

## Pruebas

```powershell
$env:API_TEST_POSTGRES = '1'
try {
    .\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p test_legacy_history.py -v
} finally {
    Remove-Item Env:API_TEST_POSTGRES -ErrorAction SilentlyContinue
}
```

Las pruebas usan tablas y esquemas temporales dentro de transacciones revertidas. Cubren
conservación de notas y textos, conteos, duplicados, faltantes, conciliación exacta,
idempotencia, reversión completa, API y exclusión de datos no acreditados de los hechos oficiales.

## Después de la copia

Resolver los pendientes contra publicaciones y cartografía históricas documentadas.
Después, crear cargas oficiales nuevas con fechas y atribución acreditadas, y conservar
la relación con la fila heredada revisada. Cambiar los visores a leer la base nueva será
un paso separado que requiere comparar sus salidas; esta migración no hace ese cambio.
