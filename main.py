import os, json
from flask import Flask, request
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")
DATA_FILE = "data.json"

app = Flask(__name__)

def tg(method, payload):
    return requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}", json=payload, timeout=15).json()

def send(chat_id, text, kb=None):
    p = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    if kb: p["reply_markup"] = kb
    tg("sendMessage", p)

def menu():
    return {"inline_keyboard":[
        [{"text":"💳 Поповнити","callback_data":"topup"}],
        [{"text":"📞 Запит номера","callback_data":"number"}],
        [{"text":"💬 Підтримка","callback_data":"support"}],
    ]}

def load():
    try: return json.load(open(DATA_FILE,"r",encoding="utf-8"))
    except: return {"admin":{}, "users":{}}

def save(db):
    json.dump(db, open(DATA_FILE,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

@app.get("/")
def home():
    return "OK", 200

@app.post("/webhook")
def webhook():
    up = request.get_json(silent=True) or {}
    db = load()

    if "callback_query" in up:
        cb = up["callback_query"]
        data = cb.get("data","")
        chat_id = cb["message"]["chat"]["id"]
        uid = str(cb["from"]["id"])
        name = (cb["from"].get("first_name","") + " " + cb["from"].get("last_name","")).strip()

        if data in ("topup","number","support"):
            prompts = {
                "topup":"💳 Напиши суму поповнення:",
                "number":"📞 Опиши, для чого потрібен номер:",
                "support":"💬 Напиши питання:"
            }
            send(chat_id, prompts[data], menu())
            send(ADMIN_CHAT_ID,
                 f"📩 Нова заявка\n👤 {name}\n🆔 {uid}\nТип: {data}",
                 {"inline_keyboard":[[{"text":"✉️ Відповісти","callback_data":f"rep|{uid}"}]]})
            db["users"][uid] = {"state": data}
            save(db)
            tg("answerCallbackQuery", {"callback_query_id": cb["id"]})
            return "OK", 200

        if data.startswith("rep|") and str(chat_id) == str(ADMIN_CHAT_ID):
            to_uid = data.split("|",1)[1]
            db["admin"]["reply_to"] = to_uid
            save(db)
            tg("answerCallbackQuery", {"callback_query_id": cb["id"]})
            send(chat_id, f"✉️ Напиши текст — я відправлю клієнту {to_uid}\n(або /cancel)")
            return "OK", 200

    if "message" in up:
        m = up["message"]
        chat_id = str(m["chat"]["id"])
        text = (m.get("text") or "").strip()

        if chat_id == str(ADMIN_CHAT_ID) and db.get("admin",{}).get("reply_to"):
            if text == "/cancel":
                db["admin"].pop("reply_to", None)
                save(db)
                send(chat_id, "✅ Скасовано.")
                return "OK", 200

            to_uid = db["admin"].pop("reply_to")
            save(db)
            send(to_uid, f"📩 Повідомлення:\n{text}", menu())
            send(chat_id, f"✅ Відправлено користувачу {to_uid}")
            return "OK", 200

        if text in ("/start","/menu"):
            send(chat_id, "Вітаю! Обери дію:", menu())
            return "OK", 200

        uid = str(m["from"]["id"])
        if db.get("users",{}).get(uid,{}).get("state"):
            send(chat_id, "✅ Прийняв. Чекай відповідь.", menu())
            send(ADMIN_CHAT_ID,
                 f"📝 Від клієнта\n🆔 {uid}\nТекст: {text}",
                 {"inline_keyboard":[[{"text":"✉️ Відповісти","callback_data":f"rep|{uid}"}]]})
            db["users"][uid] = {}
            save(db)
            return "OK", 200

        send(chat_id, "Оберіть дію:", menu())
    return "OK", 200
