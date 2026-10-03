param([switch]$Automatico)
$ErrorActionPreference = 'Stop'
$principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Se requiere PowerShell como administrador.' }
$adapter = Get-NetAdapter -Name 'Wi-Fi'
if ($adapter.MacAddress -ne 'A4-F9-33-92-A9-3C') { throw 'Este script corresponde exclusivamente al Wi-Fi de MARISA.' }
$ruleName = 'Go2Win-PostgreSQL-Equipo2'
$logDir = Join-Path $PSScriptRoot '..\data\backups\red_marisa'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$log = Join-Path $logDir 'resultado.txt'
function Run-Netsh([string[]]$Arguments) {
    & netsh.exe @Arguments | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "netsh fallo: $LASTEXITCODE" }
}
function Restore-Automatic {
    Run-Netsh @('interface','ipv4','set','address','name=Wi-Fi','source=dhcp')
    Run-Netsh @('interface','ipv4','set','dnsservers','name=Wi-Fi','source=dhcp')
}
if ($Automatico) {
    Restore-Automatic
    'DHCP y DNS automaticos activados. La regla PostgreSQL conserva la IP fija de la red habitual.' | Set-Content $log
    exit
}
$current = Get-NetIPAddress -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4
if (@($current.IPAddress) -notcontains '192.168.1.127') { throw 'La IP inicial no es 192.168.1.127; revisar antes de aplicar.' }
$rule = Get-NetFirewallRule -Name $ruleName
$filter = $rule | Get-NetFirewallAddressFilter
if ($filter.LocalAddress -ne '192.168.1.127' -or $filter.RemoteAddress -ne '192.168.1.189') { throw 'La regla de firewall cambio; revisar.' }
$snapshot = [ordered]@{
    Fecha = (Get-Date).ToString('o'); Adaptador = $adapter.Name; MAC = $adapter.MacAddress
    IP = @($current.IPAddress); Prefijo = @($current.PrefixLength)
    Gateway = @(Get-NetRoute -InterfaceIndex $adapter.ifIndex -DestinationPrefix '0.0.0.0/0' | Select-Object -ExpandProperty NextHop)
    DNS = @(Get-DnsClientServerAddress -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 | Select-Object -ExpandProperty ServerAddresses)
    FirewallLocal = $filter.LocalAddress; FirewallRemoto = $filter.RemoteAddress
}
$snapshot | ConvertTo-Json | Set-Content (Join-Path $logDir ('antes_' + (Get-Date -Format yyyyMMdd_HHmmss) + '.json'))
try {
    $rule | Set-NetFirewallRule -LocalAddress '192.168.1.10'
    Run-Netsh @('interface','ipv4','set','address','name=Wi-Fi','source=static','address=192.168.1.10','mask=255.255.255.0','gateway=192.168.1.254','store=persistent')
    Run-Netsh @('interface','ipv4','set','dnsservers','name=Wi-Fi','source=static','address=192.168.1.254','validate=no')
    Start-Sleep -Seconds 5
    $new = Get-NetIPAddress -InterfaceIndex $adapter.ifIndex -IPAddress '192.168.1.10'
    if ($new.AddressState -ne 'Preferred') { throw 'La nueva IP no esta disponible o tiene conflicto.' }
    if (-not (Test-Connection -ComputerName '192.168.1.254' -Count 2 -Quiet)) { throw 'No responde la puerta de enlace.' }
    Resolve-DnsName 'www.microsoft.com' -Server '192.168.1.254' -DnsOnly -ErrorAction Stop | Out-Null
    'OK: IP fija 192.168.1.10/24, gateway y DNS 192.168.1.254. Firewall actualizado solo para Jorge 192.168.1.189.' | Set-Content $log
} catch {
    $failure = $_.Exception.Message
    try {
        Restore-Automatic
        Get-NetFirewallRule -Name $ruleName | Set-NetFirewallRule -LocalAddress '192.168.1.127'
        "ERROR: $failure. Restaurados DHCP, DNS automatico y firewall anterior." | Set-Content $log
    } catch {
        "ERROR: $failure. Restauracion incompleta: $($_.Exception.Message). Revisar Wi-Fi manualmente." | Set-Content $log
    }
    exit 1
}
