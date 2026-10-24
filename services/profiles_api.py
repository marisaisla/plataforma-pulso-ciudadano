"""Cliente HTTP de la pantalla 01. No accede a la base de datos."""
import requests
from services.settings import get_setting


class ProfileAPIError(ValueError):
    def __init__(self,message,status_code=None):
        super().__init__(message)
        self.status_code=status_code


def request(method,path,token,payload=None,binary=False,timeout=15):
    base=(get_setting('API_BASE_URL') or 'http://127.0.0.1:8000').rstrip('/')
    try:
        response=requests.request(method,base+'/api/v1'+path,
                                  headers={'Authorization':'Bearer '+token},json=payload,timeout=timeout,
                                  allow_redirects=False)
    except requests.RequestException:
        raise ProfileAPIError('No se pudo conectar con la API. Comprueba que FastAPI esté encendido.') from None
    if response.status_code==401:
        raise ProfileAPIError('La API no reconoce tu sesión. Cierra sesión y entra con usuario y contraseña; el acceso de desarrollo sin contraseña no es compatible.',401)
    if response.status_code==403:
        raise ProfileAPIError('La API rechazó el acceso. Revisa tu rol, territorio y si debes cambiar la contraseña temporal.',403)
    if response.status_code==503:
        raise ProfileAPIError('La API no pudo acceder a PostgreSQL. Inténtalo nuevamente cuando se restablezca la conexión.',503)
    if not response.ok:
        try: detail=response.json().get('detail')
        except ValueError: detail=None
        if isinstance(detail,list): detail=' '.join(str(e.get('msg','Entrada inválida.')) for e in detail)
        raise ProfileAPIError(detail if isinstance(detail,str) else f'La API rechazó la operación (HTTP {response.status_code}).',response.status_code)
    if response.status_code==204: return None
    if binary: return response.content
    try: return response.json()
    except ValueError: raise ProfileAPIError('La API devolvió una respuesta inválida.') from None
