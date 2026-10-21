# Go2Win API — backend

Guía del estado actual **0.14.0**. FastAPI concentra el acceso a PostgreSQL y las reglas de
permisos de las funciones migradas: perfiles y elección, administración de usuarios,
operación de Telegram, Planes de acción y el portal del trabajador.
El frontend actual sigue siendo Streamlit; React queda como una siguiente etapa.

## Arquitectura y alcance

```text
Pantallas Streamlit → clientes HTTP en services/ → FastAPI → PostgreSQL
Telegram → backend.telegram_polling → FastAPI → PostgreSQL
                                  ← respuesta ←
```

Las pantallas migradas consultan y guardan mediante HTTP. Los clientes no recurren a SQL
como alternativa si la API falla ni reintentan automáticamente sus escrituras.
El backend utiliza la misma base PostgreSQL existente y no crea ni migra su esquema al arrancar.

| Pantalla o función | Integración actual |
| --- | --- |
| 01 Perfil y elección | `services/profile_screen.py` y `services/profiles_api.py` |
| Administración de usuarios | `services/field_staff_ui.py` y `services/field_api.py` |
| Operación de Telegram | `services/telegram_operations_ui.py`: vinculación, simpatizantes y necesidades |
| Planes de acción | `services/action_plans_ui.py`: actividades, asignaciones, reportes, fotos y revisión |
| Mi espacio Go2Win | `services/web_portal.py` y `/api/v1/field/portal` |
| Cuestionarios de campo | `services/field_surveys_ui.py`, cliente HTTP `services/field_surveys.py` y `backend/surveys.py` |

Los componentes de tareas, reportes, simpatizantes y necesidades de estas pantallas también
usan los clientes HTTP. La migración no abarca todo el sistema: el inicio de sesión general
de Streamlit, parte de su inicialización y otros módulos aún conservan acceso heredado a la BD.
Las sesiones web normales existentes son reconocidas por la API; las sesiones de desarrollo no.

## Configuración

Ejecutar los comandos desde la raíz del repositorio. Usar el archivo **`.env` de la raíz**,
no un archivo dentro de `backend/`. Las variables de PowerShell tienen prioridad sobre `.env`,
incluso si contienen un valor vacío.

| Variable | Uso |
| --- | --- |
| `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` | Conexión PostgreSQL; todas requeridas |
| `API_BASE_URL` | Dirección que usan pantallas y receptor; predeterminada `http://127.0.0.1:8000` |
| `GO2WIN_PUBLIC_URL` | Dirección HTTPS de la pantalla web, leída por FastAPI para el botón de cuestionarios; vacía deshabilita el botón |
| `API_ADMIN_KEY` | Clave provisional para diagnóstico de BD y generación inicial de códigos |
| `TELEGRAM_WEBHOOK_SECRET` | Secreto compartido entre receptor y API |
| `TELEGRAM_BOT_TOKEN` | Token de BotFather para recibir, responder y descargar fotos |

El backend usa PostgreSQL independientemente de `DB_BACKEND`, que pertenece a módulos heredados.
`TELEGRAM_WEBHOOK_SECRET` conserva ese nombre aunque el receptor actual trabaja por polling.
Las dos claves de API y el token del bot son credenciales distintas. Guardarlas con valores
estables en `.env`; no generarlas cada vez que se inicia el servidor ni incluirlas en Git o colecciones exportadas.

Si anteriormente se definieron claves temporales en esa terminal, quitar esas variables
antes de iniciar el proceso para que se lean los valores de `.env`:

```powershell
Remove-Item Env:API_ADMIN_KEY -ErrorAction SilentlyContinue
Remove-Item Env:TELEGRAM_WEBHOOK_SECRET -ErrorAction SilentlyContinue
```

## Arranque local

Instalar las dependencias del backend:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
```

Iniciar la API y mantener abierta su terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Para probar el bot real, abrir otra terminal:

```powershell
.\.venv\Scripts\python.exe -m backend.telegram_polling
```

Para usar las pantallas, en otra terminal y con las dependencias generales del proyecto instaladas:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Postman y las pantallas no requieren que el receptor de Telegram esté corriendo.
`--reload` recarga FastAPI; reiniciar el receptor y Streamlit cuando cambie código que importan.
Estas direcciones son locales. Para otro servidor, configurar una dirección accesible y
`API_BASE_URL`; el despliegue requiere configurar HTTPS y la gestión de secretos.

## Contrato y documentación

- Swagger del servidor: <http://127.0.0.1:8000/docs>.
- Contrato servido por la aplicación: <http://127.0.0.1:8000/openapi.json>.
- Contrato versionable del repositorio: [openapi.json](openapi.json).
- Exportador: [export_openapi.py](export_openapi.py).

Después de cambiar rutas o modelos, actualizar el contrato guardado:

```powershell
.\.venv\Scripts\python.exe -m backend.export_openapi
```

La documentación en ejecución refleja el código cargado en ese proceso. Si no aparece un
cambio, comprobar el servidor y su reinicio, además de recargar el navegador.
Los esquemas de Swagger son la referencia para los campos y tipos completos.

## Autenticación

| Credencial | Encabezado | Funciones |
| --- | --- | --- |
| Sesión de usuario | `Authorization: Bearer <access_token>` | Administración, perfiles y operación web |
| Secreto de integración | `X-Telegram-Bot-Api-Secret-Token: <secreto>` | Eventos y consultas del receptor Telegram |
| Clave provisional | `X-API-Key: <clave>` | Salud de BD y código inicial de vinculación |

Los identificadores de trabajador, perfil o Telegram no sustituyen estas credenciales.
La clave provisional no reemplaza el login de administración y debe retirarse de ese uso
provisional al preparar producción.

### Sesión Bearer

1. Enviar `POST /api/v1/auth/login` con el usuario y contraseña de una cuenta web existente.
2. Guardar `access_token` y usarlo en Authorization → Bearer Token en Postman.
3. Consultar `GET /api/v1/auth/me` para comprobar identidad y permisos.

Ejemplo del cuerpo de login:

```json
{"username": "usuario_de_prueba", "password": "su_contraseña"}
```

La respuesta incluye `access_token`, `token_type`, `expires_at` (Unix UTC) y
`must_change_password`. El token es opaco, dura ocho horas y se almacena como hash en BD.
Si debe cambiarse la contraseña temporal, usar `POST /api/v1/auth/password`:

```json
{"old_password": "su_contraseña_actual", "new_password": "una_contraseña_nueva"}
```

La nueva contraseña debe tener de 12 a 128 caracteres. El cambio cierra todas las sesiones:
volver a iniciar sesión y sustituir el token. Mientras exista cambio obligatorio, solo están
habilitadas las operaciones de sesión correspondientes. Cinco intentos fallidos en quince
minutos bloquean el login durante cinco minutos.

Los endpoints administrativos requieren administrador activo y contraseña definitiva.
Los permisos y el alcance territorial se verifican en el servidor. Cambiar accesos o territorios,
restablecer cuentas o desactivar usuarios puede revocar sus sesiones. Se protege al último
administrador activo con cuenta web frente a desactivación o pérdida de ese rol.

## Inventario de APIs

Todas las rutas siguientes incluyen el prefijo `/api/v1`. `Bearer` identifica una sesión
normal; las restricciones adicionales de rol, permiso, asignación y territorio siguen aplicando.

### Diagnóstico e integración Telegram

| Método | Ruta | Credencial / resultado |
| --- | --- | --- |
| GET | `/health` | Pública; disponibilidad del proceso |
| GET | `/health/database` | X-API-Key; conexión y columnas básicas de vinculación |
| POST | `/workers/{worker_id}/telegram/activation-codes` | X-API-Key; código inicial, 201 |
| POST | `/integrations/telegram/updates` | Secreto Telegram; procesa mensaje o callback |
| GET | `/integrations/telegram/users/{telegram_user_id}/tasks` | Secreto Telegram; tareas propias abiertas |
| GET | `/integrations/telegram/users/{telegram_user_id}/tasks/{task_id}` | Secreto Telegram; detalle autorizado |

La consulta de tareas acepta `after` (predeterminado 0) y `limit` (predeterminado 3, máximo 50);
responde con `items` y `next_after`. El código de activación dura treinta minutos, es de un
solo uso y se guarda como hash. La respuesta de generación incluye el comando `/start`.

### Sesiones y administración de usuarios

| Método | Ruta | Función |
| --- | --- | --- |
| POST | `/auth/login` | Crear sesión con usuario y contraseña |
| GET | `/auth/me` | Consultar mi sesión, Bearer |
| POST | `/auth/logout` | Cerrar sesión, 204 |
| POST | `/auth/password` | Cambiar contraseña y cerrar sesiones, 204 |
| GET | `/users` | Listar usuarios: `after=0`, `limit=50`, máximo 100 |
| POST | `/users` | Crear trabajador con `name` y `team` opcional, 201 |
| GET | `/users/{wid}` | Consultar trabajador |
| PATCH | `/users/{wid}` | Cambiar nombre |
| PUT | `/users/{wid}/access` | Cambiar `role_key`, `team`, `supervisor_id`, 204 |
| PUT | `/users/{wid}/active` | Activar o desactivar con `active` booleano, 204 |
| GET | `/users/{wid}/scopes` | Consultar territorios |
| POST | `/users/{wid}/scopes` | Agregar alcance territorial, 204 |
| DELETE | `/users/{wid}/scopes` | Retirar alcance mediante cuerpo JSON, 204 |
| PUT | `/users/{wid}/account` | Crear o restablecer cuenta: `username`, `temporary_password`, 204 |
| DELETE | `/users/{wid}/telegram` | Desvincular Telegram, 204 |
| POST | `/users/{wid}/telegram/activation-codes` | Generar código con sesión administrativa, 201 |
| GET | `/roles` | Consultar roles y permisos disponibles |

Salvo las operaciones de sesión, estas rutas requieren administrador.
Los alcances utilizan `profile_id`, `state` y `municipality`; consultar el esquema para valores
vacíos y opcionales. Supervisor y equipo deben ser compatibles y no pueden formar ciclos.
Desactivar conserva trabajador, vínculo e historial, pero revoca sesiones, códigos y capturas.
Desvincular elimina la asociación Telegram y sus capturas/códigos sin borrar el trabajador.
Las acciones de administración de accesos registran al actor en `field_access_audit`.

### Perfiles y elección

Todas estas rutas requieren administrador con Bearer.

| Método | Ruta | Función |
| --- | --- | --- |
| GET | `/profiles/options` | Tipos de perfil y condiciones disponibles |
| GET | `/profiles` | Consultar candidatos/perfiles; `active_only=false` predeterminado |
| POST | `/profiles` | Guardar perfil, 201 |
| PUT | `/profiles/{profile_id}/active` | Activar o desactivar con `active` booleano |
| GET | `/profile-positions` | Consultar cargos; filtro opcional `profile_id` |
| POST | `/profiles/{profile_id}/positions` | Guardar cargo o candidatura, 201 |

La ruta se llama **`/profiles`**, ya no `/campaigns`. La prueba de Postman se llama
**Consultar candidatos**, aunque el catálogo admite Persona, Partido político,
Institución pública y Tema sin actor.

Crear un perfil requiere `name` y `actor_type`; admite `notes`. Guardar un cargo requiere
`office`, `condition` y `starts_at`; admite `ends_at` y `party_or_coalition`.
La fecha final no puede preceder a la inicial. Desactivar es una baja lógica:
conserva historial, aparece con `active=0` en el listado completo y deja de estar disponible
para nuevas selecciones activas y nuevos cargos. No hay borrado físico de perfiles por API.

### Planes de acción y operación

| Método | Ruta | Función y acceso |
| --- | --- | --- |
| GET | `/territory-options` | Administrador; estados y municipios, filtro `state` |
| GET | `/profiles/{pid}/states` | Administrador; estados del perfil |
| GET | `/action-strategies` | Administrador; requiere `profile_id` y `state` |
| GET | `/activities` | Administrador; requiere `strategy_id` |
| POST | `/activities` | Administrador; crear actividad, 201 |
| PATCH | `/activities/{tid}` | Administrador; actualizar estado y nota de evidencia |
| GET | `/activities/{tid}/assignment` | Bearer y `tasks.view`; asignación actual o null |
| GET | `/activities/{tid}/candidates` | Bearer; responsables elegibles según permisos y alcance |
| PUT | `/activities/{tid}/assignment` | Bearer y `tasks.assign`; asignar o retirar, 204 |
| GET | `/activities/{tid}/reports` | Bearer y `reports.view`; avances e incidencias autorizados |
| GET | `/reports/{rid}/photo` | Bearer y `reports.view`; JPEG, 204 si no existe foto |
| PUT | `/reports/{rid}/review` | Bearer y `reports.review`; aceptar o pedir corrección, 204 |
| GET | `/supporters` | Bearer; simpatizantes dentro del alcance autorizado |
| GET | `/needs` | Bearer; necesidades dentro del alcance autorizado |
| GET | `/field/portal` | Bearer; tareas y reportes autorizados del portal |

Para crear una actividad enviar `strategy_id`, `activity_name` y `due_date`;
`priority_level` admite Alta, Media o Baja (predeterminada Media). Son opcionales
`activity_description`, `responsible`, `district` y `electoral_section`. El backend obtiene perfil
y territorio de la estrategia; no confía esos datos al cliente.

Actualizar una actividad utiliza `status`: Pendiente, En curso, Concluida o Cancelada,
y `evidence_note` opcional. Asignar utiliza `{"worker_id": 4}`; retirar, `{"worker_id": null}`.
El responsable debe estar activo, tener permiso para confirmar y estar dentro del alcance.
Las tareas cerradas no admiten nueva asignación. Repetir el mismo responsable conserva
la recepción; reasignar genera una nueva generación e invalida los botones anteriores.

Revisar un reporte utiliza `decision` (`accepted` o `correction`) y `note` de hasta 500
caracteres; una corrección requiere explicación. No se permite revisar un reporte propio.
Las revisiones son inmutables: repetir la misma decisión y nota es idempotente; intentar
cambiarlas devuelve 409. La revisión no cambia automáticamente el estado de la actividad.
Las fotos requieren autorización y responden con `Cache-Control: no-store`.

## Bot real de Telegram

### Cuestionarios por API

Estas rutas usan el prefijo `/api/v1` y la sesión Bearer normal. Las sesiones de
desarrollo sin contraseña no son válidas. `tasks.assign` permite configurar y
asignar dentro del alcance del usuario. La captura requiere `reports.submit` y ser
el responsable actual de la actividad; la consulta aplica `tasks.view` y filtra
respuestas por `reports.view`, usando el territorio registrado en cada envío.

| Método | Ruta | Función |
| --- | --- | --- |
| GET | `/activities/{tid}/questionnaires` | Actividad, cuestionario vigente, plantillas autorizadas y permisos de pantalla |
| POST | `/activities/{tid}/questionnaires` | Crear borrador o publicar con `publish=true`, 201 |
| PUT | `/activities/{tid}/questionnaires/{qid}` | Editar o publicar un borrador de la actividad |
| PUT | `/activities/{tid}/questionnaire` | Asignar `questionnaire_id` y `target`, 204 |
| GET | `/activities/{tid}/questionnaire/capture` | Obtener formulario; requiere parámetros `assignment` y `survey` |
| POST | `/activities/{tid}/questionnaire/responses` | Guardar respuestas y devolver folio; repetir el mismo envío devuelve el mismo resultado |
| GET | `/activities/{tid}/questionnaire/results` | Respuestas e indicadores por versión, dentro del alcance autorizado |

Una definición contiene `title`, `description`, `mode` (`single` o `multiple`),
`publish` y entre 1 y 30 `questions`. Cada pregunta define `label`, `type` (`text`,
`number` o `choice`), `required`, `options`, límites opcionales `min`/`max`, `metric`
(`none`, `count`, `sum`, `average`) y `metric_label`. Suma y promedio requieren número.
El backend asigna identificadores `q1`, `q2`, etc.; las versiones publicadas no se editan.

El envío incluye `assignment_generation`, `survey_generation`, `submission_key`
(16 a 128 caracteres, conservar la misma clave al reintentar el mismo envío) y
`answers`, un objeto indexado por los identificadores de pregunta. Nunca acepta
`worker_id` como identidad. Reasignación, cambio de versión, cierre de actividad y
revocación de permisos se verifican nuevamente al guardar. Un envío inválido no
guarda respuestas parciales. Se usan las mismas tablas de la primera versión local:
`field_questionnaires`, `field_task_surveys` y `field_survey_responses`.

Los indicadores se calculan en el backend por actividad y versión: conteo de envíos,
avance respecto a meta, conteo de respuestas no vacías y sumas/promedios numéricos.
Se conservan las respuestas anteriores. Una nueva versión genera otro grupo de
resultados. La captura se contabiliza al enviar y no cierra la actividad.

`backend.tasks` incorpora el botón en `/mis_tareas` y `/tarea FOLIO`, dentro de la
respuesta de `/integrations/telegram/updates`. El receptor existente lo envía a
Telegram; no requiere acceso directo a PostgreSQL ni un segundo bot. El enlace
apunta a la pantalla Streamlit y no contiene tokens de sesión ni secretos del bot.

Antes de actualizar los procesos, aplicar `scripts/agregar_cuestionarios_postgresql.sql`
en la base usada por la API. Para `go2win_desarrollo` se incluye en
`python scripts/aplicar_actualizacion_telegram.py`; es aditiva y repetible. Si la
primera versión local ya creó las tablas, se conservan registros y folios. No hay
migración automática al iniciar FastAPI. Reiniciar API, Streamlit y receptor tras
actualizar. No ejecutar también `scripts/integrador_telegram.py` con el mismo bot.

Swagger y `backend/openapi.json` documentan los cuerpos completos. Una API inaccesible
produce error visible en las pantallas, sin recurrir a SQL. La dirección pública
HTTPS sigue siendo necesaria para abrir el formulario fuera de la red local.

### Receptor y comandos

`backend.telegram_polling` recibe eventos y los envía a `/integrations/telegram/updates`;
la API valida, consulta o guarda y devuelve `reply` y, cuando corresponde, `reply_markup`.
El receptor envía esa respuesta al chat. Un POST simulado desde Postman procesa el evento,
pero por sí solo no manda un mensaje a Telegram.

Solo se admiten conversaciones privadas con identidad de remitente y chat coherentes.
El trabajador debe estar vinculado y activo; se respetan permisos y alcance territorial.
Incluso un administrador consulta sus propias tareas mediante `/mis_tareas`.

| Comando | Comportamiento |
| --- | --- |
| `/start CODIGO` | Vincular cuenta con un código vigente de un solo uso |
| `/perfil`, `/mi_perfil` | Consultar identidad y acceso del trabajador |
| `/ayuda` | Ayuda según permisos, estado de captura y comandos habilitados |
| `/mis_tareas` | Listar tareas propias abiertas, paginadas |
| `/tarea FOLIO` | Consultar detalle y confirmar recepción con botón |
| `/reportar` | Elegir tarea y registrar avance de texto o foto con descripción |
| `/incidencia` | Elegir tarea y registrar una incidencia |
| `/mis_reportes` | Consultar reportes propios y su revisión |
| `/simpatizante` | Elegir perfil autorizado y capturar simpatizante |
| `/necesidad` | Elegir perfil autorizado y capturar necesidad territorial |
| `/evidencia` | Orientación para usar `/reportar` |
| `/cancelar` | Cancelar la captura pendiente |

Los botones de recepción y selección de tareas validan trabajador, permiso y generación
de asignación. Confirmar repetidamente la misma recepción no crea eventos adicionales.
Las capturas duran treinta minutos y se guardan en BD. Iniciar otro flujo de captura
sustituye el anterior; consultar ayuda, perfil, tareas o historial no amplía su vigencia.

### Avances, imágenes e incidencias

Después de seleccionar una tarea recibida, enviar texto de hasta 4.000 caracteres o una
foto JPEG con el avance en la descripción **del mismo mensaje**. La foto admite hasta 10 MB
y 25 millones de píxeles; el flujo admite una foto por reporte, no documentos, video ni álbumes.
El backend descarga y valida la imagen con el token del bot y guarda reporte y foto de
forma atómica. No guarda URLs con el token. Si la imagen falla, se conserva la captura
para corregir el envío.

Los reportes generan folio R y quedan pendientes de revisión. Las incidencias se guardan
como reportes con el prefijo `[INCIDENCIA]` seguido de salto de línea y descripción;
no son una entidad separada con estado de resolución. Su descripción admite hasta 3.987
caracteres por el prefijo. Se consultan en los reportes autorizados de la tarea y en
`/mis_reportes`; una celda que muestra solo la primera línea puede ocultar la descripción.
El historial del bot muestra pendiente, aceptado o corrección y la nota correspondiente.
No se envía una notificación automática al registrar una revisión.

### Simpatizantes

Después de elegir un perfil, enviar un mensaje con este formato:

```text
Nombre: Persona de prueba
Teléfono: 5512345678
Estado: Sonora
Municipio: Hermosillo
Sección: 123
Clave de elector: ABCDEF123456789012
Registro: SI
Mensajes: NO
```

Nombre, teléfono, estado, municipio, clave de elector y consentimiento de registro son necesarios; la sección es opcional y se debe indicar `Mensajes: SI` o `Mensajes: NO`. La clave se valida por formato, no contra el INE.
`Registro: SI` autoriza el registro; el consentimiento de mensajes es independiente.
Registrar no envía mensajes a esa persona. No se sobrescribe un registro con teléfono o
clave de elector duplicados dentro del mismo perfil. Se genera folio S.

### Necesidades territoriales

Después de elegir un perfil, enviar:

```text
Estado: Sonora
Municipio: Hermosillo
Sección: 123
Origen: comentada
Necesidad: Falta alumbrado en dos calles.
```

Todos esos campos son necesarios. Origen admite `detectada` o `comentada`; sección debe
ser numérica positiva de hasta seis dígitos (validación de formato). La descripción va
al final, puede ocupar varias líneas y admite hasta 3.000 caracteres. Se genera folio N.
No requiere seleccionar ni confirmar una tarea. No capturar datos personales del informante.

### Receptor y límites actuales

El receptor comprueba el bot y rechaza arrancar si ya tiene webhook configurado.
No ejecutar simultáneamente otro polling con el mismo token. El antiguo
`scripts/integrador_telegram.py` sigue en el repositorio y tiene referencias de pruebas;
el receptor del flujo nuevo es **`backend.telegram_polling`**. Conservar ese archivo no
significa que deba ejecutarse junto al nuevo receptor ni que se haya completado su retirada.

El offset del receptor está en memoria y avanza después del procesamiento y envío de la
respuesta. Hay reintentos para errores transitorios, pero no hay outbox durable ni supervisor
de procesos integrado. Los registros usan deduplicación lógica cuando corresponde por
chat/mensaje; no existe una garantía global de procesamiento único para todo `update_id`.
Una interrupción puede repetir respuestas. Los rechazos de negocio pueden llegar con
HTTP 200 y `status`/`reply` explicativos: revisar también el cuerpo de la respuesta.

## Pruebas desde Postman

Importar las colecciones guardadas en el repositorio:

| Colección | Uso |
| --- | --- |
| [Go2Win.postman_collection.json](postman/Go2Win.postman_collection.json) | Vinculación y comandos/eventos Telegram |
| [Go2Win-users.postman_collection.json](postman/Go2Win-users.postman_collection.json) | Sesión, usuarios, territorios, perfiles y cargos |
| [Go2Win-operations.postman_collection.json](postman/Go2Win-operations.postman_collection.json) | Planes de acción y operación web |

Configurar las variables en la pestaña **Variables de cada colección**, no en Params.
Las colecciones tienen valores propios: un token guardado en una no se copia automáticamente
a las otras. Guardar los cambios con Save o Ctrl+S.

- Comunes: `base_url=http://127.0.0.1:8000`; `access_token` para las colecciones con login.
- Telegram: `admin_key`, `telegram_secret`, `worker_id`, `telegram_user_id` y `activation_code`.
  Para tareas/reportes: `task_id`, `task_generation`, identificadores de mensaje/callback y
  cuerpos de las capturas; para fotos, los identificadores reales del archivo Telegram.
- Usuarios: `user_id` y las variables de los cuerpos de cada prueba. `profile_id` corresponde
  al perfil/candidato. La colección incluye creación de perfil, cargo y desactivación.
- Operación: `profile_id`, `state`, `strategy_id`, `activity_id`, `assignment_worker_id`,
  `report_id` y los valores de revisión. `assignment_worker_id` debe ser un ID o `null` explícito.

`worker_id`/`user_id` son IDs internos del trabajador; `telegram_user_id` es el ID numérico
real de Telegram; `profile_id` es el perfil. Algunas variables del bot conservan el nombre
`campaign_id`, pero representan el perfil, no una API distinta de campañas.

Secuencia recomendada:

1. Probar Salud; comprobar PostgreSQL con la credencial provisional.
2. Ejecutar 01 Login de la colección de usuarios u operación. El script guarda `access_token`.
3. Consultar Mi sesión. Cambiar contraseña solo si corresponde y volver a hacer login.
4. Consultar catálogos y definir IDs reales antes de ejecutar escrituras de prueba.
5. Para el bot, generar un código de un trabajador activo no vinculado y usarlo una sola vez.
6. Asignar una tarea de prueba, confirmar recepción y probar avances, foto e incidencia.
7. Consultar/revisar el reporte desde la pantalla o colección de operación y verificar el historial.

Las escrituras de Postman modifican la BD configurada. No ejecutar toda la colección de
forma automática sobre usuarios o tareas reales. Para comprobar el bot real, usar Telegram
con el receptor nuevo activo; los IDs ficticios de un ejemplo solo sirven para simulaciones.

## Persistencia

| Información | Tablas principales |
| --- | --- |
| Trabajadores y sesiones | `field_workers`, `web_accounts`, `web_sessions`, `web_login_attempts` |
| Permisos y alcance | `field_roles`, `field_permissions`, `field_role_permissions`, `field_worker_scopes`, `field_access_audit` |
| Vinculación | `field_activation_codes` y columnas Telegram de `field_workers` |
| Perfiles y cargos | `profiles`, `profile_keywords`, `profile_positions` |
| Actividades y asignación | `territorial_strategies`, `territorial_action_plans`, `field_task_assignments`, `field_task_events` |
| Avances e incidencias | `field_reports`, `field_report_reviews`, `field_report_photos` y tablas de captura/selección |
| Simpatizantes y necesidades | `supporters`, `supporter_sessions`, `field_needs`, `field_need_sessions` |

Las fotos se guardan en PostgreSQL en base64; considerar su volumen en los respaldos.
Las capturas pendientes también persisten en la BD. Las fechas se manejan en UTC;
consultar los esquemas para distinguir campos Unix de campos de fecha/texto.

## Organización del backend

| Archivo | Responsabilidad |
| --- | --- |
| `main.py` | Aplicación FastAPI, diagnóstico y entrada de eventos Telegram |
| `config.py`, `database.py` | Configuración y conexión PostgreSQL |
| `admin.py`, `permissions.py` | Sesiones, administración, permisos y alcance |
| `profiles.py` | Perfiles, opciones y cargos |
| `operations.py` | Planes de acción, asignación, revisión y consultas de pantallas |
| `telegram.py`, `tasks.py` | Despacho del bot, vinculación, tareas y recepción |
| `reports.py`, `photos.py` | Capturas, avances, incidencias e imágenes |
| `supporters.py`, `needs.py`, `profile.py`, `help.py` | Flujos y consultas del bot |
| `telegram_polling.py` | Transporte entre Telegram y la API |
| `verify_database.py` | Comprobación básica de conexión/esquema de vinculación |
| `export_openapi.py`, `openapi.json` | Exportador y contrato guardado |
| `postman/`, `tests/` | Colecciones y pruebas automatizadas |

## Verificación y pruebas automatizadas

Diagnóstico de conexión y columnas básicas:

```powershell
.\.venv\Scripts\python.exe -m backend.verify_database
```

Esta comprobación cubre la conexión y las columnas necesarias de `field_workers` y
`field_activation_codes`; no valida el esquema completo de todos los módulos.

Pruebas del backend con PostgreSQL habilitado:

```powershell
$env:API_TEST_POSTGRES = '1'
try {
    .\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
} finally {
    Remove-Item Env:API_TEST_POSTGRES -ErrorAction SilentlyContinue
}
```

Sin esa variable se omiten las pruebas que requieren PostgreSQL. Las pruebas de integración
usan tablas/esquemas temporales y reversión; requieren conexión configurada y permisos para
crear sus estructuras temporales. Las pruebas de pantallas requieren también las dependencias
Streamlit del proyecto y comprueban HTTP sin permitir las conexiones SQL heredadas en esas vistas.
Los tests heredados de `tests/` son una suite aparte.

## Problemas frecuentes

| Resultado | Revisar |
| --- | --- |
| 401 en una ruta Bearer | Token ausente, vencido, revocado o usuario inactivo; volver a hacer login |
| 401 en diagnóstico o Telegram | Clave de Postman distinta de la cargada en el servidor; revisar variables de PowerShell |
| 403 | Rol, permiso, alcance, cambio de contraseña obligatorio o intento de revisar un reporte propio |
| 404 | Ruta o registro inexistente; usar `/profiles`, no la antigua `/campaigns` |
| 409 | Conflicto de asignación, tarea cerrada, revisión existente o protección del último administrador |
| 422 | Cuerpo/tipo inválido; `user_id` debe resolverse a entero y las contraseñas no pueden estar vacías |
| 429 en login | Bloqueo temporal por intentos fallidos |
| 503 | Configuración faltante, conexión/esquema de PostgreSQL o fallo interno de una operación |

Un 200 en `/health` solo confirma que el proceso responde. El mensaje genérico de 503
no identifica por sí solo la causa exacta; revisar configuración y diagnóstico del servidor.
Si falla una foto, comprobar descripción en el mismo mensaje, tipo/tamaño y token del bot.

Si no aparece un botón nuevo, comprobar que corre el código actual y reiniciar Streamlit.
Actualizar el navegador puede perder el token conservado en `session_state`; todavía no
hay persistencia de sesión del navegador que resuelva ese caso.

La migración completa de otros servicios, el frontend React, un despliegue webhook y la
supervisión durable del receptor siguen fuera de lo implementado aquí.
