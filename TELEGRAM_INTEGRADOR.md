# Vincular personal con Telegram

Los roles, equipos y territorios ya se configuran desde **Personal y Telegram**. Consulta [Roles y permisos](ROLES_Y_PERMISOS.md). El comando `/mi_perfil` muestra el acceso del usuario vinculado; reinicia el integrador después de actualizar su código.

Esta etapa registra trabajadores reales en la base local de Go2Win y vincula una cuenta de Telegram con cada trabajador. El piloto utiliza un solo bot para esta base. Ya conecta las actividades asignadas, su recepción y los reportes de texto con revisión. Fotografías e incidencias siguen pendientes.

## Enviar y revisar un reporte de texto

1. Reinicia Go2Win y el integrador después de actualizar el código.
2. Desde Telegram, envía `/reportar`. Selecciona una tarea asignada cuya recepción ya confirmaste. El bot valida tu usuario activo, rol, alcance, asignación actual y que la tarea esté pendiente o en curso.
3. Envía el avance en un solo mensaje de texto, de hasta 4000 caracteres. La captura vence a los 30 minutos; `/cancelar` la descarta sin crear un reporte.
4. El bot confirma el guardado con un folio como `R-000001` y estado **Por validar**. El folio identifica al reporte, no a la tarea. Guardar un reporte no cambia la actividad a concluida.
5. En Go2Win abre **Planes de acción**, selecciona la actividad y consulta **Reportes de campo**. Usa el botón de actualizar o recarga para ver los recién recibidos.
6. Elige **Aceptar reporte** o **Solicitar corrección** y pulsa **Guardar revisión**. La corrección requiere observaciones; máximo 500 caracteres. La revisión registrada no se sobrescribe.
7. El trabajador envía `/mis_reportes` para ver el estado y las observaciones. Para corregir, envía un nuevo reporte con `/reportar`; el original y su revisión permanecen en el historial. No se envían avisos automáticos en esta etapa.

La captura pendiente se guarda en la base y sobrevive a un reinicio dentro de su vigencia. El bot guarda antes de responder. Si falla la respuesta y Telegram reentrega el mismo mensaje, devuelve el mismo folio sin duplicar el reporte. Si cambia el responsable, se retira el alcance, se desactiva el usuario o se cierra la actividad, la captura se rechaza al guardar. No se aceptan archivos en esta etapa.

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
