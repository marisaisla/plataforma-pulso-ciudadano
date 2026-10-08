# Match services.settings/storage: environment first, then the project .env.
function Get-Go2WinFilesRoot {
    $projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
    $value = [Environment]::GetEnvironmentVariable('GO2WIN_FILES_ROOT')
    if (-not $value) {
        $settingsFile = Join-Path $projectRoot '.env'
        if (Test-Path -LiteralPath $settingsFile -PathType Leaf) {
            foreach ($line in Get-Content -LiteralPath $settingsFile -Encoding UTF8) {
                if ($line.StartsWith('GO2WIN_FILES_ROOT=')) {
                    $value = $line.Substring('GO2WIN_FILES_ROOT='.Length)
                    break
                }
            }
        }
    }
    if ($null -ne $value) { $value = $value.Trim() }
    if (-not $value) { $value = $projectRoot }
    if ($value -notmatch '^(?:[A-Za-z]:[\\/]|\\\\[^\\/]+[\\/][^\\/]+)') {
        throw 'GO2WIN_FILES_ROOT debe ser una ruta absoluta o UNC.'
    }
    if (-not (Test-Path -LiteralPath $value -PathType Container)) {
        throw 'La carpeta de Go2Win no esta disponible. Revisa MARISA, la red y tus credenciales.'
    }
    return $value
}
