# Plataforma Pulso Ciudadano - Etapa 1 local

El **Dashboard de indicadores** presenta las 45 variables con sus estados, cuatro
indicadores exploratorios y series INEGI existentes, consultadas por API. Se encuentra
en el bloque de diagnóstico y requiere administrador. Ver [guía del dashboard](backend/DASHBOARD.md).
La pestaña **Encuestas y expediente** conecta además las mediciones, cargos, documentos y
evidencias existentes por perfil, distinguiendo porcentajes reportados de puntuaciones de viabilidad.

Primera base local de la plataforma integrada. No modifica las bases de los Pulsos existentes ni usa servicios de nube.

## Base histórica electoral

La rama de desarrollo incorpora la Fase 1 del modelo de inteligencia electoral: catálogos
geográficos versionados, elecciones y cargas de resultados con fuente, validación y revisiones.
La pantalla **Base histórica electoral** utiliza FastAPI y requiere administrador.
Aplicar `python -m backend.migrate_history` con el entorno del proyecto antes de usarla.
La instalación crea una base vacía; las cifras oficiales deben obtenerse, revisarse y cargarse.
Consultar [la guía de base histórica](backend/HISTORY.md) y [el README del backend](backend/README.md).

La **Fase 2 — Motor de indicadores** añade catálogo, fórmulas electorales, controles de calidad,
comparaciones documentadas, tablas y gráficas por API. Abrir **Motor de indicadores** en el
bloque de diagnóstico; consultar [INDICATORS.md](backend/INDICATORS.md). No modifica las
cargas anteriores y las explora únicamente con reconocimiento explícito de su estado.

## Ejecutar

Go2Win ahora requiere inicio de sesión. Para el primer acceso ejecuta `.\.venv\Scripts\python.exe scripts\crear_admin.py` y define tus propias credenciales. Consulta [Inicio de sesión](INICIO_DE_SESION.md). El usuario de campo existente conserva su rol y Telegram.

~~~powershell
## 🚀 Instalación y Ejecución

1. **Clonar el repositorio:**
   ```bash
   git clone [https://github.com/tu-usuario/plataforma-pulso-ciudadano.git](https://github.com/tu-usuario/plataforma-pulso-ciudadano.git)
   cd plataforma-pulso-ciudadano

py -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

streamlit run app.py

---

## 🔄 Ejecuciones Posteriores (Uso Diario)

Una vez realizada la instalación inicial, no es necesario volver a crear el entorno virtual ni instalar las librerías. Para volver a ejecutar la aplicación en el futuro, solo sigue estos dos pasos:

1. **Abrir la terminal en la carpeta del proyecto y activar el entorno:**
   * **Windows (PowerShell / CMD):**
     ```bash
     .\.venv\Scripts\Activate.ps1
     ```
   * **Git Bash / Linux / macOS:**
     ```bash
     source .venv/bin/activate
     ```

2. **Ejecutar la aplicación:**
   ```bash
   streamlit run app.py

~~~

La aplicación crea automáticamente el archivo data\pulso_ciudadano_local.db.

## Alcance inicial

- Perfiles de personas, instituciones, partidos o temas.
- Historial de cargos, candidaturas y condición temporal.
- Territorios y fuentes asignadas a cada perfil.
- Base preparada para importar después resultados de Pulso detallado, Pulso necesidades y Pulso medios.

La etapa 1 funciona localmente. No requiere Supabase ni otro servicio de infraestructura.

## Prueba de Telegram

Para registrar trabajadores y activar su acceso real, consulta [Vinculación de personal con Telegram](TELEGRAM_INTEGRADOR.md). Ejecuta `scripts/integrador_telegram.py` en lugar del script de demostración. Permite consultar tareas asignadas, confirmar recepción, enviar reportes de texto o una foto con descripción y folio, y consultar su revisión. Para PostgreSQL aplica primero `scripts/agregar_evidencias_postgresql.sql`.

Los cinco roles y sus alcances por campaña y territorio se administran en **Administración de usuarios**. Consulta [Roles y permisos](ROLES_Y_PERMISOS.md) para configurarlos y conocer el alcance del control de acceso actual.

El comando `/simpatizante` registra nombre, teléfono, territorio, sección opcional, clave de elector y autorizaciones en un catálogo consultable por rol y alcance. Para PostgreSQL aplica también `scripts/agregar_simpatizantes_postgresql.sql`. El envío de información a simpatizantes queda pendiente.

`/necesidad` permite a campo registrar necesidades detectadas o comentadas por estado,
municipio y sección, sin depender de una tarea. Coordinadores y directores consultan
**Mi espacio Go2Win → Necesidades** dentro de su campaña y territorio autorizado.
La tabla es `field_needs`; PostgreSQL requiere `scripts/agregar_necesidades_postgresql.sql`.

El script `scripts/prueba_bot_telegram.py` permite ejecutar la demostración del bot desde este proyecto. Consulta [la guía de Telegram](TELEGRAM_PRUEBA.md) para configurar el token en PowerShell y probar los comandos. Esta prueba todavía no consulta ni guarda datos en Go2Win.

## Cuestionarios de campo

El administrador abre **Cuestionarios de campo** desde la barra lateral o desde la
asignación de una actividad. Coordinación lo encuentra en **Mi espacio Go2Win →
Cuestionarios**, para actividades asignadas a su equipo dentro de su alcance.

1. Seleccionar una actividad y abrir **Crear o editar cuestionario**.
2. Capturar nombre, instrucciones, modalidad (una respuesta por actividad o varias
   entrevistas) y hasta 30 preguntas de texto, número o una opción. Configurar
   preguntas obligatorias, límites numéricos e indicadores de conteo, suma o promedio.
3. Probar **Mostrar vista previa**, guardar borrador o publicar. Las versiones
   publicadas son inmutables; al seleccionarlas en el editor se crea una copia.
4. Seleccionar el cuestionario publicado y la meta en **Asignar cuestionario a la
   actividad**. Se pueden reutilizar cuestionarios de actividades autorizadas de la
   misma campaña. En modalidad de una respuesta la meta debe ser 1.
5. Campo abre **Responder cuestionario** en `/mis_tareas` o `/tarea FOLIO`, inicia
   sesión con su cuenta web y envía sus respuestas. También puede responder desde
   la pestaña Cuestionarios de su espacio web.

El configurador, la captura y los indicadores utilizan la API por HTTP mediante
`services/field_surveys.py`; las reglas y el acceso a PostgreSQL residen en
`backend/surveys.py`. No se consulta SQL como alternativa si la API falla.

Configurar `GO2WIN_PUBLIC_URL=https://direccion-del-sistema` en la configuración
privada del **servidor FastAPI**. Debe ser la dirección real de la pantalla web de
Go2Win accesible desde los celulares, distinta de `API_BASE_URL`. Sin una dirección HTTPS configurada el bot no
presenta el botón web. Esta opción no publica el servidor ni configura un túnel.
Crear las cuentas web del personal en **Administración de usuarios**. Actualizar y
reiniciar FastAPI, Streamlit y el receptor `python -m backend.telegram_polling`.
No ejecutar simultáneamente el integrador anterior. La asignación se consulta con `/mis_tareas`; no
se envía una notificación automática.

Las respuestas guardan folio, trabajador, fecha UTC, territorio y versión. El envío
es definitivo; una segunda entrega del mismo formulario no duplica el registro.
Las tareas cerradas, cambios de responsable, cambios de cuestionario y revocaciones
de alcance invalidan el acceso correspondiente. El enlace no sustituye la sesión
web ni permite capturar por otro trabajador.

En **Indicadores y respuestas** se calculan el total de capturas, avance de meta y
los indicadores configurados por pregunta. Se contabilizan al enviar, sin revisión
previa. Conteo excluye respuestas vacías y promedio usa solo números respondidos.
Los indicadores son operativos por actividad y versión; no sobrescriben indicadores
oficiales INEGI ni metas PMD. Las versiones anteriores conservan su historial.

SQLite crea estas tablas al iniciar. En PostgreSQL ejecutar antes de iniciar la
versión nueva: `.\.venv\Scripts\python.exe scripts\aplicar_actualizacion_telegram.py`.
El script incluye `scripts/agregar_cuestionarios_postgresql.sql` y solo admite la
base `go2win_desarrollo`. Para otras bases, administrar esa migración explícitamente.
