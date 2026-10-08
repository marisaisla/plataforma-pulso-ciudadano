"""Piloto local: activación de trabajadores. Ejecutar desde cualquier directorio."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import prueba_bot_telegram as transport
from services.field_staff import initialize_staff, telegram_reply, telegram_callback
from services.settings import get_setting
from services.database import DATABASE_ERRORS


def process_update(update):
    callback = update.get('callback_query')
    if callback:
        response = telegram_callback(callback)
        # La recepción ya está guardada. Un callback vencido no debe impedir enviar el resultado.
        try:
            transport.api('answerCallbackQuery', callback_query_id=callback['id'])
        except transport.TelegramError:
            print('No se pudo cerrar el aviso del botón; se enviará el resultado al chat.')
        chat = callback.get('message', {}).get('chat', {})
    else:
        message = update.get('message')
        if not message:
            return
        response = telegram_reply(message, photo_loader=transport.download_photo)
        chat = message.get('chat', {})
    if response is not None:
        payload = response if isinstance(response, dict) else {'text': response}
        transport.api('sendMessage', chat_id=chat['id'], **payload)


def main():
    transport.TOKEN = get_setting('TELEGRAM_BOT_TOKEN').strip()
    if not transport.TOKEN:
        print('Falta TELEGRAM_BOT_TOKEN. Configúralo en PowerShell o en el .env privado.')
        return 1
    try:
        transport.api('getMe')
        if transport.api('getWebhookInfo').get('url'):
            print('Existe un webhook activo. No se modificó; revisa el servicio que lo utiliza.')
            return 1
    except transport.TelegramError as exc:
        print(exc)
        return 1
    initialize_staff()
    print('Integrador activo: personal, tareas, recepción y reportes con fotografías. Ctrl+C para detener.')
    print('Detén el script de prueba y cualquier otro receptor del mismo bot.')
    offset = None
    while True:
        try:
            params = {'timeout': 25, 'allowed_updates': ['message', 'callback_query']}
            if offset is not None:
                params['offset'] = offset
            for update in transport.api('getUpdates', **params):
                process_update(update)
                # Solo confirmar lectura después de guardar y responder. No registrar códigos ni mensajes.
                offset = update['update_id'] + 1
        except transport.TelegramError as exc:
            print(f'{exc} Se reintentará en 5 segundos.')
            time.sleep(5)
        except DATABASE_ERRORS:
            print('No se pudo completar el registro en la base de datos. Se reintentará en 5 segundos.')
            time.sleep(5)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('\nIntegrador detenido.')
