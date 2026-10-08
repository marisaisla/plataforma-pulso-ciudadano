# Go2Win en tres computadoras

## Distribución

- Cada computadora tiene un checkout Git, su entorno Python y su `.env` privado.
- PostgreSQL permanece en MARISA. No compartir una base SQLite para uso simultáneo.
- Los archivos comunes estarán en `D:\go2win` de MARISA, publicados como `\\MARISA\Go2WinDatos`.
- MARISA debe permanecer encendida, sin suspensión y conectada a la red.

```text
D:\go2win\
  data\                    Cartografía, insumos y reference_documents
  output\                  PDF, HTML, presentaciones, videos y otros entregables
  assets\go2win_video\     Material audiovisual para generar videos
  _migration\              Manifiestos de copia y verificación
```

Git conserva código, scripts, pruebas, documentación, lista de dependencias y el logo de la interfaz. No conserva los directorios anteriores, los temporales `.build`/`tmp`, las credenciales ni los respaldos. Ignorar y dejar de seguir archivos no borra el historial previo de Git.

## 1. Crear la carpeta EN MARISA

Copiar `scripts/crear_carpeta_compartida_marisa.ps1` a MARISA y ejecutarlo con PowerShell como administrador:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\crear_carpeta_compartida_marisa.ps1
```

El script autoriza la cuenta de Windows que lo ejecuta. Para elegir otra cuenta existente de MARISA, agregar `-AccessUser 'MARISA\nombre_usuario'`. Utilizar una cuenta con contraseña, no el PIN de Windows. Desde las otras dos computadoras, abrir `\\MARISA\Go2WinDatos` en el Explorador e ingresar esa cuenta cuando Windows la solicite. No poner la contraseña en Git ni en scripts.

Si no se puede abrir: verificar que MARISA está encendida y que la red de confianza permite compartir archivos e impresoras. El script no modifica el firewall, no crea usuarios y no concede permisos a Todos. Si la carpeta ya existe, conserva sus archivos y sus permisos anteriores.

## 2. Copiar desde la computadora que tiene los archivos

Cerrar las herramientas que estén generando o modificando archivos durante la copia. Desde la raíz del proyecto en JORGE:

```powershell
.venv\Scripts\python.exe scripts/copy_shared_files.py --destination '\\MARISA\Go2WinDatos'
.venv\Scripts\python.exe scripts/copy_shared_files.py --destination '\\MARISA\Go2WinDatos' --apply
```

El primer comando revisa sin copiar. El segundo copia y verifica SHA256. No elimina los originales, no sobrescribe versiones diferentes y excluye `.db`, `.dump`, logs y `data/backups`. Los respaldos de PostgreSQL se administran por separado. Un error de verificación o un archivo parcial exige revisar el archivo afectado antes de reintentar. No activar la carpeta hasta terminar.

La copia preserva todos los subdirectorios para conservar los enlaces relativos de HTML y documentos. Algunos materiales intermedios ya están en `output` y se conservan durante esta primera separación para no perder trabajo.

## 3. Verificar antes de activar

En cada equipo, con su conexión PostgreSQL configurada:

```powershell
.venv\Scripts\python.exe scripts/check_shared_files.py --root '\\MARISA\Go2WinDatos' --database
```

Este comando solo lee la cartografía y las referencias de documentos. Si reporta documentos externos al proyecto (por ejemplo, Downloads u OneDrive), copiarlos explícitamente a `data/reference_documents` y registrar la nueva ruta relativa en el expediente. No se busca solo por nombre porque puede haber archivos distintos con el mismo nombre.

## 4. Activar en cada computadora

Agregar a su `.env` local, conservando las otras opciones y credenciales:

```dotenv
GO2WIN_FILES_ROOT=\\MARISA\Go2WinDatos
```

MARISA puede usar la misma UNC o `GO2WIN_FILES_ROOT=D:\go2win`. Reiniciar Streamlit y los procesos de trabajo para recargar las rutas y cachés. Todas las computadoras deben tener esta versión del código antes de activar la variable.

Sin la variable, el sistema conserva las rutas locales anteriores. Con la variable, utiliza la carpeta compartida y no cambia silenciosamente a datos locales si falta un archivo.

Las rutas antiguas de BD que contienen `data/...` u `output/...` se resuelven contra la carpeta configurada. Se conservan los registros de PostgreSQL. Para nuevos documentos preferir `data/reference_documents/nombre.pdf`, sin letra de unidad ni nombre del usuario.

## Escritura y herramientas

El archivo compartido no reemplaza PostgreSQL. Los registros concurrentes de usuarios siguen en la BD. No ejecutar dos importadores o generadores contra el mismo archivo de destino simultáneamente. Usar nombres de salida distintos para cada ejecución.

Los importadores, generadores de documentos y scripts audiovisuales usan `GO2WIN_FILES_ROOT`. Los generadores de video comparten las rutas de sus módulos base; las variantes v3 a v6 heredan esa configuración. Los narradores y el exportador de PowerPoint leen la misma variable mediante `scripts/shared_files.ps1`, independientemente del directorio desde el que se ejecuten.

Los cinco insumos antes ubicados en Descargas/OneDrive se centralizan en `assets/go2win_video/fuentes`: el PDF `Tablero de Mnado Go2Win.pdf`, los tres videos de recorrido y la presentación `Arquitectura_Integracion_Telegram_Go2Win_Tres_Flujos_Operativos.pptx`. Los fotogramas, narraciones, diapositivas e imágenes intermedias mantienen sus subcarpetas existentes bajo `output` y `assets/go2win_video`.

Los entregables nuevos se guardan en `output` de MARISA: `pdf`, `html`, `documentos`, `mapas` y `videos`. Para nuevos scripts utilizar `services.storage.storage_path`; los temporales de revisión pueden permanecer en `.build` o `tmp`, pero el resultado final debe copiarse y verificarse en la carpeta compartida. Esta regla también está registrada en `AGENTS.md`.

Compartir los archivos no instala programas: cada equipo que genere videos necesita sus dependencias Python y FFmpeg; la narración requiere Windows con la voz Microsoft Sabina Desktop y la exportación de diapositivas requiere PowerPoint. No ejecutar dos versiones contra el mismo destino a la vez. Los archivos locales históricos se conservan y no son sincronizados automáticamente.

## Git y transición

Los archivos locales se conservan al retirarlos del índice de Git. En OTRAS computadoras, aplicar un commit que deja de seguir archivos puede retirarlos del checkout: copiar/verificar la carpeta compartida primero. No usar `git clean -fdx`: elimina también archivos ignorados.

No se requiere reescribir el historial para esta separación. Los archivos ya publicados permanecen en commits anteriores. Para volver temporalmente al almacenamiento local, quitar `GO2WIN_FILES_ROOT` y reiniciar, siempre que se hayan conservado las copias locales.
