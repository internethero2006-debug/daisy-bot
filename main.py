import asyncio
import json
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

TOKEN = "8874721999:AAGpI--ajvKvCzShq5C2O3VyiIFM0TVx-DE"
OWNER_ID = 6228594837  # Твой ID

URL = f"https://api.telegram.org/bot{TOKEN}/"

# Крошечный веб-сервер, чтобы хостинг не отключал бота
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_server():
    server = HTTPServer(('0.0.0.0', 10000), HealthCheckHandler)
    server.serve_forever()

async def check_updates():
    offset = 0
    print("Daisy запущена на сервере!")
    
    while True:
        try:
            req = urllib.request.urlopen(f"{URL}getUpdates?offset={offset}&timeout=10", timeout=12)
            res = json.loads(req.read().decode())
            for update in res.get("result", []):
                offset = update["update_id"] + 1
                if "message" in update and "text" in update["message"]:
                    user_id = update["message"]["from"]["id"]
                    chat_id = update["message"]["chat"]["id"]
                    text = update["message"]["text"]
                    
                    if chat_id == user_id and user_id == OWNER_ID:
                        parts = text.split()
                        if len(parts) == 3 and parts[0].startswith(("/", "!", ".")):
                            cmd = parts[0].lower()
                            target_chat = parts[1]
                            target_user = parts[2]
                            reply = ""

                            if cmd in ["/ban", "!ban"]:
                                urllib.request.urlopen(f"{URL}banChatMember?chat_id={target_chat}&user_id={target_user}")
                                reply = "Пользователь забанен! 🚫"
                            elif cmd in ["/unban", "!unban"]:
                                urllib.request.urlopen(f"{URL}unbanChatMember?chat_id={target_chat}&user_id={target_user}&only_if_banned=true")
                                reply = "Пользователь разбанен! ✅"
                            elif cmd in ["/kick", "!kick"]:
                                urllib.request.urlopen(f"{URL}banChatMember?chat_id={target_chat}&user_id={target_user}")
                                urllib.request.urlopen(f"{URL}unbanChatMember?chat_id={target_chat}&user_id={target_user}")
                                reply = "Пользователь кикнут! 💨"
                            elif cmd in ["/mute", "!mute"]:
                                perm = {"can_send_messages": False, "can_send_media_messages": False, "can_send_polls": False, "can_send_other_messages": False, "can_add_web_page_previews": False}
                                urllib.request.urlopen(f"{URL}restrictChatMember?chat_id={target_chat}&user_id={target_user}&permissions={json.dumps(perm)}")
                                reply = "Пользователь отправлен в мут! 🤫"
                            elif cmd in ["/unmute", "!unmute"]:
                                perm = {"can_send_messages": True, "can_send_media_messages": True, "can_send_polls": True, "can_send_other_messages": True, "can_add_web_page_previews": True}
                                urllib.request.urlopen(f"{URL}restrictChatMember?chat_id={target_chat}&user_id={target_user}&permissions={json.dumps(perm)}")
                                reply = "Мут успешно снят! 🔊"

                            if reply:
                                urllib.request.urlopen(f"{URL}sendMessage?chat_id={chat_id}&text={urllib.parse.quote(reply)}")
        except Exception:
            pass
        await asyncio.sleep(1)

ifif __name__ == "__main__":

    threading.Thread(target=run_health_server, daemon=True).start()
    asyncio.run(check_updates())
