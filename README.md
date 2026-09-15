# Plataforma Pulso Ciudadano - Etapa 1 local

Primera base local de la plataforma integrada. No modifica las bases de los Pulsos existentes ni usa servicios de nube.

## Ejecutar

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
