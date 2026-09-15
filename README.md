# Plataforma Pulso Ciudadano - Etapa 1 local

Primera base local de la plataforma integrada. No modifica las bases de los Pulsos existentes ni usa servicios de nube.

## Ejecutar

~~~powershell
cd C:\Users\jorge\Documents\Codex\2026-09-05\Plataforma-Pulso-Ciudadano-Local
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
~~~

La aplicación crea automáticamente el archivo data\pulso_ciudadano_local.db.

## Alcance inicial

- Perfiles de personas, instituciones, partidos o temas.
- Historial de cargos, candidaturas y condición temporal.
- Territorios y fuentes asignadas a cada perfil.
- Base preparada para importar después resultados de Pulso detallado, Pulso necesidades y Pulso medios.

La etapa 1 funciona localmente. No requiere Supabase ni otro servicio de infraestructura.
