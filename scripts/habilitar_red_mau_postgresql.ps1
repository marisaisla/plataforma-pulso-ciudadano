$ErrorActionPreference = 'Stop'
$logDir = Join-Path $PSScriptRoot '..\data\backups\red_mau'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$log = Join-Path $logDir 'resultado.txt'
try {
    $principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Ejecutar como administrador.' }
    $hba = 'D:\PostgreSQL\data\pg_hba.conf'
    $line = 'host    go2win_desarrollo    go2win_mau    192.168.1.65/32    scram-sha-256'
    $content = [IO.File]::ReadAllText($hba)
    if ($content -notmatch '(?m)^host\s+go2win_desarrollo\s+go2win_mau\s+192\.168\.1\.65/32\s+scram-sha-256\s*$') {
        Copy-Item -LiteralPath $hba -Destination ($hba + '.before_mau_' + (Get-Date -Format yyyyMMdd_HHmmss))
        [IO.File]::AppendAllText($hba, "`r`n# Go2Win: Mau, solo equipo autorizado`r`n$line`r`n", [Text.UTF8Encoding]::new($false))
    }
    $name = 'Go2Win-PostgreSQL-Mau'
    $existing = Get-NetFirewallRule -Name $name -ErrorAction SilentlyContinue
    if ($existing) {
        $address = $existing | Get-NetFirewallAddressFilter
        $port = $existing | Get-NetFirewallPortFilter
        $app = $existing | Get-NetFirewallApplicationFilter
        if ($address.LocalAddress -ne '192.168.1.10' -or $address.RemoteAddress -ne '192.168.1.65' -or
            $port.LocalPort -ne '5432' -or $port.Protocol -ne 'TCP' -or
            $app.Program -ne 'C:\Program Files\PostgreSQL\18\bin\postgres.exe' -or
            $existing.Direction -ne 'Inbound' -or $existing.Action -ne 'Allow' -or $existing.Enabled -ne 'True') {
            throw 'La regla existente difiere de lo esperado; no se modifico.'
        }
    } else {
        New-NetFirewallRule -Name $name -DisplayName 'Go2Win PostgreSQL - Mau 192.168.1.65' `
            -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5432 `
            -LocalAddress '192.168.1.10' -RemoteAddress '192.168.1.65' `
            -Program 'C:\Program Files\PostgreSQL\18\bin\postgres.exe' -Profile Any | Out-Null
    }
    # PostgreSQL on Windows applies pg_hba.conf changes to new connections.
    'OK: HBA y firewall preparados para go2win_mau desde 192.168.1.65 hacia 192.168.1.10:5432. Falta comprobar cuenta y conexion remota.' | Set-Content $log
} catch {
    ('ERROR: ' + $_.Exception.Message) | Set-Content $log
    exit 1
}
