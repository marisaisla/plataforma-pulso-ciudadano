# Roles y permisos del personal

Go2Win incorpora un rol por trabajador, un equipo, un supervisor opcional y alcances por perfil/campaña, estado y municipio. La cuenta de Telegram vinculada se conserva. Los usuarios existentes y nuevos comienzan como **Personal de campo**. Nadie recibe acceso a campañas por su nombre o por pertenecer a un equipo.

## Roles disponibles

| Rol | Permisos definidos para la integración de campo |
| --- | --- |
| Personal de campo | Consultar sus tareas y reportes, confirmar recepción, enviar avances, evidencias e incidencias. |
| Supervisor | Además de sus acciones propias, consultar y validar reportes y atender incidencias del personal de campo asignado directamente a su cargo. |
| Coordinador | Además de sus acciones propias, asignar tareas, consultar y validar reportes y atender incidencias del personal y supervisores de su equipo. |
| Director de campaña | Consultar tareas y resultados y definir prioridades dentro de sus campañas y territorios autorizados. No administra usuarios. |
| Administrador | Todos los permisos, incluida administración de usuarios, roles y configuración, con alcance global. |

Los supervisores y coordinadores requieren el mismo equipo que el responsable de la tarea y alcances compatibles con la campaña y territorio de la tarea. No validan sus propios reportes. Un coordinador no administra tareas de otro coordinador, director o administrador por compartir equipo. El rol de administrador tiene acceso global explícito.

## Configurar un usuario

1. Abre **Configuración y apoyo → Personal y Telegram**.
2. Selecciona el trabajador. En **Rol y equipo**, elige el rol y equipo; opcionalmente asigna un supervisor o coordinador activo del mismo equipo. Pulsa **Guardar rol y equipo**.
3. En **Campañas y territorios autorizados**, selecciona el perfil/campaña, estado y municipio y pulsa **Agregar alcance**.
4. Para autorizar una campaña completa, selecciona todos los estados y municipios. Para limitarla, selecciona el territorio específico. Puedes agregar varios alcances.
5. Para reducir acceso, retira los alcances generales que incluyan el territorio que quieres excluir. Los alcances se suman; uno específico no restringe a otro más amplio.

Sin alcance asignado, un usuario distinto de administrador no tiene autorización operativa para tareas. Desactivar el usuario bloquea todos sus permisos. Los cambios se consultan en la base en cada validación; no dependen de reiniciar su sesión.

Los cambios de rol, equipo, supervisor, alcance, activación y desvinculación quedan registrados en una bitácora local. Esta etapa atribuye los cambios a `local_console`, no a un administrador identificado.

## Consultar desde Telegram

`needs.submit` permite a campo registrar necesidades territoriales con `/necesidad`.
`needs.view` permite a campo consultar sus registros y a coordinadores y directores
consultar todos los registros de su campaña y territorio autorizado. Administración
dispone de ambos permisos para toda la operación. No se exige el mismo equipo
entre el autor y el coordinador para esta consulta territorial.

El catálogo de simpatizantes incorpora `supporters.submit` (campo, supervisor,
coordinador y administrador) y `supporters.view`. Campo consulta sus registros;
supervisor y coordinador consultan su equipo con alcance autorizado; director
consulta su campaña y territorio; administrador consulta toda la operación.
El bot usa `/simpatizante` para la captura y conserva por separado la autorización
para registrar datos y para recibir información. Consulta `TELEGRAM_INTEGRADOR.md`.

Reinicia `scripts/integrador_telegram.py` para cargar la nueva versión y envía `/mi_perfil` en el chat privado del bot. Muestra el rol, equipo, alcances y permisos del usuario vinculado. Puedes escribir el comando aunque no esté en el menú de BotFather. `/ayuda` también lo menciona.

## Alcance de la implementación

El catálogo, las asignaciones y la función central de autorización ya están implementados. `/mis_tareas`, `/tarea FOLIO` y los botones de recepción consultan la asignación real y validan al usuario activo, su permiso y territorio antes de mostrar o guardar información. `/reportar` valida además la recepción de la tarea antes de guardar el texto. `/mis_reportes` permite consultar los reportes propios y sus revisiones dentro del alcance autorizado. `/mis_tareas` presenta solo las actividades propias, incluso para roles con acceso más amplio. Las fotografías siguen pendientes. La asignación y revisión desde el panel siguen siendo operaciones de la consola local de confianza.

El panel Streamlit ahora requiere **inicio de sesión**. Las pantallas generales, incluido Planes de acción, están restringidas a administradores. Los demás roles acceden a un panel operativo filtrado por identidad y alcance. Las revisiones y reasignaciones vuelven a comprobar permisos al guardar. El primer administrador se crea mediante una herramienta local, sin modificar al personal existente. Consulta [Inicio de sesión](INICIO_DE_SESION.md).

## Datos y validación

La base sigue siendo `data/pulso_ciudadano_local.db`:

- `field_workers`: incorpora `role_key` y `supervisor_id`, además del equipo y vínculo existentes.
- `field_roles`, `field_permissions`, `field_role_permissions`: catálogo de cinco roles y sus permisos.
- `field_worker_scopes`: campañas y territorios autorizados.
- `field_access_audit`: historial de cambios administrativos.

`services/field_permissions.py` contiene `can_access` y `require_access`. Reciben la identidad validada del trabajador y el contexto real de la tarea, obtenido por el backend. No deben recibir una identidad elegida por el cliente. Los permisos desconocidos, usuarios inactivos y alcances insuficientes se rechazan.

Pruebas sobre bases temporales:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_field*.py" -v
```
