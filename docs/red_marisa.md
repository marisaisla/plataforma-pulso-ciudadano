# Red de MARISA

Configuración fija aplicada al adaptador Wi-Fi (MAC A4:F9:33:92:A9:3C).

| Campo | Valor |
|---|---|
| IP | 192.168.1.10 |
| Máscara | 255.255.255.0 |
| Prefijo | 24 |
| Puerta de enlace | 192.168.1.254 |
| DNS preferido | 192.168.1.254 |

La IP está fuera del rango DHCP observado del módem (192.168.1.64–253).
No hubo respuesta ARP para esa IP antes del cambio y Windows la marcó Preferred
al aplicarla. Un equipo apagado con una configuración manual previa no se puede
excluir con esas comprobaciones.

## Jorge

Cambiar PGHOST a 192.168.1.10 en su .env y el campo Host de la conexión en pgAdmin.
Mantener puerto 5432, base go2win_desarrollo y usuario go2win_jorge.
Reiniciar su Go2Win después del cambio. MARISA conserva PGHOST=localhost.
La regla de firewall sigue permitiendo exclusivamente el cliente 192.168.1.189;
si cambia la IP de Jorge, también deberá revisarse esa autorización.
La prueba de conexión desde Jorge queda pendiente.

## Volver a automático para otra red

1. Windows + R, escribir ncpa.cpl y pulsar Enter.
2. Wi-Fi → Propiedades → Protocolo de Internet versión 4 (TCP/IPv4) → Propiedades.
3. Seleccionar Obtener una dirección IP automáticamente y Obtener la dirección
   del servidor DNS automáticamente; aceptar.
4. Reconectar el Wi-Fi si hace falta.

Al regresar a esta red, introducir de nuevo los valores fijos de la tabla.
La configuración manual corresponde al adaptador y afecta su uso en otras redes.
Los datos de PostgreSQL permanecen en MARISA; localhost funciona en cualquier red.

El script scripts/configurar_ip_marisa.ps1 -Automatico también restaura DHCP y DNS
automáticos, ejecutándolo como administrador. Conserva la regla del firewall para
192.168.1.10 en la red habitual. El modo de aplicación inicial del script requiere
la IP original 192.168.1.127; para otros estados usar los pasos manuales anteriores.
Los respaldos de configuración y el resultado están en data/backups/red_marisa/.
