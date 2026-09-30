# Prueba local de Telegram para Go2Win

El script `scripts/prueba_bot_telegram.py` permite probar el bot existente desde este proyecto. Usa únicamente la biblioteca estándar de Python y funciona como proceso independiente de Streamlit.

Esta es una demostración: muestra una tarea ficticia, recibe texto y reconoce fotografías. No consulta actividades reales, no descarga fotografías ni guarda reportes en la base de Go2Win. La conexión con la plataforma sigue pendiente.

## Ejecutar en PowerShell

Detén el script en la otra computadora si continúa funcionando: debe existir un solo receptor para el mismo bot. No necesitas crear otro bot ni repetir la configuración del menú.

Abre PowerShell y ejecuta:

```powershell
Set-Location 'D:\PROYECTOS\plataforma-pulso-ciudadano'

$tokenSeguro = Read-Host 'Pega el token de BotFather' -AsSecureString
$env:TELEGRAM_BOT_TOKEN = [System.Net.NetworkCredential]::new('', $tokenSeguro).Password
Remove-Variable tokenSeguro

py .\scripts\prueba_bot_telegram.py
```

Si utilizas el entorno virtual del proyecto, puedes sustituir la última línea por:

```powershell
.\.venv\Scripts\python.exe .\scripts\prueba_bot_telegram.py
```

El script lee `TELEGRAM_BOT_TOKEN` del entorno de esa ventana; no carga el archivo `.env`. El token no debe añadirse al código ni compartirse en el chat. Al cerrar PowerShell tendrás que configurarlo nuevamente.

Mantén el proceso activo y la computadora conectada a internet. No hace falta abrir Streamlit para esta prueba. Para detener el bot, pulsa `Ctrl+C`. Para quitar el token de la sesión después de detenerlo:

```powershell
Remove-Item Env:TELEGRAM_BOT_TOKEN
```

## Probar desde Telegram

Abre el chat privado del bot y envía mensajes nuevos después de arrancar el programa:

| Acción | Resultado esperado |
| --- | --- |
| `/start` o `/ayuda` | Muestra los comandos y el aviso de demostración. |
| `/mis_tareas` | Muestra la tarea ficticia 245. |
| `/reportar`, seguido de texto | Confirma recepción de prueba, sin guardar. |
| `/incidencia`, seguido de texto | Confirma recepción de prueba, sin guardar. |
| `/evidencia`, seguido de una foto | Reconoce una fotografía enviada como foto, no como documento. |
| `/cancelar` | Cancela la captura pendiente. |

La consola muestra los mensajes recibidos. Utiliza datos ficticios: esta versión no restringe el acceso a trabajadores registrados. Los mensajes permanecen en Telegram y pueden quedar visibles en la terminal.

## Límites y diagnóstico

- La sesión de captura y el avance de lectura se conservan solo en memoria; se pierden al reiniciar.
- El script descarta mensajes anteriores al arranque. Una respuesta fallida puede perderse.
- Si falta `TELEGRAM_BOT_TOKEN`, configúralo en la misma ventana desde la que ejecutas Python.
- HTTP 401 indica que debes revisar el token.
- HTTP 409 puede indicar otro receptor activo. Revisa también la otra computadora.
- Si existe un webhook, el script termina sin modificarlo. Revisa qué servicio lo utiliza antes de cambiar la configuración.

## Siguiente etapa

Desarrollar el integrador con trabajadores vinculados a Telegram, permisos sobre las actividades existentes, reportes persistentes, almacenamiento de evidencias y reintentos. Incorporar este archivo al repositorio no implementa todavía esas funciones.
