"""Cliente HTTP de cuestionarios. No abre conexiones a bases de datos."""
from urllib.parse import urlencode

from services.field_api import call, APIError
from services.survey_rules import validate_definition


def save_questionnaire(token, task_id, title, description, mode, questions, questionnaire_id=None, publish=False):
    payload = dict(title=title, description=description, mode=mode, questions=questions, publish=publish)
    path = f'/activities/{task_id}/questionnaires'
    if questionnaire_id is not None:
        return call('PUT', path + f'/{questionnaire_id}', payload, token=token)['id']
    return call('POST', path, payload, token=token)['id']


def assign_questionnaire(token, task_id, questionnaire_id, target=1):
    return call('PUT', f'/activities/{task_id}/questionnaire',
                dict(questionnaire_id=questionnaire_id, target=target), token=token)


def task_data(token, task_id):
    data = call('GET', f'/activities/{task_id}/questionnaires', token=token)
    return data['task'], data['assignment'], data['questionnaires'], data['can_manage']


def capture_data(token, task_id, assignment_generation, survey_generation):
    query = urlencode(dict(assignment=assignment_generation, survey=survey_generation))
    data = call('GET', f'/activities/{task_id}/questionnaire/capture?' + query, token=token)
    return data['task'], data['questionnaire']


def submit_response(token, task_id, assignment_generation, survey_generation, submission_key, answers):
    return call('POST', f'/activities/{task_id}/questionnaire/responses',
                dict(assignment_generation=assignment_generation, survey_generation=survey_generation,
                     submission_key=submission_key, answers=answers), token=token)['id']


def results(token, task_id):
    return call('GET', f'/activities/{task_id}/questionnaire/results', token=token)
