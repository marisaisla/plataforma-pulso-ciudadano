# Manual técnico

Este módulo es para quien instala, configura y respalda la Plataforma Pulso Ciudadano. No se requieren cambios técnicos para consultar los tableros.

## 1. Requisitos

- Windows con Python y PowerShell.
- Entorno virtual `.venv` dentro del directorio de la plataforma.
- Archivo `.env` para las credenciales opcionales de X, OpenAI, YouTube e INEGI.

## 2. Arranque local

Abra PowerShell en el directorio de la plataforma y ejecute:

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

La aplicación mostrará una dirección local, normalmente `http://localhost:8501`. Para detenerla presione `Ctrl + C` en esa ventana de PowerShell.

## 3. Configuración de claves

Las claves se guardan en `.env`, nunca dentro de la base de datos, archivos exportados o el dashboard público. Ejemplo:

```text
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.6-luna
X_BEARER_TOKEN=
YOUTUBE_API_KEY=
INEGI_TOKEN=
```

Use el módulo **Conexiones privadas** para comprobar el estado. Una consulta a X, YouTube u OpenAI solo se ejecuta cuando el usuario presiona el botón correspondiente.

## 4. Base de datos y evidencia

La base local se encuentra en `data\pulso_ciudadano_local.db`. Conserva publicaciones originales, fuentes, análisis por enfoque e historial de consultas. No borre ni modifique el archivo mientras Streamlit esté abierto.

Los mensajes originales se conservan en `publications`. Los análisis y las consultas IA se guardan aparte, para que se puedan revisar sin alterar la evidencia capturada.

## 5. Respaldo

1. Detenga la aplicación con `Ctrl + C`.
2. Copie `data\pulso_ciudadano_local.db` a una carpeta de respaldo con fecha.
3. Conserve también `.env` de forma privada y separada; contiene credenciales.
4. Para restaurar, reemplace la base solo con la aplicación detenida.

## 6. Actualización y diagnóstico

- Actualice dependencias solo desde el entorno virtual: `python -m pip install -r requirements.txt`.
- Si el puerto está ocupado, inicie con `streamlit run app.py --server.port 8502`.
- Si una fuente falla, revise primero **Conexiones privadas**, después la cuota de la API y finalmente el mensaje de error de la bitácora de obtención.
- Antes de una actualización, haga respaldo de la base y pruebe con una copia.

## 7. Seguridad operativa

- No comparta `.env` ni tokens en capturas de pantalla, correo o reportes.
- Mantenga acceso físico controlado a la computadora que aloja el piloto.
- El sitio público ÁGORA solo debe recibir resultados agregados: nunca llaves, mensajes privados ni capacidad para ejecutar consultas de pago.
