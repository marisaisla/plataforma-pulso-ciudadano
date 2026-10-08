"""Prueba local de Telegram. Solo biblioteca estandar; sin conexion a Go2Win."""
import json
import os
import time
import urllib.error
import urllib.request
import re


TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()


class TelegramError(Exception):
    pass


def download_photo(file_id):
    """Descarga acotada; nunca expone la URL que contiene el token."""
    limit = 10 * 1024 * 1024
    info = api('getFile', file_id=file_id)
    path = info.get('file_path', '')
    if (not re.fullmatch(r'[A-Za-z0-9_/-]+\.[A-Za-z0-9]+', path)
            or '..' in path or path.startswith('/') or info.get('file_size', 0) > limit):
        raise ValueError('Archivo inválido o demasiado grande')
    try:
        with urllib.request.urlopen(f'https://api.telegram.org/file/bot{TOKEN}/{path}', timeout=40) as response:
            content = response.read(limit + 1)
    except (urllib.error.URLError, TimeoutError, OSError):
        raise TelegramError('No se pudo descargar la fotografía. Se reintentará.') from None
    if len(content) > limit:
        raise ValueError('Fotografía demasiado grande')
    return content


def api(method, **params):
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/{method}",
        data=json.dumps(params).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        # No imprimir la URL: contiene el token.
        raise TelegramError(f"Telegram devolvio HTTP {exc.code}.") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise TelegramError("No se pudo contactar con Telegram.") from None
    if not payload.get("ok"):
        raise TelegramError("Telegram no acepto la operacion.")
    return payload["result"]


def reply(message, pending):
    chat = message["chat"]["id"]
    text = message.get("text", "")
    command = text.split()[0].split("@")[0].lower() if text else ""
    if command in {"/start", "/ayuda"}:
        pending.pop(chat, None)
        return (
            "PRUEBA LOCAL Go2Win (sin conexion a Go2Win).\n"
            "/mis_tareas - Ver una tarea ficticia\n"
            "/reportar - Probar un reporte\n"
            "/evidencia - Probar recepcion de foto\n"
            "/incidencia - Probar una incidencia\n"
            "/cancelar - Cancelar la captura\n"
            "Usa solo datos de prueba. Nada se guarda en Go2Win."
        )
    if command == "/cancelar":
        pending.pop(chat, None)
        return "Captura cancelada."
    if command == "/mis_tareas":
        return "DEMOSTRACION: tarea ficticia 245 — Verificar material de prueba."
    if command in {"/reportar", "/incidencia", "/evidencia"}:
        pending[chat] = command
        return ("Envia una fotografia de prueba." if command == "/evidencia"
                else "Escribe un texto de prueba (sin datos personales).")
    if command.startswith("/"):
        return "Comando desconocido. Usa /ayuda."
    state = pending.get(chat)
    if state == "/evidencia" and not message.get("photo"):
        return "Espero una fotografia, o /cancelar."
    if state in {"/reportar", "/incidencia"} and not text:
        return "Espero un texto, o /cancelar."
    if state:
        pending.pop(chat, None)
        return "Recibido en la PRUEBA. No se guardo en Go2Win ni en archivos locales."
    return "Bot de prueba activo. Selecciona /mis_tareas, /reportar o /ayuda."


def show_message(message):
    # JSON escapa controles de terminal; se muestran solo campos seleccionados.
    sender = message.get("from", {})
    details = {
        "hora": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(message["date"])),
        "chat_id": message["chat"]["id"],
        "usuario": sender.get("username") or sender.get("first_name", "Sin nombre"),
    }
    if "text" in message:
        details["texto"] = message["text"]
    for kind in ("photo", "document", "video", "audio", "voice", "sticker", "location", "contact"):
        if kind in message:
            details["tipo_adjunto"] = kind
            if kind == "document":
                details["archivo"] = message[kind].get("file_name", "Sin nombre")
            break
    if "caption" in message:
        details["descripcion"] = message["caption"]
    print("\nMENSAJE RECIBIDO", flush=True)
    print(json.dumps(details, ensure_ascii=True, indent=2), flush=True)


def main():
    if not TOKEN:
        print("Falta TELEGRAM_BOT_TOKEN. Configuralo en esta ventana de PowerShell.")
        return 1
    try:
        me = api("getMe")
        if api("getWebhookInfo").get("url"):
            print("El bot tiene un webhook activo. No lo modifico; usa otro bot de prueba.")
            return 1
    except TelegramError as exc:
        print(exc)
        return 1
    print(f"Bot @{me['username']} activo. Abre su chat privado y envia /start.")
    print("Ctrl+C para detener. No ejecutes otro receptor para este bot a la vez.")
    print("Solo procesa mensajes privados nuevos; descarta los pendientes anteriores.")
    started = int(time.time())
    pending = {}
    offset = None
    while True:
        try:
            params = {"timeout": 25, "allowed_updates": ["message"]}
            if offset is not None:
                params["offset"] = offset
            updates = api("getUpdates", **params)
            for update in updates:
                offset = update["update_id"] + 1
                message = update.get("message")
                if not message or message.get("date", 0) < started:
                    continue
                if message["chat"].get("type") != "private":
                    continue
                show_message(message)
                response = reply(message, pending)
                api("sendMessage", chat_id=message["chat"]["id"], text=response)
                print("Mensaje de prueba atendido.")
        except TelegramError as exc:
            print(f"{exc} Reintento en 5 segundos; una respuesta fallida puede perderse.")
            time.sleep(5)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nPrueba detenida.")
