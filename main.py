import asyncio, json, os, threading
import urllib.request as request
import urllib.parse as parse
from http.server import BaseHTTPRequestHandler, HTTPServer

TOKEN = "8874721999:AAGpI--ajvKvCzShq5C2O3VyiIFM0TVx-DE"
OWNER_ID = 6228594837  # Твой ID
URL = f"https://api.telegram.org/bot{TOKEN}/"
SETTINGS_FILE = "welcomes.json"
USER_CACHE = {}

def call_api(method, **kwargs):
    try:
        query = "&".join([f"{k}={parse.quote(str(v))}" if k != "permissions" else f"{k}={parse.quote(json.dumps(v))}" for k, v in kwargs.items()])
        req = request.urlopen(f"{URL}{method}?{query}", timeout=10)
        return json.loads(req.read().decode())
    except Exception as e:
        print(f"Ошибка API ({method}): {e}")
        return None

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                db = json.load(f)
                # Проверяем наличие всех нужных разделов в базе
                for key in ["welcomes", "goodbyes", "warns", "ban_list"]:
                    if key not in db: db[key] = {}
                return db
        except: pass
    return {"welcomes": {}, "goodbyes": {}, "warns": {}, "ban_list": {}}

def save_settings(data):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e: print(f"Ошибка сохранения: {e}")

settings = load_settings()

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK")

def is_admin(chat_id, user_id):
    if user_id == OWNER_ID: return True
    res = call_api("getChatMember", chat_id=chat_id, user_id=user_id)
    return res and res.get("result", {}).get("status") in ["administrator", "creator"]

async def check_updates():
    global settings, USER_CACHE
    offset = 0
    print("Daisy-Модератор (Варны + Причины + Списки) запущена!")
    
    MUTE_PERMS = {"can_send_messages": False, "can_send_media_messages": False, "can_send_polls": False, "can_send_other_messages": False, "can_add_web_page_previews": False}
    UNMUTE_PERMS = {"can_send_messages": True, "can_send_media_messages": True, "can_send_polls": True, "can_send_other_messages": True, "can_add_web_page_previews": True}
    
    MOD_COMMANDS = {
        "ban": ("banChatMember", "забанен! 🚫", None),
        "unban": ("unbanChatMember", "разбанен! ✅", {"only_if_banned": True}),
        "kick": ("banChatMember", "кикнут! 💨", "kick_flag"),
        "mute": ("restrictChatMember", "отправлен в мут! 🤫", {"permissions": MUTE_PERMS}),
        "unmute": ("restrictChatMember", "Мут успешно снят! 🔊", {"permissions": UNMUTE_PERMS})
    }

    while True:
        try:
            res = call_api("getUpdates", offset=offset, timeout=10)
            if not res or "result" not in res: continue
            
            for update in res["result"]:
                offset = update["update_id"] + 1
                if "message" not in update: continue
                
                msg = update["message"]
                user_id, chat_id, text = msg["from"]["id"], msg["chat"]["id"], msg.get("text", "")
                group_id_str = str(chat_id)
                
                if "username" in msg["from"]: USER_CACHE[f"@{msg['from']['username'].lower()}"] = user_id
                
                # Системные события (Вход/Выход)
                if "new_chat_members" in msg:
                    for nm in msg["new_chat_members"]:
                        if "username" in nm: USER_CACHE[f"@{nm['username'].lower()}"] = nm["id"]
                        bot_user = call_api("getMe")
                        if nm.get("username") == (bot_user.get("result", {}).get("username") if bot_user else ""):
                            call_api("sendMessage", chat_id=chat_id, text="Привет! 🌸 Я Daisy. Дайте мне права админа!")
                        else:
                            txt = settings["welcomes"].get(group_id_str, "Привет! Добро пожаловать! 🌸")
                            name = f"@{nm['username']}" if nm.get("username") else nm.get("first_name", "Участник")
                            call_api("sendMessage", chat_id=chat_id, text=f"{name}, {txt}")
                    continue

                if "left_chat_member" in msg:
                    lm = msg["left_chat_member"]
                    txt = settings["goodbyes"].get(group_id_str, "покинул нас. 😿")
                    name = f"@{lm['username']}" if lm.get("username") else lm.get("first_name", "Участник")
                    call_api("sendMessage", chat_id=chat_id, text=f"{name} {txt}")
                    continue

                if not text: continue
                parts = text.split()
                cmd = parts[0].lower()
                
                # Настройки приветствий
                if cmd in ["!сетпривет", "/setwelcome", "!сетпока", "/setgoodbye"] and chat_id != user_id:
                    if is_admin(chat_id, user_id):
                        content = text[len(parts[0]):].strip()
                        key = "welcomes" if "привет" in cmd or "welcome" in cmd else "goodbyes"
                        if content:
                            settings[key][group_id_str] = content
                            save_settings(settings)
                            call_api("sendMessage", chat_id=chat_id, text="✅ Сохранено!", reply_to_message_id=msg['message_id'])
                    continue

                if cmd == "/start":
                    call_api("sendMessage", chat_id=chat_id, text="Привет! Я Daisy — бот-модератор. 🌸")
                    continue

                # --- ПРОСМОТР СПИСКА БАНОВ ЧАТА ---
                if cmd in ["!bans", "/bans", ".bans"] and chat_id != user_id:
                    if not is_admin(chat_id, user_id): continue
                    chat_bans = settings["ban_list"].get(group_id_str, {})
                    if not chat_bans:
                        call_api("sendMessage", chat_id=chat_id, text="📋 Список забаненных в этом чате пуст.")
                    else:
                        lines = ["📋 **Список забаненных пользователей:**"]
                        for b_id, b_info in chat_bans.items():
                            lines.append(f"• ID: `{b_id}` | Причина: *{b_info['reason']}*")
                        call_api("sendMessage", chat_id=chat_id, text="\n".join(lines), parse_mode="Markdown")
                    continue

                # --- БЛОК МОДЕРАЦИИ (С ВАРНАМИ И ПРИЧИНАМИ) ---
                clean_cmd = cmd.lstrip("/!.")
                if clean_cmd in ["ban", "unban", "kick", "mute", "unmute", "warn", "unwarn", "warns"] and chat_id != user_id:
                    if not is_admin(chat_id, user_id): continue
                    
                    target_id = None
                    reason_start_index = 1
                    
                    # Поиск цели
                    if "reply_to_message" in msg:
                        target_id = msg["reply_to_message"]["from"]["id"]
                    elif len(parts) > 1:
                        if parts[1].startswith("@"):
                            target_id = USER_CACHE.get(parts[1].lower())
                            reason_start_index = 2
                        elif parts[1].isdigit():
                            target_id = int(parts[1])
                            reason_start_index = 2
                            
                    if not target_id:
                        call_api("sendMessage", chat_id=chat_id, text="❌ Пользователь не найден.", reply_to_message_id=msg['message_id'])
                        continue
                    
                    target_str = str(target_id)
                    reason = " ".join(parts[reason_start_index:]).strip()
                    if not reason: reason = "Не указана"
                    
                    # Просмотр варнов (Команда !warns)
                    if clean_cmd == "warns":
                        current_warns = settings["warns"].get(group_id_str, {}).get(target_str, [])
                        call_api("sendMessage", chat_id=chat_id, text=f"ℹ️ У пользователя [{target_id}] сейчас **{len(current_warns)}/3** варнов.", parse_mode="Markdown")
                        continue

                    # Снятие варна (Команда !unwarn)
                    if clean_cmd == "unwarn":
                        if group_id_str in settings["warns"] and target_str in settings["warns"][group_id_str]:
                            if settings["warns"][group_id_str][target_str]:
                                settings["warns"][group_id_str][target_str].pop()
                                save_settings(settings)
                                call_api("sendMessage", chat_id=chat_id, text=f"✅ Снято одно предупреждение с [{target_id}].")
                                continue
                        call_api("sendMessage", chat_id=chat_id, text=f"❌ У пользователя [{target_id}] нет варнов.")
                        continue

                    # Выдача варна (Команда !warn)
                    if clean_cmd == "warn":
                        if group_id_str not in settings["warns"]: settings["warns"][group_id_str] = {}
                        if target_str not in settings["warns"][group_id_str]: settings["warns"][group_id_str][target_str] = []
                        
                        settings["warns"][group_id_str][target_str].append(reason)
                        total_warns = len(settings["warns"][group_id_str][target_str])
                        save_settings(settings)
                        
                        if total_warns >= 3:
                            # 3 варна -> Автоматический Бан
                            call_api("banChatMember", chat_id=chat_id, user_id=target_id)
                            if group_id_str not in settings["ban_list"]: settings["ban_list"][group_id_str] = {}
                            settings["ban_list"][group_id_str][target_str] = {"reason": "Достигнут лимит в 3 предупреждения"}
                            settings["warns"][group_id_str][target_str] = [] # Сброс варнов после бана
                            save_settings(settings)
                            call_api("sendMessage", chat_id=chat_id, text=f"🔥 Пользователь [{target_id}] получил 3/3 варнов и был автоматически **забанен**!")
                        else:
                            call_api("sendMessage", chat_id=chat_id, text=f"⚠️ Пользователь [{target_id}] получил предупреждение (**{total_warns}/3**).\n📝 Причина: *{reason}*", parse_mode="Markdown")
                        continue

                    # Обычные команды (ban, mute, и т.д.)
                    method, success_msg, extra_args = MOD_COMMANDS[clean_cmd]
                    kwargs = {"chat_id": chat_id, "user_id": target_id}
                    if isinstance(extra_args, dict): kwargs.update(extra_args)
                    
                    if clean_cmd == "kick":
                        call_api("banChatMember", chat_id=chat_id, user_id=target_id)
                        call_api("unbanChatMember", chat_id=chat_id, user_id=target_id, only_if_banned=True)
                    else:
                        call_api(method, **kwargs)
                    
                    # Ведение списков банов для !bans
                    if clean_cmd == "ban":
                        if group_id_str not in settings["ban_list"]: settings["ban_list"][group_id_str] = {}
                        settings["ban_list"][group_id_str][target_str] = {"reason": reason}
                        save_settings(settings)
                    elif clean_cmd == "unban":
                        if group_id_str in settings["ban_list"] and target_str in settings["ban_list"][group_id_str]:
                            del settings["ban_list"][group_id_str][target_str]
                            save_settings(settings)
                            
                    call_api("sendMessage", chat_id=chat_id, text=f"Пользователь [{target_id}] {success_msg}\n📝 Причина: *{reason}*", parse_mode="Markdown", reply_to_message_id=msg['message_id'])

        except Exception as e: print(f"Системный лог: {e}")
        await asyncio.sleep(1)

if __name__ == "__main__":
    threading.Thread(target=HTTPServer(('0.0.0.0', 10000), HealthCheckHandler).serve_forever, daemon=True).start()
    asyncio.run(check_updates())
