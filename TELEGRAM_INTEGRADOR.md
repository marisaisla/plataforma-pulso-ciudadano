# Vincular personal con Telegram

Los roles, equipos y territorios ya se configuran desde **Personal y Telegram**. Consulta [Roles y permisos](ROLES_Y_PERMISOS.md). El comando `/mi_perfil` muestra el acceso del usuario vinculado; reinicia el integrador después de actualizar su código.

Esta etapa registra trabajadores reales en la base de Go2Win y vincula una cuenta de Telegram con cada trabajador. El piloto utiliza un solo bot para esta base. Conecta las actividades asignadas, su recepción y los reportes de texto o con fotografía y revisión. Las incidencias siguen pendientes.

## Evidencias fotográficas

1. Envía `/reportar` y selecciona una tarea cuya recepción ya confirmaste.
2. Adjunta una sola **foto** en Telegram y escribe el avance en la descripción de esa foto. No la envíes como archivo ni como álbum. También puedes continuar enviando reportes de texto.
3. Espera la confirmación con folio. Cada reporte admite una fotografía JPEG de hasta 10 MB y 25 millones de píxeles. Para otra foto, inicia otro reporte.
4. Revisa la imagen desde **Reportes de campo** o **Mi espacio Go2Win → Reportes**, según tu rol y alcance.

La imagen se descarga usando [getFile de Telegram](https://core.telegram.org/bots/api#getfile), se verifica y se guarda en `field_report_photos` dentro de la misma transacción del reporte. Se conserva en la base compartida, sin depender de archivos de una computadora ni guardar URLs con el token. Los respaldos de la base incluyen las fotos y crecerán con ellas. Si falla la descarga, el integrador reintenta y conserva la captura; si la imagen es inválida, solicita otra. El mismo mensaje no crea dos reportes.

**PostgreSQL:** antes de reiniciar la aplicación y el integrador, el administrador de la base debe ejecutar `scripts/agregar_evidencias_postgresql.sql` sobre la base compartida. Esta actualización crea una tabla sin cambiar reportes anteriores. En SQLite la tabla se crea al inicializar el servicio. No se ha aplicado automáticamente a ninguna base PostgreSQL desde esta actualización.

## Necesidades territoriales

El personal de campo envía `/necesidad`, elige una campaña autorizada y envía:

```text
Estado: Sonora
Municipio: Hermosillo
Sección: 123
Origen: comentada
Necesidad: Falta alumbrado en dos calles.
```

Todos los campos son obligatorios. Origen admite `detectada` o `comentada`.
La descripción admite hasta 3000 caracteres y puede ocupar varias líneas al final.
No se solicitan datos personales de quien comentó la necesidad. No requiere una
tarea ni recepción previa. Estado y municipio deben coincidir con el alcance
autorizado del trabajador. La sección admite un número positivo de hasta seis
dígitos; esta etapa comprueba formato, no pertenencia al catálogo electoral.
La captura vence en 30 minutos y `/cancelar` la descarta. Iniciar otro flujo de
captura sustituye el anterior; consultar `/perfil` lo conserva.

El bot confirma con `N-000001`. La tabla `field_needs` conserva campaña, autor,
estado, municipio, sección, descripción, origen, fecha UTC y mensaje de origen.
`field_need_sessions` conserva capturas pendientes. Reintentos del mismo mensaje
devuelven el mismo folio sin duplicar; necesidades distintas del mismo territorio
pueden coexistir. No se cambia el estado de las tareas ni se envían notificaciones.

Coordinadores y directores consultan **Mi espacio Go2Win → Necesidades**, filtrado
por campaña y territorio autorizado, sin exigir pertenencia al equipo del autor.
Campo consulta sus propias capturas. Administradores consultan **Personal y
Telegram → Necesidades territoriales**. Incluye filtros de campaña, estado,
municipio, sección y búsqueda de descripción.

PostgreSQL requiere `scripts/agregar_necesidades_postgresql.sql` o el ejecutor
`scripts/aplicar_actualizacion_telegram.py`, que aplica todas las actualizaciones
Telegram en una transacción. Reiniciar los servicios después de aplicar.

## Consultar perfil y registrar incidencias

`/perfil` y `/mi_perfil` muestran el mismo rol, equipo, alcance y permisos, incluso
durante una captura pendiente. Consultarlos no cancela ni guarda esa captura.
Un comando desconocido se identifica expresamente y muestra los comandos disponibles.

Para registrar un problema, envía `/incidencia`, selecciona una tarea asignada
cuya recepción ya confirmaste y describe el problema, con foto opcional. Se
guarda en `field_reports` con la marca `[INCIDENCIA]` y folio `R-...`; las fotos
se conservan en `field_report_photos`. Go2Win muestra **Incidencia** en el título
del reporte y permite revisar el registro con el flujo existente. Aceptar ese
registro valida la información; no significa que el problema esté resuelto.
El trabajador lo consulta con `/mis_reportes`. La captura dura 30 minutos,
comprueba `incidents.submit` y respeta `/cancelar`, reintentos y alcance.
Comenzar `/incidencia` sustituye capturas anteriores de reporte o simpatizante.
No requiere otra migración PostgreSQL.

La opción `/evidencia` del menú antiguo orienta al flujo `/reportar`; no abre
una captura separada. Reinicia el integrador después de actualizar el código.

## Registrar un simpatizante

Envía `/simpatizante`, elige la campaña y envía los campos en un solo mensaje siguiendo el formato del bot. También puedes elegir directamente con `/simpatizante FOLIO_CAMPAÑA`. La captura dura 30 minutos y `/cancelar` la descarta. Comenzar `/reportar` sustituye la captura de simpatizante y viceversa.

Campos: nombre, teléfono, estado, municipio, sección electoral opcional, clave de elector obligatoria, autorización para registrar sus datos y autorización separada para recibir información. Estado y municipio deben coincidir con el alcance territorial autorizado del trabajador. La clave se normaliza a mayúsculas y se comprueba que tenga 18 caracteres alfanuméricos, conforme al [formato descrito por el INE](https://pautas.ine.mx/transparencia/caap/glosario.html); no se verifica identidad ni vigencia ante el INE.

`Registro: SI` declara que la persona autorizó guardar sus datos como simpatizante en esa campaña. `Mensajes: SI` o `Mensajes: NO` conserva por separado su decisión sobre recibir información. Se registra quién capturó los datos y cuándo; esto es una declaración del trabajador, no una confirmación enviada por el simpatizante. No se envían mensajes en esta versión. El teléfono y la clave de elector no pueden repetirse dentro de la misma campaña; un registro existente no se sobrescribe. Si Telegram reentrega el mensaje, el bot devuelve el mismo folio `S-000001` sin duplicarlo ni repetir los datos personales en la respuesta.

El catálogo se encuentra en **Personal y Telegram → Catálogo de simpatizantes** para administradores y en **Mi espacio Go2Win → Simpatizantes** para los demás roles. Campo consulta sus propios registros; supervisores y coordinadores consultan su equipo y alcance; directores consultan su campaña autorizada. El catálogo permite buscar y filtrar por autorización para recibir información. Una cuenta de Telegram del trabajador y un teléfono del simpatizante son datos distintos: el teléfono por sí solo no permite enviarle mensajes mediante el bot; el futuro canal de envío y vinculación debe implementarse aparte.

**PostgreSQL:** aplica también `scripts/agregar_simpatizantes_postgresql.sql` como administrador de la base antes de reiniciar. Crea las tablas `supporters` y `supporter_sessions` y sus permisos. En SQLite la inicialización crea el catálogo automáticamente. Prueba local: `py -m unittest discover -s tests -p "test_supporters.py"`.

## Enviar y revisar un reporte de texto

1. Reinicia Go2Win y el integrador después de actualizar el código.
2. Desde Telegram, envía `/reportar`. Selecciona una tarea asignada cuya recepción ya confirmaste. El bot valida tu usuario activo, rol, alcance, asignación actual y que la tarea esté pendiente o en curso.
3. Envía el avance en un solo mensaje de texto, de hasta 4000 caracteres. La captura vence a los 30 minutos; `/cancelar` la descarta sin crear un reporte.
4. El bot confirma el guardado con un folio como `R-000001` y estado **Por validar**. El folio identifica al reporte, no a la tarea. Guardar un reporte no cambia la actividad a concluida.
5. En Go2Win abre **Planes de acción**, selecciona la actividad y consulta **Reportes de campo**. Usa el botón de actualizar o recarga para ver los recién recibidos.
6. Elige **Aceptar reporte** o **Solicitar corrección** y pulsa **Guardar revisión**. La corrección requiere observaciones; máximo 500 caracteres. La revisión registrada no se sobrescribe.
7. El trabajador envía `/mis_reportes` para ver el estado y las observaciones. Para corregir, envía un nuevo reporte con `/reportar`; el original y su revisión permanecen en el historial. No se envían avisos automáticos en esta etapa.

La captura pendiente se guarda en la base y sobrevive a un reinicio dentro de su vigencia. El bot guarda antes de responder. Si falla la respuesta y Telegram reentrega el mismo mensaje, devuelve el mismo folio sin duplicar el reporte. Si cambia el responsable, se retira el alcance, se desactiva el usuario o se cierra la actividad, la captura se rechaza al guardar. Se aceptan fotos con descripción; documentos y otros archivos no se aceptan.

Streamlit requiere inicio de sesión y la revisión registra al usuario autenticado, aplicando `reports.review`, territorio y equipo. Los administradores revisan desde Planes de acción; supervisores y coordinadores usan su panel operativo. No se habilita aún revisión por Telegram. No se permite que un revisor valide su propio reporte. Los registros históricos con `local_console` se conservan.

Tablas añadidas: `field_reports` guarda el texto, folio numérico, autor, tarea, fecha y estado; `field_report_reviews` conserva la decisión y las observaciones; `field_report_sessions` conserva capturas pendientes; `field_report_selections` evita reactivar una captura por reentrega del mismo botón.

## Consultar y recibir una tarea

1. Reinicia Go2Win y el integrador para cargar esta versión. Go2Win: `.\.venv\Scripts\python.exe -m streamlit run app.py`. Integrador, en otra terminal con el token: `.\.venv\Scripts\python.exe scripts/integrador_telegram.py`.
2. En **Personal y Telegram**, verifica el rol, la vinculación y el alcance del trabajador para la campaña y territorio de la tarea.
3. En **Planes de acción**, selecciona perfil, estado, estrategia y la actividad en **Actualizar una actividad**.
4. En **Asignación a Telegram**, selecciona el trabajador registrado y pulsa **Guardar asignación de Telegram**. El campo libre **Responsable** conserva el dato anterior; por sí solo no vincula cuentas.
5. Desde el chat privado del trabajador, envía `/mis_tareas`. Verás actividades pendientes o en curso asignadas a esa persona, con paginación. `/tarea FOLIO` muestra la descripción completa, por páginas si es extensa.
6. Pulsa **Confirmar recepción**. El bot guarda la fecha antes de responder. Confirmar dos veces no duplica el registro.
7. En Go2Win pulsa **Actualizar actividades y recepciones**. La tabla y la sección de asignación mostrarán la recepción en UTC. Esta confirmación no cambia la actividad a concluida.

La asignación no envía avisos automáticos todavía: el trabajador consulta `/mis_tareas`. Las tareas canceladas o concluidas no aparecen. Cambiar el responsable o retirar la asignación invalida sus botones anteriores y deja historial. Reasignar al mismo trabajador sin cambios conserva su recepción. Si se retiran permisos o territorio, se bloquean nuevas consultas y confirmaciones; el historial guardado se conserva.

Las tablas nuevas son `field_task_assignments` (responsable registrado y recepción actual) y `field_task_events` (historial de asignaciones y recepciones). Referencian los folios existentes de `territorial_action_plans`; no copian tareas ni asignan por coincidencia de nombres.

## Activar al primer trabajador

1. Abre Go2Win como de costumbre. Si estaba abierto, recarga la página.
2. En **Configuración y apoyo → Personal y Telegram**, registra nombre y, opcionalmente, equipo.
3. Selecciona al trabajador y pulsa **Generar código de activación**. Copia el comando mostrado; vence en 30 minutos, se utiliza una vez y un código nuevo invalida el anterior.
4. Detén `prueba_bot_telegram.py` con `Ctrl+C`. No ejecutes ambos programas ni otro receptor del mismo bot simultáneamente.
5. En PowerShell, desde el proyecto y con el token configurado, ejecuta:

```powershell
Set-Location 'D:\PROYECTOS\plataforma-pulso-ciudadano'
py .\scripts\integrador_telegram.py
```

También puedes usar `.\.venv\Scripts\python.exe .\scripts\integrador_telegram.py`.

6. Entrega el comando `/start CODIGO` solo al trabajador correspondiente. Esa persona debe enviarlo desde su propia cuenta al chat privado del bot.
7. Telegram debe responder **Acceso activado en Go2Win**. En la plataforma, pulsa **Actualizar estado de vinculación** y verifica que aparezca **Vinculado**.

## Token

El integrador busca `TELEGRAM_BOT_TOKEN` primero en el entorno y después en el `.env` privado del proyecto. Para configurarlo en la sesión actual sin mostrarlo:

```powershell
$tokenSeguro = Read-Host 'Pega el token de BotFather' -AsSecureString
$env:TELEGRAM_BOT_TOKEN = [System.Net.NetworkCredential]::new('', $tokenSeguro).Password
Remove-Variable tokenSeguro
```

No hace falta cambiar el menú de BotFather. Si existe un webhook, el programa termina sin modificarlo.

## Administración y alcance

- La pantalla general de personal requiere una sesión de administrador; los demás roles tienen un panel operativo filtrado. Consulta [Inicio de sesión](INICIO_DE_SESION.md).
- **Desactivar acceso** bloquea al trabajador y revoca sus códigos pendientes. **Reactivar acceso** conserva el vínculo existente.
- **Desvincular Telegram** retira la asociación y revoca los códigos; después puedes generar otro para vincular una nueva cuenta.
- El código autoriza la vinculación: entrégalo por un canal privado después de verificar al trabajador. En la base solo se conserva su hash, no el código original.
- Los nombres y equipos son datos de registro; todavía no otorgan permisos territoriales ni asignan actividades por coincidencia de nombre.
- El programa no imprime mensajes ni códigos. Guarda vínculos, recepciones y reportes antes de responder y reintenta si falla Telegram. Puede repetir una respuesta si Telegram la recibió pero se perdió la confirmación de red; los reportes se deduplican por chat y mensaje.
- Procesa mensajes pendientes entregados por Telegram, incluso después de reiniciar; la validez del código y de las capturas se verifica al procesarlos. Los reportes y las capturas son persistentes; todavía no hay una cola propia de notificaciones ni supervisión para producción.
- Los datos se almacenan en `data/pulso_ciudadano_local.db`. Las tablas nuevas no modifican las actividades existentes. La prueba anterior sigue disponible por separado.

## Comprobación local sin Telegram

```powershell
py -m unittest discover -s tests -p "test_field*.py" -v
```

Estas pruebas utilizan una base temporal. La comprobación desde el celular se realiza con los pasos anteriores.

Referencia del transporte: [Telegram Bot API](https://core.telegram.org/bots/api#getupdates).
