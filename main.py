import asyncio
import json
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import os

TOKEN = "8874721999:AAGpI--ajvKvCzShq5C2O3VyiIFM0TVx-DE"
OWNER_ID = 6228594837  # Твой ID

URL = f"https://api.telegram.org/bot{TOKEN}/"
SETTINGS_FILE = "welcomes.json"

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"welcomes": {}, "goodbyes": {}}
    return {"welcomes": {}, "goodbyes": {}}

def save_settings(data):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Ошибка сохранения настроек: {e}")

settings = load_settings()

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_server():
    server = HTTPServer(('0.0.0.0', 10000), HealthCheckHandler)
    server.serve_forever()

def is_admin(chat_id, user_id):
    if user_id == OWNER_ID:
        return True
    try:
        check_url = f"{URL}getChatMember?chat_id={chat_id}&user_id={user_id}"
        req = urllib.request.urlopen(check_url)
        res = json.loads(req.read().decode())
        status = res.get("result", {}).get("status", "")
        return status in ["administrator", "creator"]
    except Exception:
        return False

async def check_updates():
    global settings
    offset = 0
    print("Daisy-Модератор (Приветствия + Прощания) запущена!")
    
    while True:
        try:
            req = urllib.request.urlopen(f"{URL}getUpdates?offset={offset}&timeout=10", timeout=12)
            res = json.loads(req.read().decode())
            for update in res.get("result", []):
                offset = update["update_id"] + 1
                if "message" in update:
                    message = update["message"]
                    user_id = message["from"]["id"]
                    chat_id = message["chat"]["id"]
                    text = message.get("text", "")
                    group_id_str = str(chat_id)
                    
                    if "new_chat_members" in message:
                        for new_member in message["new_chat_members"]:
                            bot_username = json.loads(urllib.request.urlopen(f"{URL}getMe").read().decode()).get("result", {}).get("username")
                            if new_member.get("username") == bot_username:
                                bot_intro = "Привет всем! 🌸 Я Daisy, ваш новый бот-модератор. Дайте мне права админа!\n\nНастройки:\n`!сетпривет Текст` — приветствие\n`!сетпока Текст` — прощание"
                                urllib.request.urlopen(f"{URL}sendMessage?chat_id={chat_id}&text={urllib.parse.quote(bot_intro)}&parse_mode=Markdown")
                            else:
                                welcome_text = settings["welcomes"].get(group_id_str, "Привет! Добро пожаловать в наш чат! 🌸")
                                first_name = new_member.get("first_name", "Участник")
                                final_welcome = f"@{new_member.get('username', first_name)}, {welcome_text}" if new_member.get('username') else f"{first_name}, {welcome_text}"
                                urllib.request.urlopen(f"{URL}sendMessage?chat_id={chat_id}&text={urllib.parse.quote(final_welcome)}")
                        continue

                    if "left_chat_member" in message:
                        left_member = message["left_chat_member"]
                        bot_username = json.loads(urllib.request.urlopen(f"{URL}getMe").read().decode()).get("result", {}).get("username")
                        
                        if left_member.get("username") == bot_username:
                            print(f" Нас удалили из чата {chat_id}. Очень грустно!")
                        else:
                            goodbye_text = settings["goodbyes"].get(group_id_str, "покинул нас. Нам будет тебя не хватать! 😿")
                            first_name = left_member.get("first_name", "Участник")
                            final_goodbye = f"@{left_member.get('username', first_name)} {goodbye_text}" if left_member.get('username') else f"{first_name} {goodbye_text}"
                            urllib.request.urlopen(f"{URL}sendMessage?chat_id={chat_id}&text={urllib.parse.quote(final_goodbye)}")
                        continue

                    if not text:
                        continue
                        
                    parts = text.split()
                    cmd = parts[0].lower() if parts else ""

                    if cmd in ["!сетпривет", "/setwelcome"] and chat_id != user_id:
                        if is_admin(chat_id, user_id):
                            content = text[len(parts[0]):].strip()
                            if content:
                                settings["welcomes"][group_id_str] = content
                                save_settings(settings)
                                reply = "✅ Приветствие для новых участников сохранено!"
                            else:
                                reply = "❌ Укажите текст приветствия после команды."
                            urllib.request.urlopen(f"{URL}sendMessage?chat_id={chat_id}&text={urllib.parse.quote(reply)}&reply_to_message_id={message['message_id']}")
                        continue

                    if cmd in ["!сетпока", "/setgoodbye"] and chat_id != user_id:
                        if is_admin(chat_id, user_id):
                            content = text[len(parts[0]):].strip()
                            if content:
                                settings["goodbyes"][group_id_str] = content
                                save_settings(settings)
                                reply = "✅ Прощание для уходящих участников сохранено!"
                            else:
                                reply = "❌ Укажите текст прощания после команды."
                            urllib.request.urlopen(f"{URL}sendMessage?chat_id={chat_id}&text={urllib.parse.quote(reply)}&reply_to_message_id={message['message_id']}")
                        continue

                    if not cmd.startswith(("/", "!", ".")):
                        continue

                    if chat_id != user_id and "reply_to_message" in message:
                        target_user = message["reply_to_message"]["from"]["id"]
                        if is_admin(chat_id, user_id):
                            reply = ""
                            if cmd in ["/ban", "!ban", ".ban"]:
                                urllib.request.urlopen(f"{URL}banChatMember?chat_id={chat_id}&user_id={target_user}")
                                reply = "Пользователь забанен! 🚫"
                            elif cmd in ["/unban", "!unban", ".unban"]:
                                urllib.request.urlopen(f"{URL}unbanChatMember?chat_id={chat_id}&user_id={target_user}&only_if_banned=true")
                                reply = "Пользователь разбанен! ✅"
                            elif cmd in ["/kick", "!kick", ".kick"]:
                                urllib.request.urlopen(f"{URL}banChatMember?chat_id={chat_id}&user_id={target_user}")
                                urllib.request.urlopen(f"{URL}unbanChatMember?chat_id={chat_id}&user_id={target_user}")
                                reply = "Пользователь кикнут! 💨"
                            elif cmd in ["/mute", "!mute", ".mute"]:
                                perm = {"can_send_messages": False, "can_send_media_messages": False, "can_send_polls": False, "can_send_other_messages": False, "can_add_web_page_previews": False}
                                urllib.request.urlopen(f"{URL}restrictChatMember?chat_id={chat_id}&user_id={target_user}&permissions={json.dumps(perm)}")
                                reply = "Пользователь отправлен в мут! 🤫"
                            elif cmd in ["/unmute", "!unmute", ".unmute"]:
                                perm = {"can_send_messages": True, "can_send_media_messages": True, "can_send_polls": True, "can_send_other_messages": True, "can_add_web_page_previews": True}
                                urllib.request.urlopen(f"{URL}restrictChatMember?chat_id={chat_id}&user_id={target_user}&permissions={json.dumps(perm)}")
                                reply = "Мут успешно снят! 🔊"
                            
                            if reply:
                                urllib.request.urlopen(f"{URL}sendMessage?chat_id={chat_id}&text={urllib.parse.quote(reply)}&reply_to_message_id={message['message_id']}")

                    elif chat_id == user_id and user_id == OWNER_ID:
                        if len(parts) == 3:
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

                    if cmd == "/start":
                        if chat_id == user_id and user_id == OWNER_ID:
                            reply_msg = "Привет, хозяин! 🌸 Дейзи полностью обновлена и готова к работе."
                        else:
                            reply_msg = "Привет! Я Daisy — бот-модератор. 🌸 Добавь меня в группу и дай права админа!"
                        urllib.request.urlopen(f"{URL}sendMessage?chat_id={chat_id}&text={urllib.parse.quote(reply_msg)}")
                        
        except Exception as e:
            print(f"Системный лог: {e}")
            
        await asyncio.sleep(1)

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    asyncio.run(check_updates())
