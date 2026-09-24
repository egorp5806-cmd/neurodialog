# -*- coding: utf-8 -*-
import os
import json
import re
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

# ===================== НАСТРОЙКИ =====================
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВСТАВЬ_СЮДА_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "ВСТАВЬ_СЮДА_OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")

HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "10000"))

# Для Telegram нужен публичный HTTPS-адрес Mini App.
# Например: https://example.com
WEB_APP_URL = os.getenv("WEB_APP_URL", "")

DEMO = {
    "summary": "Судя по тексту, собеседник сейчас занят и не готов продолжать обсуждение. Лучше показать понимание и оставить лёгкий вариант для продолжения позже.",
    "emotional_tone": "Нейтральный",
    "initiative": "Низкая",
    "approach": "Мягкий",
    "pace": "Спокойный",
    "recommendations": [
        "Не давите вопросами и не требуйте немедленного ответа.",
        "Покажите, что уважаете занятость собеседника.",
        "Можно предложить простой вариант продолжить разговор позже.",
        "Сохраните спокойный и позитивный тон."
    ],
    "answers": {
        "calm": "Хорошо, без проблем 🙂 Давай позже, когда будет удобнее.",
        "initiative": "Понял! Тогда как будешь свободна, давай выберем день и обсудим.",
        "warm": "Кажется, у тебя сейчас очень насыщенный день. Не буду отвлекать. Напиши, когда будет удобнее 🙂"
    }
}

SYSTEM_PROMPT = """
Ты — Нейродиалог, помощник для анализа переписки.
Анализируй только переданный текст. Не утверждай, что знаешь реальные мысли,
намерения или чувства другого человека. Используй формулировки «судя по тексту»
и «может выглядеть так». Не ставь диагнозы. Не предлагай манипуляции, давление,
шантаж или обман.

Определи:
- краткий ключ ситуации;
- эмоциональный фон;
- инициативу;
- подход;
- темп общения;
- 3-5 рекомендаций;
- три естественных варианта ответа: calm, initiative, warm.

Верни ТОЛЬКО JSON:
{
 "summary":"...",
 "emotional_tone":"...",
 "initiative":"...",
 "approach":"...",
 "pace":"...",
 "recommendations":["...","...","..."],
 "answers":{"calm":"...","initiative":"...","warm":"..."}
}
"""

def extract_json(text):
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b < a:
        raise ValueError("AI не вернул JSON")
    return json.loads(text[a:b+1])

def ai_request(user_text, system_prompt=SYSTEM_PROMPT):
    if not OPENAI_API_KEY or OPENAI_API_KEY.startswith("ВСТАВЬ"):
        return DEMO.copy()

    payload = {
        "model": OPENAI_MODEL,
        "instructions": system_prompt,
        "input": user_text
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + OPENAI_API_KEY
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read().decode("utf-8"))

        text = data.get("output_text", "")
        if not text:
            parts = []
            for item in data.get("output", []):
                for c in item.get("content", []):
                    if isinstance(c, dict) and c.get("text"):
                        parts.append(c["text"])
            text = "\n".join(parts)

        return extract_json(text)
    except Exception as e:
        print("[OpenAI]", e)
        return DEMO.copy()

def tg_api(method, data=None):
    if not BOT_TOKEN or BOT_TOKEN.startswith("ВСТАВЬ"):
        return None
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
            json=data or {},
            timeout=40
        )
        result = r.json()
        if not result.get("ok"):
            print("[Telegram]", result)
        return result
    except Exception as e:
        print("[Telegram]", e)
        return None

def send_message(chat_id, text, markup=None):
    data = {"chat_id": chat_id, "text": text}
    if markup:
        data["reply_markup"] = markup
    return tg_api("sendMessage", data)

def start_telegram_bot():
    if not BOT_TOKEN or BOT_TOKEN.startswith("ВСТАВЬ"):
        print("[Telegram] BOT_TOKEN не задан — бот не запущен.")
        return

    tg_api("setMyCommands", {"commands": [
        {"command": "start", "description": "Открыть Нейродиалог"},
        {"command": "help", "description": "Помощь"}
    ]})

    if WEB_APP_URL:
        tg_api("setChatMenuButton", {
            "menu_button": {
                "type": "web_app",
                "text": "Нейродиалог",
                "web_app": {"url": WEB_APP_URL}
            }
        })

    # Для long polling удаляем старый webhook, если он был установлен.
    tg_api("deleteWebhook", {"drop_pending_updates": False})
    print("[Telegram] Бот запущен.")
    offset = 0

    while True:
        result = tg_api("getUpdates", {
            "offset": offset,
            "timeout": 25,
            "allowed_updates": ["message"]
        })

        if not result or not result.get("ok"):
            continue

        for update in result.get("result", []):
            offset = update["update_id"] + 1
            message = update.get("message", {})
            chat_id = message.get("chat", {}).get("id")
            text = message.get("text", "")

            if not chat_id:
                continue

            if text.startswith("/start"):
                if WEB_APP_URL:
                    markup = {
                        "inline_keyboard": [[
                            {
                                "text": "🧠 Открыть Нейродиалог",
                                "web_app": {"url": WEB_APP_URL}
                            }
                        ]]
                    }
                    send_message(
                        chat_id,
                        "Привет! Я Нейродиалог.\n\n"
                        "Открой приложение, вставь переписку, "
                        "и получи анализ и варианты ответа.",
                        markup
                    )
                else:
                    send_message(
                        chat_id,
                        "Бот работает, но Mini App ещё не настроен. "
                        "Укажи WEB_APP_URL с публичным HTTPS-адресом."
                    )

            elif text.startswith("/help"):
                send_message(
                    chat_id,
                    "Нажми «Открыть Нейродиалог», вставь переписку "
                    "и получи подсказки."
                )

HTML = r"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Нейродиалог</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
*{box-sizing:border-box}
body{margin:0;background:#020b14;color:#f5f7fa;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.app{max-width:430px;min-height:100vh;margin:auto;background:#071522}
.top{height:70px;display:flex;align-items:center;justify-content:space-between;padding:10px 14px;border-bottom:1px solid #193047}
.top button{background:none;border:0;color:#50a7ff;font-size:30px}
.title{text-align:center}.title b{font-size:18px}.title small{display:block;color:#8093a7;font-size:11px}
.screen{display:none;padding:12px}.screen.on{display:block}
.profile{display:flex;gap:11px;align-items:center;background:#102033;border:1px solid #1b344b;border-radius:16px;padding:11px;margin-bottom:11px}
.avatar{width:43px;height:43px;border-radius:50%;display:grid;place-items:center;background:linear-gradient(135deg,#c78972,#654a60);font-weight:bold}
.profile small{display:block;color:#8093a7;margin-top:2px}
.chat{min-height:390px}
.bubble{max-width:88%;background:#172638;padding:12px 13px;border-radius:15px;margin:8px 0;line-height:1.4}
.out{margin-left:auto;background:#176db3}.time{font-size:10px;color:#8297aa}
.box,.card{background:#0d1d2c;border:1px solid #1b344b;border-radius:16px;padding:12px;margin-bottom:10px}
textarea{width:100%;height:95px;resize:none;border:0;outline:0;border-radius:12px;background:#102439;color:#fff;padding:11px;font-size:14px}
.btn{width:100%;padding:14px;border:0;border-radius:13px;margin-top:8px;font-weight:bold;font-size:15px;background:#2587ff;color:#fff}
.btn:disabled{opacity:.55}.secondary{background:#102d48;color:#72b9ff;border:1px solid #25577f}
.tabs{display:grid;grid-template-columns:repeat(4,1fr);gap:5px;margin-bottom:11px}
.tab{border:0;background:#0d1d2d;color:#8296aa;border-radius:9px;padding:9px 2px;font-size:11px}
.tab.active{background:#205f99;color:#fff}
.card h3{margin:0 0 10px;font-size:15px}.key{line-height:1.5;font-size:14px}
.metric{display:flex;justify-content:space-between;border-top:1px solid #1b3145;padding-top:10px;margin-top:10px;color:#8499ad;font-size:13px}
.metric b{color:#fff}li{margin:7px 0;color:#c9d5df;font-size:13px}
.answer{background:#0d1d2c;border:1px solid #1b344b;border-radius:16px;padding:14px;margin:10px 0}
.answer h3{margin:0 0 9px;color:#58db79;font-size:14px}.answer p{line-height:1.5;font-size:14px}
.row{display:flex;gap:7px}.row button{flex:1;border:0;border-radius:10px;padding:11px;background:#142d44;color:#d9e4ed}
.row .send{background:#2587ff;color:#fff}.privacy{text-align:center;color:#607589;font-size:11px;padding:16px}
.toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#16304a;padding:11px 15px;border-radius:11px;display:none;z-index:99}
</style>
</head>
<body>
<div class="app">
<header class="top">
<button id="back">‹</button>
<div class="title"><b>Нейродиалог</b><small>личный помощник</small></div>
<button id="menu">•••</button>
</header>

<section id="s1" class="screen on">
<div class="profile"><div class="avatar">А</div><div><b>Анна</b><small>Личный диалог</small></div></div>
<div class="chat">
<div class="bubble">Привет! <span class="time">14:20</span></div>
<div class="bubble">Сегодня скорее всего<br>не получится, очень много дел( <span class="time">14:21</span></div>
<div class="bubble out">Понял, без проблем 🙂 <span class="time">14:22 ✓✓</span></div>
<div class="bubble">Давай позже обсудим,<br>хорошо? <span class="time">14:23</span></div>
</div>
<div class="box">
<textarea id="text">Анна: Сегодня скорее всего не получится, очень много дел(
Я: Понял, без проблем 🙂
Анна: Давай позже обсудим, хорошо?</textarea>
<button class="btn" id="go">🧠 Получить подсказки</button>
</div>
<div class="privacy">🔒 Всё, что вы видите в Нейродиалоге, доступно только вам.</div>
</section>

<section id="s2" class="screen">
<div class="profile"><div class="avatar">А</div><div><b>Анна</b><small>Личный диалог</small></div></div>
<div class="tabs"><button class="tab active">Ключи</button><button class="tab">Ситуация</button><button class="tab">Ответы</button><button class="tab">Профиль</button></div>
<div id="info" class="card"></div>
<div class="card"><h3>💡 Рекомендации</h3><ul id="rec"></ul></div>
<button class="btn" id="answersBtn">Показать варианты ответа</button>
</section>

<section id="s3" class="screen">
<div class="profile"><div class="avatar">А</div><div><b>Анна</b><small>Личный диалог</small></div></div>
<div class="tabs"><button class="tab">Ключи</button><button class="tab">Ситуация</button><button class="tab active">Ответы</button><button class="tab">Профиль</button></div>
<div id="answers"></div>
<button class="btn secondary" id="more">↻ Ещё варианты</button>
</section>
</div>
<div id="toast" class="toast"></div>

<script>
const tg=window.Telegram&&window.Telegram.WebApp?window.Telegram.WebApp:null;
if(tg){tg.ready();tg.expand();}
let A=null;
const $=id=>document.getElementById(id);

function show(id){
 document.querySelectorAll(".screen").forEach(x=>x.classList.remove("on"));
 $(id).classList.add("on");scrollTo(0,0);
}
function esc(x){
 return String(x??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
}
function toast(x){
 let t=$("toast");t.textContent=x;t.style.display="block";
 clearTimeout(window.__t);window.__t=setTimeout(()=>t.style.display="none",2200);
}
async function post(url,data){
 let r=await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});
 if(!r.ok)throw Error();return r.json();
}

$("go").onclick=async()=>{
 let text=$("text").value.trim();
 if(!text)return toast("Вставьте переписку");
 $("go").disabled=true;$("go").textContent="🧠 Анализирую…";
 try{A=await post("/api/analyze",{text});render();show("s2")}
 catch(e){toast("Ошибка анализа")}
 finally{$("go").disabled=false;$("go").textContent="🧠 Получить подсказки";}
};

function render(){
 $("info").innerHTML=`<h3>🔑 Ключ к ситуации</h3>
 <div class="key">${esc(A.summary)}</div>
 <div class="metric"><span>Эмоциональный фон</span><b>${esc(A.emotional_tone)}</b></div>
 <div class="metric"><span>Инициатива</span><b>${esc(A.initiative)}</b></div>
 <div class="metric"><span>Подход</span><b>${esc(A.approach)}</b></div>
 <div class="metric"><span>Темп общения</span><b>${esc(A.pace)}</b></div>`;
 $("rec").innerHTML=(A.recommendations||[]).map(x=>`<li>${esc(x)}</li>`).join("");
}

$("answersBtn").onclick=()=>{renderAnswers();show("s3");};

function renderAnswers(){
 $("answers").innerHTML=[
 ["calm","Спокойно"],["initiative","С инициативой"],["warm","Теплее"]
 ].map(x=>`<div class="answer"><h3>${x[1]}</h3><p>${esc(A.answers[x[0]])}</p>
 <div class="row"><button onclick="copyA('${x[0]}')">▣ Скопировать</button>
 <button class="send" onclick="sendA('${x[0]}')">➤ Отправить</button></div></div>`).join("");
}

window.copyA=async k=>{
 try{await navigator.clipboard.writeText(A.answers[k]);toast("Ответ скопирован")}
 catch(e){toast("Не удалось скопировать")}
};

window.sendA=async k=>{
 const text=A.answers[k];
 try{
   await navigator.clipboard.writeText(text);
   if(tg && tg.showPopup){
     tg.showPopup({title:"Готово",message:"Ответ скопирован. Вставьте его в нужный чат.",buttons:[{type:"ok"}]});
   }else toast("Ответ скопирован");
 }catch(e){toast("Ответ скопирован");}
};

$("more").onclick=async()=>{
 $("more").disabled=true;$("more").textContent="↻ Генерирую…";
 try{let x=await post("/api/more",{analysis:A});A.answers=x.answers;renderAnswers();toast("Новые варианты готовы")}
 catch(e){toast("Ошибка")}
 finally{$("more").disabled=false;$("more").textContent="↻ Ещё варианты";}
};

$("back").onclick=()=>{
 if($("s3").classList.contains("on"))show("s2");
 else if($("s2").classList.contains("on"))show("s1");
 else toast("Это первый экран");
};
$("menu").onclick=()=>toast("Нейродиалог • AI-анализ • варианты ответа");
</script>
</body>
</html>"""

class WebHandler(BaseHTTPRequestHandler):
    def json(self, obj, status=200):
        body=json.dumps(obj,ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Cache-Control","no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/","/index.html"):
            body=HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Cache-Control","no-store")
            self.end_headers()
            self.wfile.write(body)
        elif self.path=="/health":
            self.json({"ok":True})
        else:
            self.send_error(404)

    def do_POST(self):
        try:
            length=int(self.headers.get("Content-Length","0"))
            data=json.loads(self.rfile.read(length).decode("utf-8"))

            if self.path=="/api/analyze":
                text=str(data.get("text","")).strip()
                if not text:
                    return self.json({"error":"empty"},400)
                self.json(ai_request(text))
                return

            if self.path=="/api/more":
                analysis=data.get("analysis",{})
                prompt=(
                    "Создай ещё три естественных варианта ответа на основе "
                    "анализа. Не используй давление или манипуляции. "
                    'Верни только JSON: {"answers":{"calm":"...",'
                    '"initiative":"...","warm":"..."}}.\n'
                    + json.dumps(analysis,ensure_ascii=False)
                )
                self.json(ai_request(prompt,"Ты генерируешь естественные ответы. Верни только JSON."))
                return

            self.json({"error":"not found"},404)

        except Exception as e:
            self.json({"error":str(e)},500)

    def log_message(self, fmt, *args):
        print("[WEB]",fmt%args)

def main():
    print("\n=== НЕЙРОДИАЛОГ ===")
    print("WEB:",f"http://{HOST}:{PORT}")
    print("BOT_TOKEN:", "OK" if BOT_TOKEN and not BOT_TOKEN.startswith("ВСТАВЬ") else "НЕ ЗАДАН")
    print("OPENAI_API_KEY:", "OK" if OPENAI_API_KEY and not OPENAI_API_KEY.startswith("ВСТАВЬ") else "DEMO")
    print("WEB_APP_URL:", WEB_APP_URL or "НЕ ЗАДАН")
    print()

    threading.Thread(
        target=lambda: ThreadingHTTPServer((HOST,PORT),WebHandler).serve_forever(),
        daemon=True
    ).start()

    start_telegram_bot()

if __name__=="__main__":
    main()
