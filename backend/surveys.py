"""Cuestionarios por actividad sobre PostgreSQL y sesiones Bearer."""
import json
import math
import secrets
from typing import Annotated, Literal
from urllib.parse import urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from backend.admin import db
from backend.operations import authenticated
from backend.permissions import allowed
from backend.telegram import serialize_changes
from backend.config import setting
from services.survey_rules import validate_definition

router = APIRouter(prefix='/api/v1', tags=['Cuestionarios de campo'])


def _task(conn, actor, task_id, permission='tasks.view'):
    user = actor
    task = conn.execute('''SELECT t.*, a.worker_id, a.generation AS assignment_generation
        FROM public.territorial_action_plans t LEFT JOIN public.field_task_assignments a ON a.task_id=t.id
        WHERE t.id=%s''', (task_id,)).fetchone()
    if task is None or not allowed(conn, user['id'], permission, task, task['worker_id']):
        raise HTTPException(403, 'No tienes acceso a esta actividad.')
    return user, dict(task)


def save_questionnaire(conn, actor, task_id, title, description, mode, questions, questionnaire_id=None, publish=False):
    title, description = title.strip(), description.strip()
    if not title or len(title) > 160 or len(description) > 2000 or mode not in {'single', 'multiple'}:
        raise HTTPException(422, 'Revisa el nombre (1–160 caracteres), descripción y modalidad.')
    try:
        definition = json.dumps(validate_definition(questions), ensure_ascii=False, allow_nan=False)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    serialize_changes(conn)
    user, task = _task(conn, actor, task_id, 'tasks.assign')
    if task['status'] not in {'Pendiente', 'En curso'}:
        raise HTTPException(422, 'La actividad debe estar pendiente o en curso.')
    status = 'published' if publish else 'draft'
    if questionnaire_id is not None:
        old = conn.execute('SELECT * FROM public.field_questionnaires WHERE id=%s AND task_id=%s',
                           (questionnaire_id, task_id)).fetchone()
        if old is None or old['status'] != 'draft':
            raise HTTPException(422, 'Solo puedes modificar borradores. Crea una nueva versión del cuestionario publicado.')
        conn.execute('UPDATE public.field_questionnaires SET title=%s, description=%s, mode=%s, definition=%s, status=%s WHERE id=%s',
                     (title, description, mode, definition, status, questionnaire_id))
        return questionnaire_id
    return conn.execute('''INSERT INTO public.field_questionnaires
        (task_id,title,description,mode,definition,status,created_by) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
                        (task_id, title, description, mode, definition, status, user['id'])).fetchone()['id']


def assign_questionnaire(conn, actor, task_id, questionnaire_id, target=1):
    if type(target) is not int or not 1 <= target <= 1000000:
        raise HTTPException(422, 'La meta debe estar entre 1 y 1,000,000 capturas.')
    serialize_changes(conn)
    _, task = _task(conn, actor, task_id, 'tasks.assign')
    if task['status'] not in {'Pendiente', 'En curso'}:
        raise HTTPException(422, 'La actividad debe estar abierta.')
    q = conn.execute('SELECT * FROM public.field_questionnaires WHERE id=%s', (questionnaire_id,)).fetchone()
    if q is None or q['status'] != 'published':
        raise HTTPException(422, 'Selecciona un cuestionario publicado.')
    _, source = _task(conn, actor, q['task_id'], 'tasks.assign')
    if source['profile_id'] != task['profile_id']:
        raise HTTPException(422, 'El cuestionario debe pertenecer a la misma campaña.')
    if q['mode'] == 'single' and target != 1:
        raise HTTPException(422, 'Una sola respuesta por actividad requiere meta de 1.')
    old = conn.execute('SELECT * FROM public.field_task_surveys WHERE task_id=%s', (task_id,)).fetchone()
    generation = old['generation'] if old and old['questionnaire_id'] == questionnaire_id else secrets.token_hex(16)
    conn.execute('''INSERT INTO public.field_task_surveys (task_id,questionnaire_id,generation,target) VALUES (%s,%s,%s,%s)
        ON CONFLICT(task_id) DO UPDATE SET questionnaire_id=excluded.questionnaire_id,
        generation=excluded.generation,target=excluded.target''', (task_id, questionnaire_id, generation, target))


def task_data(conn, actor, task_id):
    user, task = _task(conn, actor, task_id)
    assignment = conn.execute('''SELECT s.*, q.title,q.description,q.definition,q.mode FROM public.field_task_surveys s
        JOIN public.field_questionnaires q ON q.id=s.questionnaire_id WHERE s.task_id=%s''', (task_id,)).fetchone()
    templates = []
    manage = allowed(conn, user['id'], 'tasks.assign', task, task['worker_id'])
    task['can_capture'] = (task['worker_id'] == user['id'] and task['status'] in {'Pendiente', 'En curso'}
                           and allowed(conn, user['id'], 'reports.submit', task, user['id']))
    task['public_url_configured'] = bool(public_url())
    if manage:
        for q in conn.execute('''SELECT q.* FROM public.field_questionnaires q JOIN public.territorial_action_plans t ON t.id=q.task_id
            WHERE t.profile_id=%s ORDER BY q.id DESC''', (task['profile_id'],)).fetchall():
            try:
                _task(conn, actor, q['task_id'], 'tasks.assign')
                templates.append(dict(q))
            except HTTPException:
                continue
    return task, dict(assignment) if assignment else None, templates, manage


def _capture(conn, actor, task_id, assignment_generation, survey_generation):
    user, task = _task(conn, actor, task_id, 'reports.submit')
    survey = conn.execute('''SELECT s.*, q.title,q.description,q.definition,q.mode FROM public.field_task_surveys s
        JOIN public.field_questionnaires q ON q.id=s.questionnaire_id WHERE s.task_id=%s''', (task_id,)).fetchone()
    if (user['id'] != task['worker_id'] or task['status'] not in {'Pendiente', 'En curso'} or survey is None
            or task['assignment_generation'] != assignment_generation or survey['generation'] != survey_generation):
        raise HTTPException(403, 'El cuestionario ya no está disponible para esta asignación. Abre de nuevo la actividad.')
    return user, task, dict(survey)


def capture_data(conn, actor, task_id, assignment_generation, survey_generation):
    _, task, survey = _capture(conn, actor, task_id, assignment_generation, survey_generation)
    return task, survey


def submit_response(conn, actor, task_id, assignment_generation, survey_generation, submission_key, answers):
    if not isinstance(submission_key, str) or not 16 <= len(submission_key) <= 128 or not isinstance(answers, dict):
        raise HTTPException(422, 'Identificador de envío o respuestas inválidos.')
    serialize_changes(conn)
    user, task, survey = _capture(conn, actor, task_id, assignment_generation, survey_generation)
    previous = conn.execute('SELECT * FROM public.field_survey_responses WHERE submission_key=%s', (submission_key,)).fetchone()
    if previous:
        if (previous['worker_id'] != user['id'] or previous['task_id'] != task_id
                or previous['assignment_generation'] != assignment_generation or previous['survey_generation'] != survey_generation):
            raise HTTPException(422, 'El identificador de envío ya está en uso.')
        return previous['id']
    if survey['mode'] == 'single' and conn.execute(
            'SELECT 1 FROM public.field_survey_responses WHERE task_id=%s AND questionnaire_id=%s',
            (task_id, survey['questionnaire_id'])).fetchone():
        raise HTTPException(422, 'Esta actividad ya tiene una respuesta para este cuestionario.')
    clean = {}
    questions = json.loads(survey['definition'])
    if set(answers) - {q['id'] for q in questions}:
        raise HTTPException(422, 'Hay respuestas para preguntas desconocidas.')
    for q in questions:
        value = answers.get(q['id'])
        if isinstance(value, str):
            value = value.strip()
        if value is None or value == '':
            if q['required']:
                raise HTTPException(422, f"Responde: {q['label']}")
            clean[q['id']] = None
            continue
        if q['type'] == 'number':
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise HTTPException(422, f"Escribe un número válido: {q['label']}")
            if (q['min'] is not None and value < q['min']) or (q['max'] is not None and value > q['max']):
                raise HTTPException(422, f"Número fuera del rango permitido: {q['label']}")
        elif not isinstance(value, str) or len(value) > 3000:
            raise HTTPException(422, f"Texto inválido o demasiado largo: {q['label']}")
        elif q['type'] == 'choice' and value not in q['options']:
            raise HTTPException(422, f"Selecciona una opción válida: {q['label']}")
        clean[q['id']] = value
    return conn.execute('''INSERT INTO public.field_survey_responses
        (task_id,questionnaire_id,worker_id,assignment_generation,survey_generation,submission_key,answers,
         profile_id,state,municipality) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
        (task_id, survey['questionnaire_id'], user['id'], assignment_generation, survey_generation, submission_key,
         json.dumps(clean, ensure_ascii=False, allow_nan=False), task['profile_id'], task['state'], task['municipality'])).fetchone()['id']


def results(conn, actor, task_id):
    user, task = _task(conn, actor, task_id)
    rows = [dict(r) for r in conn.execute('SELECT * FROM public.field_survey_responses WHERE task_id=%s ORDER BY id DESC', (task_id,)).fetchall()
            if allowed(conn, user['id'], 'reports.view', r, r['worker_id'])]
    groups = []
    ids = {r['questionnaire_id'] for r in rows}
    active = conn.execute('SELECT * FROM public.field_task_surveys WHERE task_id=%s', (task_id,)).fetchone()
    if active:
        ids.add(active['questionnaire_id'])
    for qid in sorted(ids):
        q = conn.execute('SELECT * FROM public.field_questionnaires WHERE id=%s', (qid,)).fetchone()
        selected = [r for r in rows if r['questionnaire_id'] == qid]
        answers = [json.loads(r['answers']) for r in selected]
        metrics = [{'Indicador': 'Cuestionarios enviados', 'Valor': len(answers)}]
        if active and active['questionnaire_id'] == qid:
            metrics.append({'Indicador': 'Avance de la meta (%)', 'Valor': 100 * len(answers) / active['target']})
        for question in json.loads(q['definition']):
            values = [a[question['id']] for a in answers if a.get(question['id']) is not None]
            kind = question['metric']
            if kind == 'none':
                continue
            value = len(values) if kind == 'count' else (sum(values) if kind == 'sum' else sum(values)/len(values)) if values else None
            metrics.append({'Indicador': question['metric_label'], 'Valor': value})
        groups.append(dict(id=qid, title=q['title'], metrics=metrics, responses=selected, questions=json.loads(q['definition'])))
    return groups


def public_url():
    try:
        parsed = urlsplit(setting('GO2WIN_PUBLIC_URL').strip())
        if parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password:
            return parsed
    except ValueError:
        pass
    return None


def questionnaire_button(conn, telegram_user_id, task):
    base = public_url()
    if base is None:
        return None
    from backend.tasks import identity
    worker_id, _ = identity(conn, telegram_user_id)
    if not allowed(conn, worker_id, 'reports.submit', task, worker_id):
        return None
    survey = conn.execute('SELECT generation FROM public.field_task_surveys WHERE task_id=%s', (task['id'],)).fetchone()
    if survey is None:
        return None
    query = urlencode(dict(field_survey=task['id'], assignment=task['generation'], survey=survey['generation']))
    return {'text': f"Responder cuestionario #{task['id']}",
            'url': urlunsplit((base.scheme, base.netloc, base.path, query, ''))}


Identifier = Annotated[int, Path(gt=0, le=2**63-1)]
PositiveId = Annotated[int, Field(strict=True, gt=0, le=2**63-1)]
Generation = Annotated[str, Field(min_length=1, max_length=128)]


class Question(BaseModel):
    model_config = ConfigDict(extra='forbid')
    label: str = Field(min_length=1, max_length=300)
    type: Literal['text', 'number', 'choice']
    required: StrictBool = False
    options: list[Annotated[str, Field(max_length=150)]] = Field(default_factory=list, max_length=30)
    min: float | None = Field(default=None, strict=True, allow_inf_nan=False)
    max: float | None = Field(default=None, strict=True, allow_inf_nan=False)
    metric: Literal['none', 'count', 'sum', 'average'] = 'none'
    metric_label: str = Field(default='', max_length=120)


class QuestionnaireWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default='', max_length=2000)
    mode: Literal['single', 'multiple']
    questions: list[Question] = Field(min_length=1, max_length=30)
    publish: StrictBool = False


class SurveyAssignment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    questionnaire_id: PositiveId
    target: int = Field(default=1, strict=True, ge=1, le=1000000)


class ResponseWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    assignment_generation: Generation
    survey_generation: Generation
    submission_key: str = Field(min_length=16, max_length=128)
    answers: dict[str, str | int | float | bool | None] = Field(max_length=30)


@router.get('/activities/{tid}/questionnaires')
def questionnaire_context(tid: Identifier, actor=Depends(authenticated), conn=Depends(db)):
    task, survey, templates, manage = task_data(conn, actor, tid)
    return dict(task=task, assignment=survey, questionnaires=templates, can_manage=manage)


@router.post('/activities/{tid}/questionnaires', status_code=201)
def create_questionnaire(tid: Identifier, body: QuestionnaireWrite, actor=Depends(authenticated), conn=Depends(db)):
    return {'id': save_questionnaire(conn, actor, tid, body.title, body.description, body.mode,
                                    [q.model_dump() for q in body.questions], publish=body.publish)}


@router.put('/activities/{tid}/questionnaires/{qid}')
def update_questionnaire(tid: Identifier, qid: Identifier, body: QuestionnaireWrite,
                         actor=Depends(authenticated), conn=Depends(db)):
    return {'id': save_questionnaire(conn, actor, tid, body.title, body.description, body.mode,
                                    [q.model_dump() for q in body.questions], qid, body.publish)}


@router.put('/activities/{tid}/questionnaire', status_code=204)
def set_questionnaire(tid: Identifier, body: SurveyAssignment, actor=Depends(authenticated), conn=Depends(db)):
    assign_questionnaire(conn, actor, tid, body.questionnaire_id, body.target)


@router.get('/activities/{tid}/questionnaire/capture')
def get_capture(tid: Identifier, assignment: Annotated[str, Query(min_length=1, max_length=128)],
                survey: Annotated[str, Query(min_length=1, max_length=128)],
                actor=Depends(authenticated), conn=Depends(db)):
    task, questionnaire = capture_data(conn, actor, tid, assignment, survey)
    return dict(task=task, questionnaire=questionnaire)


@router.post('/activities/{tid}/questionnaire/responses')
def create_response(tid: Identifier, body: ResponseWrite, actor=Depends(authenticated), conn=Depends(db)):
    rid = submit_response(conn, actor, tid, body.assignment_generation, body.survey_generation,
                          body.submission_key, body.answers)
    return {'id': rid, 'folio': f'ENC-{rid:06d}'}


@router.get('/activities/{tid}/questionnaire/results')
def questionnaire_results(tid: Identifier, actor=Depends(authenticated), conn=Depends(db)):
    return results(conn, actor, tid)
