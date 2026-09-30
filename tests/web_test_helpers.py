from services import web_auth


def admin_session():
    web_auth.initialize_auth()
    web_auth.bootstrap_admin('ZZ administrador pruebas', 'admin.test', 'Clave ficticia para pruebas 123')
    return web_auth.login('admin.test', 'Clave ficticia para pruebas 123')
