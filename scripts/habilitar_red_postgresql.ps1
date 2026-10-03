# Ejecutar como administrador en MARISA. No abre acceso desde otras IP.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Ejecuta PowerShell como administrador.'
}
$ruleName = 'Go2Win-PostgreSQL-Equipo2'
$existing = Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue
if ($existing) {
    $address = $existing | Get-NetFirewallAddressFilter
    $port = $existing | Get-NetFirewallPortFilter
    $application = $existing | Get-NetFirewallApplicationFilter
    if ($address.RemoteAddress -ne '192.168.1.189' -or $address.LocalAddress -ne '192.168.1.10' -or
        $port.LocalPort -ne '5432' -or $port.Protocol -ne 'TCP' -or
        $application.Program -ne 'C:\Program Files\PostgreSQL\18\bin\postgres.exe' -or
        $existing.Direction -ne 'Inbound' -or $existing.Action -ne 'Allow' -or $existing.Enabled -ne 'True') {
        throw 'La regla existente tiene otra configuracion. Revisarla antes de continuar.'
    }
} else {
    New-NetFirewallRule -Name $ruleName -DisplayName 'Go2Win PostgreSQL - equipo 192.168.1.189' `
        -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5432 `
        -LocalAddress 192.168.1.10 -RemoteAddress 192.168.1.189 `
        -Program 'C:\Program Files\PostgreSQL\18\bin\postgres.exe' -Profile Any | Out-Null
}
Write-Output 'Firewall listo: 192.168.1.189 puede conectar a 192.168.1.10:5432.'
