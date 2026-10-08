# Ejecutar en MARISA con PowerShell como administrador.
[CmdletBinding()]
param(
  [string]$AccessUser = "$env:COMPUTERNAME\$env:USERNAME"
)
$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -ine 'MARISA') { throw 'Ejecuta este script EN MARISA, no en las otras computadoras.' }
$targetFolder = 'D:\go2win'
$shareName = 'Go2WinDatos'
if (-not (Test-Path -LiteralPath 'D:\')) { throw 'No existe la unidad D:.' }
New-Item -ItemType Directory -Path $targetFolder -Force | Out-Null
$resolvedFolder = (Resolve-Path -LiteralPath $targetFolder).Path
if ($resolvedFolder -ine $targetFolder) { throw 'La carpeta resuelta no coincide con D:\go2win.' }
$existing = Get-SmbShare -Name $shareName -ErrorAction SilentlyContinue
if ($existing -and $existing.Path -ine $targetFolder) { throw 'Go2WinDatos ya apunta a otra carpeta. No se modificó.' }
# Modificar archivos solo para la cuenta elegida; no se otorga acceso a Todos.
& icacls.exe $targetFolder /grant "${AccessUser}:(OI)(CI)M"
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron asignar los permisos de carpeta.' }
if (-not $existing) {
  New-SmbShare -Name $shareName -Path $targetFolder -ChangeAccess $AccessUser -FolderEnumerationMode AccessBased | Out-Null
} else {
  Grant-SmbShareAccess -Name $shareName -AccountName $AccessUser -AccessRight Change -Force | Out-Null
}
Write-Output "Carpeta lista: \\MARISA\Go2WinDatos (D:\go2win). Cuenta autorizada: $AccessUser"
Write-Output 'En las otras computadoras abre esa ruta e inicia sesión con esta cuenta de MARISA.'
