# Manual de usuario

## Plataforma Pulso Ciudadano - Etapa 1 local

Este manual explica cómo usar la primera versión local. La información se guarda en la computadora donde se ejecuta la aplicación. No utiliza servidores de nube ni claves de X u OpenAI en esta etapa.

## 1. Iniciar la aplicación

Abra PowerShell y ejecute los siguientes comandos, uno después del otro:

    cd C:\Users\jorge\Documents\Codex\2026-09-05\Plataforma-Pulso-Ciudadano-Local

    .\.venv\Scripts\python.exe -m streamlit run app.py

Abra la dirección que aparezca en pantalla. Normalmente es http://localhost:8501.

Para detener la aplicación, vuelva a PowerShell y presione Ctrl + C.

## 2. Orden recomendado de uso

La plataforma se configura en este orden:

1. Crear el perfil que se desea monitorear.
2. Registrar su cargo, candidatura o condición.
3. Registrar el territorio.
4. Registrar las fuentes de información.
5. Capturar publicaciones RSS y revisar la clasificación inicial.

## 3. Inicio

La página Inicio muestra cuatro indicadores:

- Perfiles: personas, partidos, instituciones o temas registrados.
- Cargos o candidaturas: historial de cada perfil.
- Territorios: estados, municipios, distritos, secciones o localidades registrados.
- Fuentes configuradas: redes, medios, feeds RSS o fuentes institucionales asociadas a los perfiles.

La base local se llama pulso_ciudadano_local.db y se crea dentro de la carpeta data.

## 4. Crear un perfil

Entre a Perfiles y trayectorias. En el apartado Perfiles capture:

- Nombre: persona, institución o tema que se monitoreará.
- Tipo de perfil:
  - Persona: candidato, funcionaria, funcionario o figura pública.
  - Partido político: organización política.
  - Institución pública: dependencia, ayuntamiento o gobierno.
  - Tema sin actor: asunto general, por ejemplo agua en Ciudad Juárez.
- Notas opcionales: información breve para identificar el perfil.

Presione Guardar perfil. El perfil aparecerá en la tabla inferior.

## 5. Registrar cargo, candidatura o condición

En la misma página, use el apartado Cargo, candidatura o condición.

Capture:

- Perfil: seleccione la persona o institución ya creada.
- Cargo o candidatura: por ejemplo, Gobernadora de Chihuahua.
- Condición: Candidato/a, En funciones, Exfuncionario/a u Otro.
- Inicio y fin: fechas del periodo, campaña o cargo.
- Partido o coalición: opcional.

Una misma persona puede tener varios registros de trayectoria. Esto conserva su historia: por ejemplo, candidatura municipal y después presidencia municipal.

### Ejemplo: Maru Campos

- Perfil: Maru Campos
- Tipo de perfil: Persona
- Cargo: Gobernadora de Chihuahua
- Condición: En funciones
- Inicio: 08/09/2021
- Partido o coalición: PAN

## 6. Registrar territorios

Entre a Territorio y fuentes. En Territorios capture el nivel geográfico:

- Estado
- Municipio
- Distrito
- Sección electoral
- Colonia
- Localidad

Para un perfil estatal, como Maru Campos, se puede registrar:

- Nivel territorial: Estado
- Estado: Chihuahua

El territorio queda disponible en la base local y puede consultarse visualmente en el módulo **GIS de gobierno**.

## 7. Registrar fuentes una por una

En Fuentes por perfil, capture:

- Perfil a monitorear: el perfil relacionado.
- Tipo de fuente: X, YouTube, RSS, Medio digital, Encuesta, INEGI/DENUE u Otra.
- Nombre de la fuente: nombre de la cuenta, medio o fuente.
- Cuenta o URL: enlace de la cuenta, canal, sitio o feed.

Una fuente por registro facilita activarla, desactivarla y conocer de dónde proviene cada publicación.

## 8. Carga masiva de fuentes

Cuando se tienen muchas fuentes, use Carga masiva de fuentes:

1. Seleccione el perfil para todas las fuentes del archivo.
2. Presione Descargar plantilla CSV.
3. Abra el archivo con Excel.
4. Agregue una fila por fuente.
5. Guarde el archivo como CSV.
6. Súbalo en Archivo CSV de fuentes.
7. Revise la vista previa.
8. Presione Importar fuentes del archivo.

El CSV necesita estas columnas:

    source_type,name,account_or_url
    RSS,Nombre del medio,https://ejemplo.mx/feed
    YouTube,Nombre del canal,https://youtube.com/@canal

La aplicación omite registros duplicados e informa las filas no válidas.

## 9. Mensajes, análisis y resultados

En **20 · Fuentes y actualización** se capturan publicaciones. En **22 · Enfoques de análisis** se selecciona el perfil y se pulsa **Analizar mensajes pendientes**.

Cada ejecución procesa hasta diez mensajes. Para cada mensaje se hace una sola consulta de API con los enfoques faltantes o básicos: sentimiento hacia el perfil, necesidades, gestión, tipo de contenido y territorio. Los resultados anteriores se conservan. Un mensaje completo no se vuelve a consultar.

El botón indica cuántas consultas puede generar. Cambiar filtros, leer mensajes, navegar o consultar gráficas no llama a la IA.

En **Consultar resultados** se filtra por fuente, periodo, sentimiento, estado o texto. Las gráficas muestran distribución, evolución y temas. Los botones **Anterior** y **Siguiente** permiten ver cada mensaje con todos sus análisis y su enlace original. Los mensajes parciales muestran los enfoques que faltan; las gráficas usan el sentimiento de Perfil político o, si no existe, la clasificación anterior. No representan una encuesta de aprobación.

En **23 · Vinculación territorial**, los lugares detectados se muestran junto a los municipios vinculados. La vinculación exige una mención explícita y un nombre del catálogo municipal; no deduce el domicilio del autor ni hace otra consulta de IA.

En **25 · Revisión e historial** se consultan los enfoques guardados, método, modelo y fecha, además de la clasificación original y sus versiones anteriores. Completar un mensaje agrega enfoques faltantes. Si sólo había una clasificación básica o incompleta, se amplía y su versión anterior se conserva en el historial. Los análisis completos no se reprocesan.

## 10. Prompts y consultas IA

Entre a **Prompts y consultas IA** para formular preguntas opcionales sobre mensajes y sus análisis guardados. Cada ejecución genera una nueva consulta de API con costo; leer el historial no genera otra consulta. Los análisis guardados se envían como interpretaciones y los textos originales como respaldo.

1. Seleccione el perfil, fuente y periodo.
2. Mantenga activado el filtro de mensajes relacionados cuando analice una persona específica.
3. Elija una plantilla del catálogo o seleccione **Prompt libre**.
4. Revise los mensajes que se enviarán como evidencia y ajuste el máximo, de 1 a 30.
5. Presione **Ejecutar consulta**.

También puede seleccionar **Chat IA general**. Este modo usa el mismo catálogo de prompts, pero no envía mensajes de su base. Sirve para hacer consultas generales; la respuesta indicará que no utilizó registros ni fuentes de la plataforma.

El catálogo inicial incluye: Resumen de percepción pública, Temas críticos y alertas, Necesidades ciudadanas, Cobertura de medios y Comparativo del periodo.

La respuesta no modifica los mensajes originales ni los resultados de los enfoques. Cada consulta conserva la instrucción, los registros usados, el modelo y la respuesta en el historial.

Todas las consultas devuelven estas secciones: **Hallazgos principales**, **Riesgos o temas a vigilar**, **Recomendaciones** y **Fuentes consultadas**. Las recomendaciones son de seguimiento, comunicación pública o gestión y deben estar sustentadas en las fuentes seleccionadas.

## 11. GIS de gobierno y contexto territorial

Entre a **GIS de gobierno** y seleccione el perfil. El mapa adopta el estado asociado a su cargo o territorio: por ejemplo, Luis Donaldo Colosio Riojas muestra Sonora y un perfil de Chihuahua muestra Chihuahua. Los indicadores disponibles dependen de la capa territorial: población y viviendas están disponibles para Sonora; Chihuahua añade internet, agua entubada, drenaje, salud y participaciones Ramo 28.

- Pase el cursor sobre un municipio para ver el valor del indicador activo.
- Use el selector de municipio para ver el detalle y el enlace disponible a su Plan Municipal de Desarrollo.
- Puede cargar un GeoJSON municipal actualizado sin modificar los mensajes ni la base de datos.
- Esta vista sirve para contexto de gobierno. Los resultados electorales se conservan en el GIS de campaña como una vista independiente.

## 12. Qué no hace todavía esta versión

- No consulta automáticamente X.
- No consulta automáticamente YouTube.
- No utiliza OpenAI.
- No publica información en ÁGORA.
- No sustituye revisión humana ni una encuesta representativa.

Estas funciones se incorporarán por módulos en versiones posteriores, manteniendo las claves de API en los Pulsos privados.

## 13. Cuidados recomendados

- Revise que cada URL corresponde realmente a la fuente que desea monitorear.
- Use una fuente por perfil; no mezcle personas distintas en el mismo perfil.
- Revise resultados negativos o de urgencia alta antes de interpretarlos.
- Mantenga una copia de respaldo de la carpeta data.
- No guarde claves de API dentro de la base local ni en archivos CSV.

## 14. Próximos módulos previstos

1. Importación controlada de resultados de Pulso detallado, Pulso necesidades y Pulso medios.
2. Captura de medios digitales y YouTube.
3. Clasificación con IA privada, cuando se autorice.
4. Relación automática y verificable entre mensajes y municipio cuando el territorio esté expresamente mencionado.
5. Dashboard ejecutivo, alertas y reportes.
6. Migración a ambiente productivo cuando el piloto esté validado.
