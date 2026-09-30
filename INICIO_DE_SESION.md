# Inicio de sesión de Go2Win

Go2Win solicita usuario y contraseña antes de mostrar datos. Las cuentas web se vinculan a `field_workers`; el rol, equipo, territorio y cuenta de Telegram existentes se conservan.

## Crear el primer administrador

En PowerShell, desde el proyecto:

```powershell
Set-Location 'D:\PROYECTOS\plataforma-pulso-ciudadano'
.\.venv\Scripts\python.exe scripts\crear_admin.py
```

Escribe el nombre del administrador, un nombre de usuario y una contraseña de 12 a 128 caracteres. La contraseña se captura oculta y se pide dos veces. No se comparte en el chat ni se añade al código. El programa crea una persona administradora nueva, separada del usuario de campo ya vinculado a Telegram. No existe una contraseña predeterminada. Esta herramienta se puede usar únicamente antes de que exista la primera cuenta web.

Después reinicia Go2Win:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Si el navegador ya estaba abierto, recarga la página e inicia sesión. El integrador de Telegram sigue usando su token de bot y no requiere esta contraseña.

## Dar acceso al personal

1. Inicia sesión con el administrador.
2. Abre **Personal y Telegram** y selecciona un trabajador.
3. En **Acceso a Go2Win**, escribe su usuario y una contraseña temporal, repítela y pulsa **Crear o restablecer acceso web**.
4. Entrega las credenciales a esa persona por un canal privado.
5. Al ingresar, deberá cambiar la contraseña temporal antes de acceder a sus datos.

La misma sección permite restablecer una contraseña. Restablecerla cierra las sesiones anteriores. Los nombres de usuario son únicos, sin distinción de mayúsculas, y admiten letras sin acentos, números, punto, guion y guion bajo.

## Pantallas por rol

| Rol | Acceso web de esta etapa |
| --- | --- |
| Administrador | Pantallas generales existentes, configuración, usuarios, asignaciones y revisión de reportes. |
| Personal de campo | Panel **Mi espacio Go2Win** con sus tareas y reportes dentro de sus alcances autorizados. |
| Supervisor | Panel operativo con tareas y reportes de su personal asignado; puede revisar reportes autorizados, excepto los propios. |
| Coordinador | Panel operativo con tareas y reportes de su equipo y tareas sin asignar de su campaña y territorio; puede asignar a personal elegible y revisar reportes autorizados. |
| Director de campaña | Consulta de tareas y resultados dentro de las campañas y territorios autorizados. |

Las pantallas analíticas anteriores contienen consultas generales y edición. En esta etapa están restringidas a administradores; no se entregan a otros roles como si estuvieran filtradas. La edición de prioridades para director y la creación de actividades para coordinador desde el nuevo panel quedan pendientes. El personal continúa confirmando recepción y enviando avances por Telegram. Las decisiones de revisión y asignación desde el panel registran el usuario autenticado.

El bloqueo se aplica antes de ejecutar las pantallas generales. Las consultas del panel operativo se filtran en el backend y las asignaciones y revisiones vuelven a verificar la sesión y los permisos al guardar. Alterar una selección de la interfaz no concede permisos.

Para que un coordinador reparta tareas, el administrador debe asignarle un equipo no vacío y colocar al personal de campo o supervisores en ese mismo equipo, desde **Personal y Telegram → Rol y equipo**. Coordinador y destinatario deben tener autorizada la campaña y el territorio de la actividad. En **Mi espacio Go2Win → Tareas**, abre una actividad pendiente o en curso, selecciona **Responsable** y pulsa **Asignar tarea**. Si falta el equipo, el panel muestra el aviso de configuración; las tareas sin asignar del ámbito autorizado siguen visibles.

## Sesiones y contraseñas

### Modo de desarrollo local

En el archivo `.env` de la raíz del proyecto, configura:

```env
GO2WIN_MODO_DESARROLLO=true
```

Usa `false` para desactivar el acceso sin contraseña. Si falta la opción, permanece desactivado. Una variable de entorno de PowerShell con el mismo nombre tiene prioridad sobre `.env`.

Reinicia Go2Win con este comando, desde la carpeta del proyecto:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Abre `http://localhost:8501`. El acceso de pruebas requiere que el servidor escuche exclusivamente en loopback; se bloquea en servidores enlazados a todas las interfaces y ante encabezados de proxy. No publiques este modo mediante túneles o proxies.

La pantalla mostrará **Modo de desarrollo: acceso sin contraseña** y un selector **Usuario de prueba** con cuentas web activas. Selecciona una y pulsa **Entrar sin contraseña**. Si ya tienes sesión abierta, ciérrala primero. Para probar otro rol, cierra sesión y selecciona otra cuenta. Las contraseñas, roles, equipos y alcances se conservan; el cambio obligatorio de contraseña temporal solo se omite durante la sesión de pruebas.

Las operaciones usan la base de datos actual: las asignaciones y reportes de prueba se guardan realmente. Al desactivar el modo o reiniciar el proceso, las sesiones de desarrollo dejan de ser válidas. El inicio de sesión con contraseña sigue disponible.

- **Cerrar sesión** revoca la sesión en la base y limpia el estado de la pantalla.
- **Cambiar mi contraseña**, en la barra lateral, requiere la contraseña actual y cierra las sesiones anteriores.
- Las sesiones vencen a las ocho horas. Recargar o cerrar el navegador puede requerir iniciar sesión nuevamente; no se implementó “recordarme”.
- Desactivar al usuario o cambiar su rol/equipo/supervisor revoca sus sesiones. Los alcances territoriales se vuelven a validar en cada operación.
- Después de cinco intentos fallidos, ese usuario de acceso queda bloqueado durante cinco minutos. El mensaje de error no revela si la cuenta existe.
- Se protege al último administrador con acceso web contra desactivación o cambio a otro rol. Crea un segundo administrador antes de retirar al primero.
- Las contraseñas se guardan con scrypt y sal aleatoria; los tokens de sesión se almacenan como hash. Nunca se guardan contraseñas en texto plano.

El despliegue sigue siendo local. Para acceso remoto, HTTPS debe proteger el envío de credenciales. El acceso directo al archivo SQLite o al sistema operativo está fuera del control de la pantalla de login.

Tablas nuevas: `web_accounts`, `web_sessions` y `web_login_attempts`. Se encuentran en `data/pulso_ciudadano_local.db`, junto a los datos actuales. Los respaldos anteriores a esta etapa no contienen las cuentas web.

Referencia para almacenamiento de contraseñas: [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).
