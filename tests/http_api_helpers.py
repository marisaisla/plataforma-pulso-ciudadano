"""Transporte HTTP de pruebas contra FastAPI, con SQLite temporal de los fixtures legacy."""
import sqlite3
from unittest.mock import patch
import requests
from fastapi.testclient import TestClient
from backend.main import app
from backend.admin import db
from backend.operations import UTC
from services import database


class Cursor:
    def __init__(self,cursor): self.cursor=cursor
    def fetchone(self):
        row=self.cursor.fetchone()
        return dict(row) if row is not None else None
    def fetchall(self): return [dict(row) for row in self.cursor.fetchall()]


class SQLiteAPI:
    def __init__(self,conn): self.conn=conn
    def execute(self,sql,params=()):
        if 'pg_advisory_xact_lock' in sql: sql='SELECT 1'
        sql=sql.replace('public.','').replace('%s','?').replace(UTC,'CURRENT_TIMESTAMP')
        return Cursor(self.conn.execute(sql,params))


def use_test_api(testcase):
    def dependency():
        conn=sqlite3.connect(database.DB_PATH,check_same_thread=False)
        conn.row_factory=sqlite3.Row
        try:
            with conn: yield SQLiteAPI(conn)
        finally: conn.close()
    old=app.dependency_overrides.get(db)
    app.dependency_overrides[db]=dependency
    def restore():
        if old is None: app.dependency_overrides.pop(db,None)
        else: app.dependency_overrides[db]=old
    testcase.addCleanup(restore)
    client=TestClient(app)
    testcase.addCleanup(client.close)
    def send(method,url,**kwargs):
        assert '/api/v1/' in url, 'Las pruebas no deben acceder a la red externa'
        path='/api/v1/'+url.split('/api/v1/',1)[1]
        response=client.request(method,path,headers=kwargs.get('headers'),json=kwargs.get('json'))
        result=requests.Response()
        result.status_code=response.status_code
        result._content=response.content
        result.headers.update(response.headers)
        return result
    transport=patch('services.profiles_api.requests.request',side_effect=send)
    transport.start()
    testcase.addCleanup(transport.stop)
