from typing import Annotated, Literal
import secrets

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Path, Query, Security
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field, StrictBool, ConfigDict

from backend.config import setting
from backend.database import connect
from backend.telegram import issue_code, process_message, process_callback

app = FastAPI(title='Go2Win API', version='0.14.0', description='API de Go2Win: perfiles, usuarios, operación Telegram, Planes de acción y cuestionarios de campo con indicadores. Las pantallas consultan y guardan vía HTTP; PostgreSQL y los permisos se administran en el backend.')
admin_header = APIKeyHeader(name='X-API-Key', auto_error=False)
telegram_header = APIKeyHeader(name='X-Telegram-Bot-Api-Secret-Token', auto_error=False)


def check_secret(value, key):
    expected = setting(key)
    if not expected:
        raise HTTPException(503, 'Falta configurar el secreto de este endpoint.')
    if not value or not secrets.compare_digest(value.encode(), expected.encode()):
        raise HTTPException(401, 'Credencial inválida.')


def admin_auth(value=Security(admin_header)):
    check_secret(value, 'API_ADMIN_KEY')


def telegram_auth(value=Security(telegram_header)):
    check_secret(value, 'TELEGRAM_WEBHOOK_SECRET')


def database():
    with connect() as conn:
        yield conn


@app.exception_handler(psycopg.Error)
@app.exception_handler(RuntimeError)
async def database_error(request, exc):
    return JSONResponse(status_code=503, content={'detail': 'PostgreSQL no disponible o esquema incompatible.'})


TelegramId = Annotated[int, Field(strict=True, gt=0, le=2**52-1)]


class Sender(BaseModel):
    id: TelegramId
    is_bot: StrictBool


class Chat(BaseModel):
    id: Annotated[int, Field(strict=True, ge=-(2**52-1), le=2**52-1)]
    type: Literal['private', 'group', 'supergroup', 'channel']


class Photo(BaseModel):
    file_id: str = Field(min_length=1, max_length=1024)
    file_unique_id: str = Field(min_length=1, max_length=1024)
    width: Annotated[int, Field(strict=True, gt=0)]
    height: Annotated[int, Field(strict=True, gt=0)]
    file_size: Annotated[int, Field(strict=True, ge=0)] | None = None


class Message(BaseModel):
    model_config = ConfigDict(extra='allow')
    message_id: Annotated[int, Field(strict=True, ge=0)]
    sender: Sender = Field(alias='from')
    chat: Chat
    text: str | None = Field(default=None, max_length=4096)
    date: Annotated[int, Field(strict=True, ge=0)] | None = None
    photo: list[Photo] | None = Field(default=None, max_length=20)
    caption: str | None = Field(default=None, max_length=4096)
    media_group_id: str | None = None


class Callback(BaseModel):
    id: str
    sender: Sender = Field(alias='from')
    message: Message | None = None
    data: str = Field(default='', max_length=64)


class Update(BaseModel):
    model_config = ConfigDict(json_schema_extra={'examples': [
        {'update_id': 20001, 'message': {'message_id': 100, 'date': 1791800000,
         'from': {'id': 123456789, 'is_bot': False}, 'chat': {'id': 123456789, 'type': 'private'}, 'text': '/reportar'}},
        {'update_id': 20002, 'callback_query': {'id': 'seleccion-unica-1',
         'from': {'id': 123456789, 'is_bot': False}, 'message': {'message_id': 101,
         'from': {'id': 999, 'is_bot': True}, 'chat': {'id': 123456789, 'type': 'private'}},
         'data': 'reportselect:1:GENERATION'}},
        {'update_id': 20003, 'message': {'message_id': 102, 'date': 1791800001,
         'from': {'id': 123456789, 'is_bot': False}, 'chat': {'id': 123456789, 'type': 'private'}, 'text': 'Avance de la actividad.'}}
    ]})
    update_id: Annotated[int, Field(strict=True, ge=0)]
    message: Message | None = None
    callback_query: Callback | None = None


class UpdateResult(BaseModel):
    update_id: int
    status: Literal['ignored', 'unsupported', 'rejected', 'already_linked', 'linked', 'tasks', 'received', 'reports', 'supporters', 'needs', 'profile', 'help']
    reply: str | None
    reply_markup: dict | None = None


class CodeResult(BaseModel):
    worker_id: int
    activation_code: str
    command: str
    expires_at: int


@app.get('/api/v1/health')
def health():
    return {'status': 'ok'}


@app.get('/api/v1/health/database', dependencies=[Depends(admin_auth)])
def database_health(conn=Depends(database)):
    conn.execute('SELECT id, active, telegram_user_id, telegram_chat_id, linked_at FROM public.field_workers LIMIT 0')
    conn.execute('SELECT code_hash, worker_id, expires_at, consumed_at FROM public.field_activation_codes LIMIT 0')
    return {'status': 'ok', 'backend': 'postgresql'}


@app.post('/api/v1/workers/{worker_id}/telegram/activation-codes',
          response_model=CodeResult, status_code=201, dependencies=[Depends(admin_auth)])
def activation_code(worker_id: Annotated[int, Path(gt=0)], conn=Depends(database)):
    return issue_code(conn, worker_id)


@app.post('/api/v1/integrations/telegram/updates', response_model=UpdateResult,
          response_model_exclude_none=True,
          summary='Procesar comandos y botones de Telegram',
          dependencies=[Depends(telegram_auth)])
def telegram_update(update: Update, conn=Depends(database)):
    """Procesa un evento del receptor confiable de Telegram o una simulación de Postman.

    **Comandos:** `/start CODIGO`, `/perfil`, `/mi_perfil`, `/mis_tareas`, `/tarea FOLIO`, `/reportar`, `/incidencia`, `/simpatizante`, `/necesidad` y `/cancelar`.

    **Incidencias:** `/incidencia` muestra tareas recibidas disponibles con permiso
    incidents.submit. Selección `incidentselect:FOLIO:GENERATION`, paginación
    `incidentpage:ULTIMO_FOLIO`. Captura de 30 minutos, texto o una foto con descripción.
    Guarda en field_reports con prefijo [INCIDENCIA], estado pending y folio R-...;
    máximo 3987 caracteres de descripción para incluir el prefijo en el límite de 4000.
    Estado de respuesta reports. Validar el registro no significa resolver el problema.

    **Perfil:** `/perfil` y `/mi_perfil` son equivalentes. Consultan rol, equipo,
    campañas, territorios y permisos vigentes de la identidad Telegram vinculada.
    Devuelven status=profile; no eliminan, renuevan ni guardan capturas pendientes.
    Identidad no vinculada o inactiva devuelve status=rejected.

    **Ayuda:** `/ayuda` devuelve status=help con los comandos autorizados por los
    permisos vigentes del rol y la captura activa con su tiempo restante.
    No modifica ni renueva capturas. No vinculados reciben orientación /start CODIGO;
    inactivos reciben orientación a coordinación. Comandos desconocidos muestran la ayuda.

    **Historial de reportes:** `/mis_reportes` muestra reportes propios con estado y
    observaciones de revisión, filtrados por permiso reports.view y territorio vigente.
    `reporthistory:ULTIMO_FOLIO` pagina el historial. Conserva capturas pendientes.
    `/evidencia` orienta al flujo de /reportar, sin abrir otra captura.

    **Necesidades:** `/necesidad` muestra campañas autorizadas; seleccionar con
    `needcampaign:FOLIO` o `/necesidad FOLIO_CAMPAÑA`. Enviar Estado, Municipio,
    Sección positiva de hasta 6 dígitos, Origen: detectada/comentada y Necesidad al final
    (hasta 3000 caracteres, admite varias líneas). Captura por 30 minutos, folio N-...,
    permiso needs.submit y alcance territorial; no requiere tarea ni recepción.

    **Simpatizantes:** `/simpatizante` muestra campañas autorizadas. Elegir con callback
    `supportcampaign:FOLIO` o `/simpatizante FOLIO_CAMPAÑA`, luego enviar un texto con
    Nombre, Teléfono, Estado, Municipio, Sección opcional, Clave de elector, Registro: SI
    y Mensajes: SI o NO, un campo por línea separado por dos puntos. Captura de 30 minutos,
    máximo 2000 caracteres, folio S-..., permiso supporters.submit y alcance territorial.
    No se envían mensajes al simpatizante ni se verifica la identidad ante el INE.

    **Confirmación:** callback `taskconfirm:FOLIO:GENERATION`. Guarda recepción sin concluir la tarea.

    **Reportar texto:**
    1. Enviar un `message` con `text=/reportar`: devuelve tareas recibidas y botones en `reply_markup`.
    2. Enviar `callback_query` con `data=reportselect:FOLIO:GENERATION`: abre captura por 30 minutos.
    3. Enviar un nuevo `message` con el avance (1–4000 caracteres) y `date` Unix actual:
       guarda el reporte por validar y devuelve un folio `R-...`.
    4. `/cancelar` descarta la captura. `reportpage:ULTIMO_FOLIO` pagina el menú.

    Sustituir los IDs, GENERATION y fechas de los ejemplos por valores reales.
    Se revalidan usuario activo, asignación, recepción, permisos y alcance al guardar.
    Repetir el mismo chat/mensaje no duplica el reporte. No cambia el estado de la tarea.
    Alternativamente enviar `photo` (tamaños de Telegram) y `caption` con el avance.
    Se admite una fotografía JPEG por reporte: hasta 10 MB y 25 millones de píxeles;
    no álbumes ni documentos. API descarga mediante getFile y guarda imagen/reporte
    juntos en PostgreSQL. Fallos transitorios devuelven 503 para reintentar.

    Requiere `X-Telegram-Bot-Api-Secret-Token`. Devuelve `status`, `reply` y, cuando aplica,
    `reply_markup`. Los rechazos de negocio llegan con HTTP 200 y su explicación;
    autenticación inválida: 401; estructura inválida: 422; fallo de PostgreSQL: 503.
    La API devuelve JSON; el receptor polling envía el texto y botones a Telegram.
    """
    result = process_callback(conn, update.callback_query) if update.callback_query else process_message(conn, update.message) if update.message else {'status': 'ignored', 'reply': None}
    return {'update_id': update.update_id, **result}


class TaskResult(BaseModel):
    id: int
    profile_id: int
    activity_name: str
    activity_description: str | None
    state: str | None
    municipality: str | None
    due_date: str | None
    status: str
    received_at: str | None
    generation: str


class TaskPage(BaseModel):
    items: list[TaskResult]
    next_after: int | None


@app.get('/api/v1/integrations/telegram/users/{telegram_user_id}/tasks',
         response_model=TaskPage, dependencies=[Depends(telegram_auth)])
def assigned_tasks(telegram_user_id: Annotated[int, Path(gt=0, le=2**52-1)],
                   after: Annotated[int, Query(ge=0, le=2**63-1)]=0,
                   limit: Annotated[int, Query(ge=1, le=50)]=3, conn=Depends(database)):
    from backend.tasks import list_tasks
    from backend.telegram import serialize_changes
    serialize_changes(conn)
    return list_tasks(conn, telegram_user_id, after, limit)


@app.get('/api/v1/integrations/telegram/users/{telegram_user_id}/tasks/{task_id}',
         response_model=TaskResult, dependencies=[Depends(telegram_auth)])
def assigned_task(telegram_user_id: Annotated[int, Path(gt=0, le=2**52-1)],
                  task_id: Annotated[int, Path(gt=0, le=2**63-1)], conn=Depends(database)):
    from backend.tasks import get_task
    from backend.telegram import serialize_changes
    serialize_changes(conn)
    return get_task(conn, telegram_user_id, task_id)


from backend.admin import router as admin_router
app.include_router(admin_router)
from backend.profiles import router as profiles_router
app.include_router(profiles_router)
from backend.operations import router as operations_router
app.include_router(operations_router)
from backend.surveys import router as surveys_router
app.include_router(surveys_router)


@app.exception_handler(RequestValidationError)
async def validation_error(request,exc):
    # No devolver contraseñas u otros datos de entrada en errores de validación.
    return JSONResponse(status_code=422,content={'detail':[{'loc':list(e['loc']),'msg':e['msg'],'type':e['type']} for e in exc.errors()]})
