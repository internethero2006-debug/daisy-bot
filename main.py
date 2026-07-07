import asyncio, json, os, threading, time, random
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
                for key in ["welcomes", "goodbyes", "warns", "ban_list", "mute_list", "activity", "user_stats", "custom_rp", "shop", "cooldowns"]:
                    if key not in db: db[key] = {}
                return db
        except: pass
    return {"welcomes": {}, "goodbyes": {}, "warns": {}, "ban_list": {}, "mute_list": {}, "activity": {}, "user_stats": {}, "custom_rp": {}, "shop": {}, "cooldowns": {}}

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

def make_bar(value, max_value, length=10):
    if max_value == 0: return "░" * length
    filled = int((value / max_value) * length)
    return "█" * filled + "░" * (length - filled)

# 40 встроенных РП-команд
DEFAULT_RP = {
    "выебать": "трахнул(а) во все щели 👉👌", "дать пять": "дал(а) в ладошку пять 🖐️", "записать на ноготочки": "записал(а) на весенние ноготочки 💅🌸",
    "испугать": "резко выпрыгнул(а) из кустов роз! 👻", "извиниться": "принес(ла) букет извинений 🥺💐", "изнасиловать": "жестко изнасиловал(а) 🔞",
    "кусь": "сделал(а) нежный кусь 🐾", "кастрировать": "аккуратно срезал(а) лишнее секатором ✂️", "лизнуть": "облизал(а) с ног до головы 👅",
    "лизь": "сделал(а) цветочный лизь 👅", "обнять": "укутал(а) в теплые объятия 🌸", "отравить": "подсыпал(а) ядовитую пыльцу в чай 🧪",
    "отдаться": "страстно отдался(ась) под кустом сирени 😏", "поздравить": "осыпал(а) лепестками и поздравил(а)! 🎉🌸", "поцеловать": "сладко поцеловал(а) 💋",
    "прижать": "сильно прижал(а) к своей груди 🤗", "потрогать": "любопытно потрогал(а) 😏", "пожать руку": "уважительно пожал(а) руку🤝",
    "послать нахуй": "отправил(а) гулять в далекий дремучий лес 🖕🌲", "похвалить": "назвал(а) самым красивым цветочком 🥰", "понюхать": "с аппетитом понюхал(а) 👃🌸",
    "погладить": "нежно погладил(а) по стебельку 👋", "пригласить на чаёк": "пригласил(а) на ромашковый чаёк ☕", "пригласить на чай": "пригласил(а) на чай с лепестками роз ☕",
    "пнуть": "дал(а) ускоряющего пинка 🥾", "покормить": "угостил(а) вкусным пирожком 🍔", "расстрелять": "расстрелял(а) семенами подсолнуха 🔫",
    "секс": "устроил(а) дикий цветочный секс 💥", "сжечь": "сжег(ла) дотла, оставив лишь пепел 🔥", "трахнуть": "страстно трахнул(а) 😏",
    "ущипнуть": "больно ущипнул(а) за листик 👌", "уебать": "со всей дури уебал(а) вазой 👊🏺", "ударить": "дал(а) звонкую пощечину крапивой 🌿",
    "укусить": "сильно укусил(а) 🦷", "куснуть": "слегка куснул(а) 🦷", "убить": "закопал(а) под яблоней 💀",
    "шлепнуть": "шлепнул(а) по сочной попке 🍑", "делать кекс": "предложил(а) испечь кекс 😏", "облизать": "жадно облизал(а) 👅"
}

WORK_PHRASES = [
    ("собирал(а) сочные ромашки на поляне и нашел(ла) заначку старого садовода!", 350, 600, True),
    ("аккуратно поливал(а) кактусы админа и не укололся(ась) ни разу. Награда за ловкость!", 35, 60, False),
    ("целый час полол(а) сорняки в чате и спина теперь отваливается...", 15, 30, False),
    ("вырастил(а) гигантскую плотоядную розу, которая съела одного спамера! Админ выписал премию!", 400, 700, True),
    ("продавал(а) букеты на местном рынке. Клиенты попались щедрые!", 40, 65, False),
    ("воровал(а) удобрения из теплицы соседа. Чуть не поймали, но мешок унес(ла)!", 25, 55, False),
    ("просто лежал(а) на газоне и ловил(а) лепестки ртом. Продуктивно!", 10, 20, False),
    ("стриг(ла) кусты в форме Daisy. Получилось шедеврально!", 30, 50, False)
]

async def check_updates():
    global settings, USER_CACHE
    offset = 0
    print("Daisy-Экономика (Цветочная модерация) успешно запущена!")
    
    MUTE_PERMS = {"can_send_messages": False, "can_send_media_messages": False, "can_send_polls": False, "can_send_other_messages": False, "can_add_web_page_previews": False}
    UNMUTE_PERMS = {"can_send_messages": True, "can_send_media_messages": True, "can_send_polls": True, "can_send_other_messages": True, "can_add_web_page_previews": True}
    
    MOD_COMMANDS = {
        "ban": ("banChatMember", "изгнан(а) из оранжереи! 🚫", None), "unban": ("unbanChatMember", "возвращен(а) в сад! ✅", {"only_if_banned": True}),
        "kick": ("banChatMember", "выброшен(а) за забор чата! 💨", "kick_flag"), "mute": ("restrictChatMember", "получил(а) кляп-розу! Больше не шумит 🤫", {"permissions": MUTE_PERMS}),
        "unmute": ("restrictChatMember", "Снова может цвести и говорить! 🔊", {"permissions": UNMUTE_PERMS})
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
                
                first_name = msg["from"].get("first_name", "Участник")
                mention_from = f"[{first_name}](tg://user?id={user_id})"
                if "username" in msg["from"]: USER_CACHE[f"@{msg['from']['username'].lower()}"] = user_id
                
                # --- НЕЗАМЕТНЫЙ СБОР СТАТИСТИКИ И НАЧИСЛЕНИЕ ЛЕПЕСТКОВ ---
                if chat_id != user_id:
                    if group_id_str not in settings["activity"]: settings["activity"][group_id_str] = []
                    settings["activity"][group_id_str].append(int(time.time()))
                    
                    if group_id_str not in settings["user_stats"]: settings["user_stats"][group_id_str] = {}
                    if user_id_str not in settings["user_stats"][group_id_str]:
                        settings["user_stats"][group_id_str][user_id_str] = {"msgs": 0, "name": first_name, "balance": 100} # 100 лепестков бонус новичку
                    
                    settings["user_stats"][group_id_str][user_id_str]["msgs"] += 1
                    settings["user_stats"][group_id_str][user_id_str]["balance"] = settings["user_stats"][group_id_str][user_id_str].get("balance", 100) + 1 # +1 лепесток за смс
                    settings["user_stats"][group_id_str][user_id_str]["name"] = first_name
                    save_settings(settings)

                if "new_chat_members" in msg or "left_chat_member" in msg: continue # Пропустим ради компактности логов
                if not text: continue
                parts = text.split()
                cmd = parts[0].lower()
                clean_cmd = cmd.lstrip("/!.")
                
                # --- ЭКОНОМИКА: КОМАНДА РАБОТА ---
                if clean_cmd in ["работа", "work"]:
                    if chat_id == user_id: continue
                    if group_id_str not in settings["cooldowns"]: settings["cooldowns"][group_id_str] = {}
                    
                    last_time = settings["cooldowns"][group_id_str].get(user_id_str, 0)
                    now_ts = int(time.time())
                    
                    if now_ts - last_time < 1800: # 30 минут кулдаун
                        left = 1800 - (now_ts - last_time)
                        call_api("sendMessage", chat_id=chat_id, text=f"🌸 {mention_from}, твои руки еще устали от садоводства! Отдохни еще `{left // 60} мин. {left % 60} сек.`", parse_mode="Markdown")
                        continue
                    
                    # Шансы: 5% на супер-награду
                    is_lucky = random.random() < 0.05
                    possible_phrases = [p for p in WORK_PHRASES if p[3] == is_lucky]
                    phrase, min_p, max_p, _ = random.choice(possible_phrases)
                    reward = random.randint(min_p, max_p)
                    
                    settings["user_stats"][group_id_str][user_id_str]["balance"] += reward
                    settings["cooldowns"][group_id_str][user_id_str] = now_ts
                    save_settings(settings)
                    
                    prefix = "🌟 **МЕГА-УДАЧА!** 🌟\n" if is_lucky else "🧑‍🌾 "
                    call_api("sendMessage", chat_id=chat_id, text=f"{prefix}{mention_from} {phrase}\nЗаработано: **+{reward} 🌸 лепестков**!", parse_mode="Markdown")
                    continue

                # --- ЭКОНОМИКА: ПЕРЕВОД ДЕНЕГ ---
                if clean_cmd in ["перевод", "pay"]:
                    if chat_id == user_id: continue
                    if len(parts) < 2:
                        call_api("sendMessage", chat_id=chat_id, text="❌ Укажи сумму. Пример: `!перевод 100 @username` или реплаем `!перевод 50`", parse_mode="Markdown")
                        continue
                    
                    if not parts[1].isdigit():
                        call_api("sendMessage", chat_id=chat_id, text="❌ Сумма должна быть целым числом.")
                        continue
                    
                    amount = int(parts[1])
                    if amount <= 0:
                        call_api("sendMessage", chat_id=chat_id, text="❌ Нельзя переводить лепестки в пустоту или воровать!")
                        continue
                        
                    target_id = None
                    if "reply_to_message" in msg:
                        target_id = msg["reply_to_message"]["from"]["id"]
                    elif len(parts) > 2 and parts[2].startswith("@"):
                        target_id = USER_CACHE.get(parts[2].lower())
                        
                    if not target_id or target_id == user_id:
                        call_api("sendMessage", chat_id=chat_id, text="❌ Кому переводим? Укажи юзернейм или ответь на сообщение.")
                        continue
                        
                    t_str = str(target_id)
                    my_bal = settings["user_stats"][group_id_str].get(user_id_str, {}).get("balance", 0)
                    
                    if my_bal < amount:
                        call_api("sendMessage", chat_id=chat_id, text=f"❌ У тебя нет столько лепестков! Твой баланс: `{my_bal} 🌸`", parse_mode="Markdown")
                        continue
                        
                    if t_str not in settings["user_stats"][group_id_str]:
                        settings["user_stats"][group_id_str][t_str] = {"msgs": 0, "name": "Участник", "balance": 100}
                        
                    settings["user_stats"][group_id_str][user_id_str]["balance"] -= amount
                    settings["user_stats"][group_id_str][t_str]["balance"] += amount
                    save_settings(settings)
                    
                    t_name = settings["user_stats"][group_id_str][t_str]["name"]
                    call_api("sendMessage", chat_id=chat_id, text=f"🌸 {mention_from} бережно переслал **{amount} 🌸 лепестков** для [{t_name}](tg://user?id={target_id})!", parse_mode="Markdown")
                    continue

                # --- МАГАЗИН: ПРОСМОТР, ПОКУПКА, УПРАВЛЕНИЕ ---
                if clean_cmd in ["магазин", "shop"]:
                    if chat_id == user_id: continue
                    chat_shop = settings["shop"].get(group_id_str, {})
                    if not chat_shop:
                        call_api("sendMessage", chat_id=chat_id, text="🏪 **Цветочный магазин пуст.** Админы могут добавить товары командой:\n`!добавить_товар [цена] [описание]`", parse_mode="Markdown")
                    else:
                        lines = ["🏪 **Цветочный Магазин Наград Нашего Чата:**\n"]
                        for item_id, item_data in chat_shop.items():
                            lines.append(f"`#{item_id}` — **{item_data['price']} 🌸** | _{item_data['desc']}_")
                        lines.append("\n💡 Напиши `!купить [номер]`, чтобы приобрести товар.")
                        call_api("sendMessage", chat_id=chat_id, text="\n".join(lines), parse_mode="Markdown")
                    continue

                if clean_cmd in ["добавить_товар"] and is_admin(chat_id, user_id):
                    if len(parts) < 3 or not parts[1].isdigit():
                        call_api("sendMessage", chat_id=chat_id, text="❌ Ошибка. Формат: `!добавить_товар [цена] [описание]`")
                        continue
                    price = int(parts[1])
                    desc = " ".join(parts[2:])
                    if group_id_str not in settings["shop"]: settings["shop"][group_id_str] = {}
                    
                    new_id = str(max([int(x) for x in settings["shop"][group_id_str].keys()] + [0]) + 1)
                    settings["shop"][group_id_str][new_id] = {"price": price, "desc": desc}
                    save_settings(settings)
                    call_api("sendMessage", chat_id=chat_id, text=f"✅ Товар добавлен под номером `#{new_id}`!")
                    continue

                if clean_cmd in ["удалить_товар"] and is_admin(chat_id, user_id):
                    if len(parts) < 2: continue
                    i_id = parts[1]
                    if group_id_str in settings["shop"] and i_id in settings["shop"][group_id_str]:
                        del settings["shop"][group_id_str][i_id]
                        save_settings(settings)
                        call_api("sendMessage", chat_id=chat_id, text=f"🗑️ Товар `#{i_id}` успешно удален.")
                    continue

                if clean_cmd in ["купить", "buy"]:
                    if chat_id == user_id: continue
                    if len(parts) < 2: continue
                    i_id = parts[1]
                    chat_shop = settings["shop"].get(group_id_str, {})
                    
                    if i_id not in chat_shop:
                        call_api("sendMessage", chat_id=chat_id, text="❌ Такого товара нет в магазине.")
                        continue
                        
                    item = chat_shop[i_id]
                    my_bal = settings["user_stats"][group_id_str].get(user_id_str, {}).get("balance", 0)
                    
                    if my_bal < item["price"]:
                        call_api("sendMessage", chat_id=chat_id, text=f"❌ Недостаточно лепестков. Нужно: **{item['price']} 🌸**, у тебя: **{my_bal} 🌸**")
                        continue
                        
                    settings["user_stats"][group_id_str][user_id_str]["balance"] -= item["price"]
                    save_settings(settings)
                    
                    call_api("sendMessage", chat_id=chat_id, text=f"🎉 {mention_from} купил товар: **{item['desc']}** за **{item['price']} 🌸**!\n🔔 **Администрация**, выдайте награду покупателю!", parse_mode="Markdown")
                    continue

                # --- ИЗМЕНЕННЫЙ ПРОФИЛЬ (ВКЛЮЧАЕТ БАЛАНС) ---
                if clean_cmd in ["профиль", "profile"]:
                    target_id = msg["reply_to_message"]["from"]["id"] if "reply_to_message" in msg else user_id
                    if len(parts) > 1 and not "reply_to_message" in msg:
                        target_id = USER_CACHE.get(parts[1].lower()) if parts[1].startswith("@") else (int(parts[1]) if parts[1].isdigit() else user_id)
                    
                    t_str = str(target_id)
                    u_data = settings["user_stats"].get(group_id_str, {}).get(t_str, {"msgs": 0, "name": "Участник", "balance": 100})
                    all_chat_msgs = sum(x["msgs"] for x in settings["user_stats"].get(group_id_str, {}).values()) or 1
                    share = (u_data["msgs"] / all_chat_msgs) * 100
                    
                    warns_cnt = len(settings["warns"].get(group_id_str, {}).get(t_str, []))
                    in_mute = "Засох (В муте) 🤫" if t_str in settings["mute_list"].get(group_id_str, {}) else "Цветет 🔊"
                    is_adm_status = "Главный Садовник 👑" if is_admin(chat_id, target_id) else "Росточек чата ✨"
                    
                    prof_msg = (
                        f"👤 **Карточка цветка: {u_data.get('name', 'Участник')}**\n"
                        f"• Ранг: `{is_adm_status}`\n"
                        f"• Баланс кошелька: **{u_data.get('balance', 100)} 🌸 лепестков**\n"
                        f"• Активность в саду: `{u_data['msgs']}` сообщений (`{share:.1f}%`)\n"
                        f"• Сорняки (Варны): `{warns_cnt}/3`\n"
                        f"• Состояние: `{in_mute}`"
                    )
                    call_api("sendMessage", chat_id=chat_id, text=prof_msg, parse_mode="Markdown")
                    continue

                # --- ДАЛЬНЕЙШИЙ КОД БЕЗ ИЗМЕНЕНИЙ (ТОПЫ, СТАТИСТИКА ЗА Х ДНЕЙ, РП, МОДЕРАЦИЯ) ---
                if clean_cmd in ["топ", "top"]:
                    chat_users = settings["user_stats"].get(group_id_str, {})
                    sorted_users = sorted(chat_users.items(), key=lambda x: x[1]["msgs"], reverse=True)[:10]
                    if not sorted_users: continue
                    lines = ["🏆 **Самые пышные цветы нашего чата (ТОП-10):**\n"]
                    max_msgs = sorted_users[0][1]["msgs"] if sorted_users else 1
                    for idx, (u_id, data) in enumerate(sorted_users, 1):
                        lines.append(f"{idx}. {data['name']} — `{data['msgs']}` смс | **{data.get('balance', 100)} 🌸**\n    `{make_bar(data['msgs'], max_msgs, 8)}`")
                    call_api("sendMessage", chat_id=chat_id, text="\n".join(lines), parse_mode="Markdown"); continue

                if clean_cmd in DEFAULT_RP or clean_cmd in settings["custom_rp"].get(group_id_str, {}):
                    if "reply_to_message" not in msg: continue
                    target_name = msg["reply_to_message"]["from"].get("first_name", "Участник")
                    mention_to = f"[{target_name}](tg://user?id={msg['reply_to_message']['from']['id']})"
                    action_text = DEFAULT_RP.get(clean_cmd) or settings["custom_rp"][group_id_str][clean_cmd]
                    call_api("sendMessage", chat_id=chat_id, text=f"🌸 {mention_from} {action_text} {mention_to}", parse_mode="Markdown"); continue

                if cmd in ["!stats", "/stats"] and chat_id != user_id:
                    timestamps = settings["activity"].get(group_id_str, [])
                    now = time.time()
                    if len(parts) > 1 and parts[1].isdigit():
                        days = int(parts[1])
                        count = sum(1 for t in timestamps if now - t <= (days * 86400))
                        call_api("sendMessage", chat_id=chat_id, text=f"📊 **Аналитика за последние {days} дней:**\nВсего сообщений: `{count}`", parse_mode="Markdown"); continue
                    s_day = sum(1 for t in timestamps if now - t <= 86400)
                    s_week = sum(1 for t in timestamps if now - t <= 604800)
                    call_api("sendMessage", chat_id=chat_id, text=f"📊 **Активность в оранжерее:**\n• За 24 часа: `{s_day}` сообщений\n• За неделю: `{s_week}` сообщений", parse_mode="Markdown"); continue

                if clean_cmd in ["ban", "unban", "kick", "mute", "unmute", "warn", "unwarn", "warns"] and chat_id != user_id:
                    if not is_admin(chat_id, user_id): continue
                    target_id = msg["reply_to_message"]["from"]["id"] if "reply_to_message" in msg else (int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else USER_CACHE.get(parts[1].lower() if len(parts) > 1 else ""))
                    if not target_id: continue
                    target_str = str(target_id)
                    reason = " ".join(parts[2:]).strip() if len(parts) > 2 else "Не указана"
                    
                    if clean_cmd == "warn":
                        if group_id_str not in settings["warns"]: settings["warns"][group_id_str] = {}
                        if target_str not in settings["warns"][group_id_str]: settings["warns"][group_id_str][target_str] = []
                        settings["warns"][group_id_str][target_str].append(reason)
                        t_w = len(settings["warns"][group_id_str][target_str])
                        if t_w >= 3:
                            call_api("banChatMember", chat_id=chat_id, user_id=target_id)
                            settings["warns"][group_id_str][target_str] = []
                            call_api("sendMessage", chat_id=chat_id, text=f"🔥 Нарушитель [{target_id}] набрал 3/3 сорняков и забанен!")
                        else:
                            call_api("sendMessage", chat_id=chat_id, text=f"⚠️ [{target_id}] получил сорняк-предупреждение (**{t_w}/3**).\n📝 Причина: *{reason}*", parse_mode="Markdown")
                        save_settings(settings); continue

                    method, success_msg, extra_args = MOD_COMMANDS[clean_cmd]
                    kwargs = {"chat_id": chat_id, "user_id": target_id}
                    if isinstance(extra_args, dict): kwargs.update(extra_args)
                    call_api(method, **kwargs)
                    call_api("sendMessage", chat_id=chat_id, text=f"Пользователь [{target_id}] {success_msg}\n📝 Причина: *{reason}*", parse_mode="Markdown")

        except Exception as e: print(f"Системный лог: {e}")
        await asyncio.sleep(1)

if __name__ == "__main__":
    threading.Thread(target=HTTPServer(('0.0.0.0', 10000), HealthCheckHandler).serve_forever, daemon=True).start()
    asyncio.run(check_updates())
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# Этот класс отвечает UptimeRobot'у, что всё хорошо
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_check():
    # Render ВСЕГДА требует порт 10000 для бесплатных веб-сервисов
    server = HTTPServer(('0.0.0.0', 10000), HealthCheckHandler)
    server.serve_forever()

# Запускаем веб-сервер в отдельном потоке, чтобы он не мешал боту
threading.Thread(target=run_health_check, daemon=True).start()

# ДАЛЬШЕ ТУТ ИДЕТ ТВОЙ СТАНДАРТНЫЙ ЗАПУСК БОТА (например, bot.infinity_polling())
