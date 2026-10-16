"""Transporte Telegram → HTTP FastAPI. Ejecutar desde la raíz con -m."""
import time
import httpx

from backend.config import setting


class TransportError(Exception):
    def __init__(self, message, fatal=False, retry_after=5):
        super().__init__(message)
        self.fatal = fatal
        self.retry_after = retry_after


def telegram_call(client, token, method, **payload):
    try:
        response = client.post(f'https://api.telegram.org/bot{token}/{method}', json=payload)
        data = response.json()
    except (httpx.HTTPError, ValueError):
        raise TransportError('No se pudo comunicar con Telegram.') from None
    if not response.is_success or not data.get('ok'):
        code = data.get('error_code', response.status_code)
        if code == 409:
            raise TransportError('Telegram detectó otro receptor o un webhook activo.', fatal=True)
        raise TransportError(f'Telegram rechazó {method} (código {code}).',
                             fatal=code in (400, 401, 403),
                             retry_after=data.get('parameters', {}).get('retry_after', 5))
    return data['result']


def process_update(client, token, base_url, secret, update):
    try:
        response = client.post(base_url + '/api/v1/integrations/telegram/updates',
                               headers={'X-Telegram-Bot-Api-Secret-Token': secret}, json=update)
    except httpx.HTTPError:
        raise TransportError('FastAPI no está disponible; el evento no se confirmó.') from None
    if not response.is_success:
        raise TransportError(f'FastAPI rechazó el evento (HTTP {response.status_code}).',
                             fatal=400 <= response.status_code < 500)
    try:
        result = response.json()
        status, reply = result['status'], result.get('reply')
    except (ValueError, KeyError, TypeError):
        raise TransportError('Respuesta de FastAPI inválida.', fatal=True) from None
    callback = update.get('callback_query')
    message = callback.get('message', {}) if callback else update.get('message', {})
    chat, sender = message.get('chat', {}), callback.get('from', {}) if callback else message.get('from', {})
    private = chat.get('type') == 'private' and chat.get('id') == sender.get('id') and not sender.get('is_bot')
    if status == 'unsupported' and private:
        reply = 'Comandos disponibles: /start CODIGO, /perfil, /mi_perfil, /mis_tareas, /tarea FOLIO, /reportar, /incidencia, /simpatizante, /necesidad y /cancelar.'
    if reply and private:
        payload = {'chat_id': chat['id'], 'text': reply}
        if result.get('reply_markup'):
            payload['reply_markup'] = result['reply_markup']
        # Telegram limita cada texto a 4096 caracteres; un perfil puede tener muchos alcances.
        for offset in range(0,len(reply),4000):
            chunk_payload=dict(payload,text=reply[offset:offset+4000])
            if offset:
                chunk_payload.pop('reply_markup',None)
            telegram_call(client, token, 'sendMessage', **chunk_payload)
    if callback:
        try:
            telegram_call(client, token, 'answerCallbackQuery', callback_query_id=callback['id'])
        except TransportError as exc:
            if not exc.fatal:
                raise


def main():
    token, secret = setting('TELEGRAM_BOT_TOKEN'), setting('TELEGRAM_WEBHOOK_SECRET')
    base_url = (setting('API_BASE_URL') or 'http://127.0.0.1:8000').rstrip('/')
    if not token or not secret:
        print('Configura TELEGRAM_BOT_TOKEN y TELEGRAM_WEBHOOK_SECRET en .env.')
        return 1
    with httpx.Client(timeout=40, follow_redirects=False, trust_env=False) as client:
        try:
            telegram_call(client, token, 'getMe')
            if telegram_call(client, token, 'getWebhookInfo').get('url'):
                print('Existe un webhook activo. No se modificó. Detén el proceso y revisa la configuración.')
                return 1
            print('Receptor activo. Envía /start CODIGO al bot en privado. Ctrl+C para detener.')
            offset = None
            while True:
                try:
                    params = {'timeout': 25, 'allowed_updates': ['message', 'callback_query']}
                    if offset is not None:
                        params['offset'] = offset
                    updates = telegram_call(client, token, 'getUpdates', **params)
                    for update in updates:
                        process_update(client, token, base_url, secret, update)
                        # Solo avanzar después de guardar en API y enviar la respuesta.
                        offset = update['update_id'] + 1
                except TransportError as exc:
                    if exc.fatal:
                        raise
                    print(str(exc) + ' Se reintentará.')
                    time.sleep(min(max(exc.retry_after, 1), 60))
        except TransportError as exc:
            # Nunca imprimir la excepción HTTP original: la URL contiene el token.
            print(str(exc))
            return 1
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('\nReceptor detenido.')
