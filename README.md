# Plataforma Pulso Ciudadano - Etapa 1 local

Primera base local de la plataforma integrada. No modifica las bases de los Pulsos existentes ni usa servicios de nube.

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

Para registrar trabajadores y activar su acceso real, consulta [Vinculación de personal con Telegram](TELEGRAM_INTEGRADOR.md). Ejecuta `scripts/integrador_telegram.py` en lugar del script de demostración. Ya permite consultar tareas asignadas, confirmar recepción, enviar reportes de texto con folio y consultar su revisión. Las evidencias fotográficas siguen pendientes.

Los cinco roles y sus alcances por campaña y territorio se administran en **Personal y Telegram**. Consulta [Roles y permisos](ROLES_Y_PERMISOS.md) para configurarlos y conocer el alcance del control de acceso actual.

El script `scripts/prueba_bot_telegram.py` permite ejecutar la demostración del bot desde este proyecto. Consulta [la guía de Telegram](TELEGRAM_PRUEBA.md) para configurar el token en PowerShell y probar los comandos. Esta prueba todavía no consulta ni guarda datos en Go2Win.
