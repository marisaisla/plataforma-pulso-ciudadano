# Archivos de Go2Win

- Los insumos y entregables compartidos se guardan en la raiz configurada por
  `GO2WIN_FILES_ROOT` (en este equipo: `\\MARISA\Go2WinDatos`).
- Para cualquier nuevo documento, PDF, mapa, presentacion, imagen, audio o video,
  usar `services.storage.storage_path('output/...')`. Para insumos usar
  `storage_path('data/...')` o `storage_path('assets/go2win_video/...')`.
- No usar Descargas, OneDrive ni el `output` local del repositorio como destino
  principal. No volver a copias locales silenciosamente si MARISA no responde.
- Los scripts de PowerShell pueden cargar `scripts/shared_files.ps1` y llamar a
  `Get-Go2WinFilesRoot`. Las credenciales de red son administradas por Windows.
- El codigo, las dependencias, `.env`, SQLite local y los temporales de trabajo
  o revision (`.build`, `tmp`) permanecen locales. Nunca compartir secretos.
- Si una herramienta requiere trabajar localmente, usar un temporal, copiar el
  entregable final a la carpeta compartida, verificar la copia y enlazar ese
  archivo. Conservar los insumos originales y no sobrescribir versiones ajenas.
