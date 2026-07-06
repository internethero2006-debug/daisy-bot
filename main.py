import asyncio, json, os, threading, time
import urllib.request as request
import urllib.parse as parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime

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
                for key in ["welcomes", "goodbyes", "warns", "ban_list", "mute_list", "activity", "user_stats", "custom_rp"]:
                    if key not in db: db[key] = {}
                return db
        except: pass
    return {"welcomes": {}, "goodbyes": {}, "warns": {}, "ban_list": {}, "mute_list": {}, "activity": {}, "user_stats": {}, "custom_rp": {}}

def save_settings(data):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e: print(f"Ошибка保存: {e}")

settings = load_settings()

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK")

def is_admin(chat_id, user_id):
    if user_id == OWNER_ID: return True
    res = call_api("getChatMember", chat_id=chat_id, user_id=user_id)
    return res and res.get("result", {}).get("status") in ["administrator", "creator"]

def make_bar(value, max_value, length=10):
    if max_value == 0: return "░" * length
    filled = int((value / max_value) * length)
    return "█" * filled + "░" * (length - filled)

# Словарь дефолтных РП-команд (Команда -> Падеж/Текст действия)
DEFAULT_RP = {
    "выебать": "трахнул(а) во все щели 👉👌", "дать пять": "дал(а) пять 🖐️", "записать на ноготочки": "записал(а) на ноготочки 💅",
    "испугать": "напугал(а) до усрачки 👻", "извиниться": "искренне извинился(ась) 🥺", "изнасиловать": "жестко изнасиловал(а) 🔞",
    "кусь": "сделал(а) кусь 🐾", "кастрировать": "кастрировал(а) без наркоза ✂️", "лизнуть": "облизал(а) с ног до головы 👅",
    "лизь": "сделал(а) нежный лизь 👅", "обнять": "крепко обнял(а) 🌸", "отравить": "подсыпал(а) яд в чай 🧪",
    "отдаться": "страстно отдался(ась) 😏", "поздравить": "поздравил(а) с праздником! 🎉", "поцеловать": "нежно поцеловал(а) 💋",
    "прижать": "сильно прижал(а) к себе 🤗", "потрогать": "аккуратно потрогал(а) 😏", "пожать руку": "крепко пожал(а) руку🤝",
    "послать нахуй": "послал(а) нахуй 🖕", "похвалить": "похвалил(а) за хорошую работу 🥰", "понюхать": "принюхался(ась) 👃",
    "погладить": "нежно погладил(а) по голове 👋", "пригласить на чаёк": "пригласил(а) на чаёк ☕", "пригласить на чай": "пригласил(а) на горячий чай ☕",
    "пнуть": "дал(а) мощного пинка 🥾", "покормить": "вкусно покормил(а) 🍔", "расстрелять": "расстрелял(а) у стены 🔫",
    "секс": "занялся(ась) жестким сексом 💥", "сжечь": "сжег(ла) на костре инквизиции 🔥", "трахнуть": "трахнул(а) 😏",
    "ущипнуть": "больно ущипнул(а) 👌", "уебать": "со всей дури уебал(а) 👊", "ударить": "дал(а) пощечину 🖐️",
    "укусить": "сильно укусил(а) 🦷", "куснуть": "мило куснул(а) 🦷", "убить": "жестоко убил(а) 💀",
    "шлепнуть": "шлепнул(а) по заднице 🍑", "делать кекс": "предложил(а) сделать кекс 😏", "облизать": "жадно облизал(а) 👅"
}

async def check_updates():
    global settings, USER_CACHE
    offset = 0
    print("Daisy-Модератор (Профили + Топы + Кастомные РП) запущена!")
    
    MUTE_PERMS = {"can_send_messages": False, "can_send_media_messages": False, "can_send_polls": False, "can_send_other_messages": False, "can_add_web_page_previews": False}
    UNMUTE_PERMS = {"can_send_messages": True, "can_send_media_messages": True, "can_send_polls": True, "can_send_other_messages": True, "can_add_web_page_previews": True}
    
    MOD_COMMANDS = {
        "ban": ("banChatMember", "забанен! 🚫", None), "unban": ("unbanChatMember", "разбанен! ✅", {"only_if_banned": True}),
        "kick": ("banChatMember", "кикнут! 💨", "kick_flag"), "mute": ("restrictChatMember", "отправлен в мут! 🤫", {"permissions": MUTE_PERMS}),
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
                user_id_str = str(user_id)
                
                # Кэширование имен
                first_name = msg["from"].get("first_name", "Участник")
                mention_from = f"[{first_name}](tg://user?id={user_id})"
                if "username" in msg["from"]: USER_CACHE[f"@{msg['from']['username'].lower()}"] = user_id
                
                # --- УЧЕТ СТАТИСТИКИ АКТИВНОСТИ ---
                if chat_id != user_id:
                    if group_id_str not in settings["activity"]: settings["activity"][group_id_str] = []
                    settings["activity"][group_id_str].append(int(time.time()))
                    
                    # Персональный счетчик сообщений
                    if group_id_str not in settings["user_stats"]: settings["user_stats"][group_id_str] = {}
                    if user_id_str not in settings["user_stats"][group_id_str]:
                        settings["user_stats"][group_id_str][user_id_str] = {"msgs": 0, "name": first_name}
                    settings["user_stats"][group_id_str][user_id_str]["msgs"] += 1
                    settings["user_stats"][group_id_str][user_id_str]["name"] = first_name # Обновляем имя если сменил
                    save_settings(settings)

                # Обработка входа/выхода
                if "new_chat_members" in msg:
                    for nm in msg["new_chat_members"]:
                        if "username" in nm: USER_CACHE[f"@{nm['username'].lower()}"] = nm["id"]
                        bot_user = call_api("getMe")
                        if nm.get("username") == (bot_user.get("result", {}).get("username") if bot_user else ""):
                            call_api("sendMessage", chat_id=chat_id, text="Привет! 🌸 Я Daisy.")
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
                clean_cmd = cmd.lstrip("/!.")
                
                # --- УПРАВЛЕНИЕ КАСТОМНЫМИ РП-КОМАНДАМИ ---
                if cmd in ["!создатьрп", "/addrp"]:
                    if len(parts) < 3:
                        call_api("sendMessage", chat_id=chat_id, text="❌ Формат: `!создатьрп команда текст_действия` (Пример: `!создатьрп укусить укусил за ушко`)", parse_mode="Markdown")
                        continue
                    rp_name = parts[1].lower().lstrip("/!.")
                    if rp_name in DEFAULT_RP or rp_name in ["ban", "mute", "stats", "top", "profile", "профиль", "топ"]:
                        call_api("sendMessage", chat_id=chat_id, text="❌ Эту команду нельзя перезаписать, она системная.")
                        continue
                    rp_text = " ".join(parts[2:])
                    if group_id_str not in settings["custom_rp"]: settings["custom_rp"][group_id_str] = {}
                    settings["custom_rp"][group_id_str][rp_name] = rp_text
                    save_settings(settings)
                    call_api("sendMessage", chat_id=chat_id, text=f"✅ РП-команда `!{rp_name}` успешно создана участниками!")
                    continue

                if cmd in ["!рплист", "/rplist"]:
                    c_rp = settings["custom_rp"].get(group_id_str, {})
                    reply = "📋 **Кастомные РП-команды этого чата:**\n" + ("*Ещё никто ничего не придумал*" if not c_rp else "\n".join([f"• `!{k}` — _{v}_" for k, v in c_rp.items()]))
                    call_api("sendMessage", chat_id=chat_id, text=reply, parse_mode="Markdown")
                    continue

                # --- ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ ---
                if clean_cmd in ["профиль", "profile"]:
                    target_id = msg["reply_to_message"]["from"]["id"] if "reply_to_message" in msg else user_id
                    if len(parts) > 1 and not "reply_to_message" in msg:
                        target_id = USER_CACHE.get(parts[1].lower()) if parts[1].startswith("@") else (int(parts[1]) if parts[1].isdigit() else user_id)
                    
                    t_str = str(target_id)
                    u_data = settings["user_stats"].get(group_id_str, {}).get(t_str, {"msgs": 0, "name": "Участник"})
                    all_chat_msgs = sum(x["msgs"] for x in settings["user_stats"].get(group_id_str, {}).values()) or 1
                    share = (u_data["msgs"] / all_chat_msgs) * 100
                    
                    warns_cnt = len(settings["warns"].get(group_id_str, {}).get(t_str, []))
                    in_mute = "Да 🤫" if t_str in settings["mute_list"].get(group_id_str, {}) else "Нет 🔊"
                    is_adm_status = "Администратор 👑" if is_admin(chat_id, target_id) else "Участник ✨"
                    
                    prof_msg = (
                        f"👤 **Профиль пользователя: {u_data['name']}**\n"
                        f"• ID: `{target_id}`\n"
                        f"• Статус в чате: `{is_adm_status}`\n"
                        f"• Отправлено сообщений: `{u_data['msgs']}`\n"
                        f"• Доля от актива чата: `{share:.1f}%`\n"
                        f"• Предупреждения (Варны): `{warns_cnt}/3`\n"
                        f"• В муте: `{in_mute}`"
                    )
                    call_api("sendMessage", chat_id=chat_id, text=prof_msg, parse_mode="Markdown")
                    continue

                # --- ТОП АКТИВИСТОВ ---
                if clean_cmd in ["топ", "top"]:
                    chat_users = settings["user_stats"].get(group_id_str, {})
                    sorted_users = sorted(chat_users.items(), key=lambda x: x[1]["msgs"], reverse=True)[:10]
                    if not sorted_users:
                        call_api("sendMessage", chat_id=chat_id, text="📉 Топ пуст, пишите больше сообщений!")
                        continue
                    lines = ["🏆 **ТОП-10 АКТИВНЫХ УЧАСТНИКОВ ЧАТА** 🏆\n"]
                    max_msgs = sorted_users[0][1]["msgs"] if sorted_users else 1
                    for idx, (u_id, data) in enumerate(sorted_users, 1):
                        lines.append(f"{idx}. {data['name']} — `{data['msgs']}` сообщ. \n    `{make_bar(data['msgs'], max_msgs, 8)}`")
                    call_api("sendMessage", chat_id=chat_id, text="\n".join(lines), parse_mode="Markdown")
                    continue

                # --- ВЫПОЛНЕНИЕ РП-ДЕЙСТВИЙ (ДЕДОЛТНЫЕ + КАСТОМНЫЕ) ---
                if clean_cmd in DEFAULT_RP or clean_cmd in settings["custom_rp"].get(group_id_str, {}):
                    if "reply_to_message" not in msg:
                        call_api("sendMessage", chat_id=chat_id, text="❌ Напишите РП-команду в ответ на сообщение того, с кем хотите сделать действие!")
                        continue
                    
                    target_name = msg["reply_to_message"]["from"].get("first_name", "Участник")
                    target_id = msg["reply_to_message"]["from"]["id"]
                    mention_to = f"[{target_name}](tg://user?id={target_id})"
                    
                    action_text = DEFAULT_RP.get(clean_cmd) or settings["custom_rp"][group_id_str][clean_cmd]
                    call_api("sendMessage", chat_id=chat_id, text=f"🌸 {mention_from} {action_text} {mention_to}", parse_mode="Markdown")
                    continue

                # --- БЛОК АНАЛИТИКИ И СТАТИСТИКИ АКТИВНОСТИ ---
                if cmd in ["!stats", "/stats"] and chat_id != user_id:
                    timestamps = settings["activity"].get(group_id_str, [])
                    now = time.time()
                    
                    if len(parts) > 1 and parts[1].lower() == "hours":
                        hours_count = {i: 0 for i in range(24)}
                        for t in timestamps: hours_count[datetime.fromtimestamp(t).hour] += 1
                        max_h = max(hours_count.values()) if hours_count.values() else 1
                        lines = ["📊 **Активность чата по часам суток:**"]
                        for h in range(24): lines.append(f"`{h:02d}:00` {make_bar(hours_count[h], max_h)} ({hours_count[h]})")
                        call_api("sendMessage", chat_id=chat_id, text="\n".join(lines), parse_mode="Markdown"); continue

                    if len(parts) > 1 and parts[1].lower() == "days":
                        days_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
                        days_count = {i: 0 for i in range(7)}
                        for t in timestamps: days_count[datetime.fromtimestamp(t).weekday()] += 1
                        max_d = max(days_count.values()) if days_count.values() else 1
                        lines = ["📊 **Активность чата по дням недели:**"]
                        for i in range(7): lines.append(f"`{days_names[i]}` {make_bar(days_count[i], max_d, 12)} ({days_count[i]})")
                        call_api("sendMessage", chat_id=chat_id, text="\n".join(lines), parse_mode="Markdown"); continue

                    s_hour = sum(1 for t in timestamps if now - t <= 3600)
                    s_day = sum(1 for t in timestamps if now - t <= 86400)
                    s_week = sum(1 for t in timestamps if now - t <= 604800)
                    s_month = sum(1 for t in timestamps if now - t <= 2592000)
                    s_year = sum(1 for t in timestamps if now - t <= 31536000)
                    
                    stats_msg = (
                        f"📊 **Аналитика активности чата** 📊\n\n"
                        f"• За последний час: `{s_hour}` сообщ.\n"
                        f"• За 24 часа: `{s_day}` сообщ.\n"
                        f"• За неделю: `{s_week}` сообщ.\n"
                        f"• За месяц: `{s_month}` сообщ.\n"
                        f"• За год: `{s_year}` сообщ.\n"
                        f"• Всего записано: `{len(timestamps)}` сообщ.\n\n"
                        f"💡 `!stats hours` / `!stats days` — графики пиков."
                    )
                    call_api("sendMessage", chat_id=chat_id, text=stats_msg, parse_mode="Markdown"); continue

                # --- БЛОК СПИСКОВ НАКАЗАНИЙ ---
                if cmd in ["!bans", "/bans"] and chat_id != user_id:
                    if not is_admin(chat_id, user_id): continue
                    list_data = settings["ban_list"].get(group_id_str, {})
                    reply = "📋 **Список забаненных:**\n" + ("*Пуст*" if not list_data else "\n".join([f"• ID: `{k}` | Причина: *{v['reason']}*" for k, v in list_data.items()]))
                    call_api("sendMessage", chat_id=chat_id, text=reply, parse_mode="Markdown"); continue

                if cmd in ["!mutes", "/mutes"] and chat_id != user_id:
                    if not is_admin(chat_id, user_id): continue
                    list_data = settings["mute_list"].get(group_id_str, {})
                    reply = "📋 **Список пользователей в муте:**\n" + ("*Пуст*" if not list_data else "\n".join([f"• ID: `{k}` | Причина: *{v['reason']}*" for k, v in list_data.items()]))
                    call_api("sendMessage", chat_id=chat_id, text=reply, parse_mode="Markdown"); continue

                if cmd in ["!warns_list", "/warns_list"] and chat_id != user_id:
                    if not is_admin(chat_id, user_id): continue
                    list_data = settings["warns"].get(group_id_str, {})
                    active_warns = {k: v for k, v in list_data.items() if v}
                    reply = "📋 **Список активных варнов:**\n" + ("*Пуст*" if not active_warns else "\n".join([f"• ID: `{k}` | Предупреждений: *{len(v)}/3* (Последнее: {v[-1]})" for k, v in active_warns.items()]))
                    call_api("sendMessage", chat_id=chat_id, text=reply, parse_mode="Markdown"); continue

                # --- СТАНДАРТНАЯ МОДЕРАЦИЯ ---
                if clean_cmd in ["ban", "unban", "kick", "mute", "unmute", "warn", "unwarn", "warns"] and chat_id != user_id:
                    if not is_admin(chat_id, user_id): continue
                    target_id = None
                    r_idx = 1
                    if "reply_to_message" in msg: target_id = msg["reply_to_message"]["from"]["id"]
                    elif len(parts) > 1:
                        if parts[1].startswith("@"): target_id = USER_CACHE.get(parts[1].lower()); r_idx = 2
                        elif parts[1].isdigit(): target_id = int(parts[1]); r_idx = 2
                            
                    if not target_id:
                        call_api("sendMessage", chat_id=chat_id, text="❌ Пользователь не найден.", reply_to_message_id=msg['message_id'])
                        continue
                    
                    target_str = str(target_id)
                    reason = " ".join(parts[r_idx:]).strip() or "Не указана"
                    
                    if clean_cmd == "warns":
                        c_w = settings["warns"].get(group_id_str, {}).get(target_str, [])
                        call_api("sendMessage", chat_id=chat_id, text=f"ℹ️ У пользователя [{target_id}] **{len(c_w)}/3** варнов.", parse_mode="Markdown"); continue

                    if clean_cmd == "unwarn":
                        if group_id_str in settings["warns"] and target_str in settings["warns"][group_id_str] and settings["warns"][group_id_str][target_str]:
                            settings["warns"][group_id_str][target_str].pop()
                            save_settings(settings)
                            call_api("sendMessage", chat_id=chat_id, text=f"✅ Снят варн с [{target_id}].")
                        else: call_api("sendMessage", chat_id=chat_id, text=f"❌ У пользователя нет варнов.")
                        continue

                    if clean_cmd == "warn":
                        if group_id_str not in settings["warns"]: settings["warns"][group_id_str] = {}
                        if target_str not in settings["warns"][group_id_str]: settings["warns"][group_id_str][target_str] = []
                        settings["warns"][group_id_str][target_str].append(reason)
                        t_w = len(settings["warns"][group_id_str][target_str])
                        save_settings(settings)
                        
                        if t_w >= 3:
                            call_api("banChatMember", chat_id=chat_id, user_id=target_id)
                            if group_id_str not in settings["ban_list"]: settings["ban_list"][group_id_str] = {}
                            settings["ban_list"][group_id_str][target_str] = {"reason": "Лимит 3 предупреждения"}
                            settings["warns"][group_id_str][target_str] = []
                            save_settings(settings)
                            call_api("sendMessage", chat_id=chat_id, text=f"🔥 [{target_id}] получил 3/3 варнов и забанен!")
                        else:
                            call_api("sendMessage", chat_id=chat_id, text=f"⚠️ [{target_id}] получил варн (**{t_w}/3**).\n📝 Причина: *{reason}*", parse_mode="Markdown")
                        continue

                    method, success_msg, extra_args = MOD_COMMANDS[clean_cmd]
                    kwargs = {"chat_id": chat_id, "user_id": target_id}
                    if isinstance(extra_args, dict): kwargs.update(extra_args)
                    
                    if clean_cmd == "kick":
                        call_api("banChatMember", chat_id=chat_id, user_id=target_id)
                        call_api("unbanChatMember", chat_id=chat_id, user_id=target_id, only_if_banned=True)
                    else: call_api(method, **kwargs)
                    
                    if clean_cmd == "ban":
                        if group_id_str not in settings["ban_list"]: settings["ban_list"][group_id_str] = {}
                        settings["ban_list"][group_id_str][target_str] = {"reason": reason}
                    elif clean_cmd == "unban" and group_id_str in settings["ban_list"] and target_str in settings["ban_list"][group_id_str]:
                        del settings["ban_list"][group_id_str][target_str]
                    elif clean_cmd == "mute":
                        if group_id_str not in settings["mute_list"]: settings["mute_list"][group_id_str] = {}
                        settings["mute_list"][group_id_str][target_str] = {"reason": reason}
                    elif clean_cmd == "unmute" and group_id_str in settings["mute_list"] and target_str in settings["mute_list"][group_id_str]:
                        del settings["mute_list"][group_id_str][target_str]
                    
                    save_settings(settings)
                    call_api("sendMessage", chat_id=chat_id, text=f"Пользователь [{target_id}] {success_msg}\n📝 Причина: *{reason}*", parse_mode="Markdown", reply_to_message_id=msg['message_id'])

        except Exception as e: print(f"Системный лог: {e}")
        await asyncio.sleep(1)

if __name__ == "__main__":
    threading.Thread(target=HTTPServer(('0.0.0.0', 10000), HealthCheckHandler).serve_forever, daemon=True).start()
    asyncio.run(check_updates())
