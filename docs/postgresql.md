# Go2Win con PostgreSQL

La aplicación, los servicios de usuarios/tareas/reportes, el integrador Telegram
y los importadores operativos usan la conexión central de `services/database.py`.
`DB_BACKEND=postgresql` utiliza la base migrada `go2win_desarrollo`; un fallo de
conexión detiene la operación y **no cambia automáticamente a SQLite**.

## Configurar cada computadora

Para los reportes con fotografía, el administrador debe aplicar primero
`scripts/agregar_evidencias_postgresql.sql` y
`scripts/agregar_simpatizantes_postgresql.sql` en la base compartida y después
reiniciar Go2Win y el integrador. Las evidencias se almacenan en la base y
se incluyen en sus respaldos. Consulta `TELEGRAM_INTEGRADOR.md`.

Instalar las dependencias del proyecto:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Completar el `.env` privado siguiendo `.env.example`. En MARISA, usar
`PGHOST=localhost` y `PGUSER=go2win_marisa`. En la computadora de Jorge,
usar `PGHOST=192.168.1.10` y `PGUSER=go2win_jorge`. Ambas usan
`PGPORT=5432` y `PGDATABASE=go2win_desarrollo`, cada una con su contraseña.
Las variables del entorno tienen prioridad sobre el archivo `.env`.
Reiniciar Streamlit y el integrador tras cambiar la configuración.

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

El modo de desarrollo sigue controlado por `GO2WIN_MODO_DESARROLLO` y requiere
acceso web local. Compartir la base no habilita ese modo en la otra computadora.
Las cuentas PostgreSQL son distintas de las cuentas de acceso a Go2Win.

Ejecutar **un solo receptor** Telegram entre ambas computadoras:

```powershell
.\.venv\Scripts\python.exe scripts\integrador_telegram.py
```

## Validación sin conservar datos de prueba

```powershell
.\.venv\Scripts\python.exe scripts\validar_postgresql.py --flujos
```

Comprueba el esquema, analiza consultas estáticas con EXPLAIN sin ejecutarlas,
verifica INSERT/UPDATE/DELETE en una fila de identificador explícito con rollback,
y prueba los servicios con tablas temporales de sesión y sus restricciones.
Al terminar revierte la transacción. No deja usuarios, tareas ni reportes de prueba,
no cambia las secuencias públicas y no envía mensajes a Telegram. Estas pruebas
no sustituyen la revisión visual de cada pantalla ni la conexión desde Jorge.

Pruebas unitarias existentes, en archivos SQLite temporales independientes:

```powershell
$env:DB_BACKEND='sqlite'
.\.venv\Scripts\python.exe -m unittest discover -s tests
Remove-Item Env:DB_BACKEND
```

## Esquema, archivos y mantenimiento

El arranque valida las 61 tablas migradas y sus columnas mediante
`services/postgres_schema.json`. No importa datos ni ejecuta migraciones SQLite
en PostgreSQL. Los cambios futuros de esquema requieren una migración explícita;
actualizar el contrato de columnas después de aplicarla.

Las operaciones críticas de permisos, asignación y recepción se serializan con
un bloqueo transaccional compartido entre procesos Go2Win. PostgreSQL conserva
las fechas de v3 como texto UTC y las banderas como enteros.

Los importadores operativos ahora escriben en la base seleccionada en `.env`;
algunos reemplazan datos territoriales. Ejecutarlos solo cuando se desee esa carga.
`exportar_postgresql.py` y `merge_transferred_database.py` siguen siendo utilidades
explícitas para archivos SQLite, no conexiones de la aplicación.

La base SQLite original se conserva. Cambiar `DB_BACKEND=sqlite` vuelve a ese
archivo local, pero **no sincroniza** los cambios hechos en PostgreSQL.

Los PDF, mapas y otros archivos del disco no se transfieren con PostgreSQL.
Ambas computadoras necesitan acceso a los archivos usados por la aplicación.
El servidor MARISA debe permanecer encendido y accesible desde la red autorizada.
