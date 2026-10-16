"""Servicios de interfaz para usuarios/Telegram/planes: solo HTTP, sin SQL."""
from urllib.parse import urlencode
import streamlit as st
from services.profiles_api import request,ProfileAPIError

APIError=ProfileAPIError


def call(method,path,payload=None,token=None,binary=False):
    return request(method,path,token if token is not None else st.session_state.get('_web_token',''),payload,binary=binary)


def require_admin():
    try:
        user=call('GET','/auth/me')
        if user['role_key']!='administrator' or user['must_change']:
            raise APIError('Necesitas una sesión de administrador con contraseña actualizada.')
        return user
    except APIError as exc:
        st.error(str(exc))
        st.stop()


def list_workers():
    result=[]
    after=0
    while True:
        page=call('GET',f'/users?after={after}&limit=100')
        result.extend(page)
        if len(page)<100: break
        after=page[-1]['id']
    return sorted(result,key=lambda w:(w['name'],w['id']))


def create_worker(name,team=''):
    return call('POST','/users',{'name':name,'team':team})['id']


def save_access(wid,role,team='',supervisor_id=None):
    return call('PUT',f'/users/{wid}/access',{'role_key':role,'team':team,'supervisor_id':supervisor_id})


def set_worker_active(wid,active): return call('PUT',f'/users/{wid}/active',{'active':bool(active)})
def list_scopes(wid): return call('GET',f'/users/{wid}/scopes')
def add_scope(wid,pid,state='',municipality=''): return call('POST',f'/users/{wid}/scopes',{'profile_id':pid,'state':state,'municipality':municipality})
def remove_scope(wid,pid,state='',municipality=''): return call('DELETE',f'/users/{wid}/scopes',{'profile_id':pid,'state':state,'municipality':municipality})
def issue_code(wid): return call('POST',f'/users/{wid}/telegram/activation-codes')['activation_code']
def unlink_worker(wid): return call('DELETE',f'/users/{wid}/telegram')
def set_account(token,wid,username,password): return call('PUT',f'/users/{wid}/account',{'username':username,'temporary_password':password},token=token)
def profile_list(): return call('GET','/profiles')
def profile_options(): return {f"{p['name']} (#{p['id']})":p['id'] for p in call('GET','/profiles?active_only=true')}
def profile_states(pid): return call('GET',f'/profiles/{pid}/states')
def territories(state=''): return call('GET','/territory-options?'+urlencode({'state':state}))
def roles(): return call('GET','/roles')
def strategies(pid,state): return call('GET','/action-strategies?'+urlencode({'profile_id':pid,'state':state}))
def activities(sid): return call('GET',f'/activities?strategy_id={sid}')
def create_activity(sid,body): return call('POST','/activities',dict(body,strategy_id=sid))
def update_activity(tid,status,note): return call('PATCH',f'/activities/{tid}',{'status':status,'evidence_note':note})
def get_assignment(tid): return call('GET',f'/activities/{tid}/assignment')
def eligible_workers(tid,token=None): return call('GET',f'/activities/{tid}/candidates',token=token)
def assign_task_locally(tid,wid,session_token=None): return call('PUT',f'/activities/{tid}/assignment',{'worker_id':wid},token=session_token)
def task_is_open(task): return task['status'] in ('Pendiente','En curso')
def list_task_reports(tid): return call('GET',f'/activities/{tid}/reports')
def report_photo(rid,token): return call('GET',f'/reports/{rid}/photo',token=token,binary=True)
def review_report(rid,decision,note,session_token=None): return call('PUT',f'/reports/{rid}/review',{'decision':decision,'note':note},token=session_token)
def supporter_catalog(token): return call('GET','/supporters',token=token)
def needs_catalog(token): return call('GET','/needs',token=token)
def portal_data(token):
    data=call('GET','/field/portal',token=token)
    return data['user'],data['tasks'],data['reports']
