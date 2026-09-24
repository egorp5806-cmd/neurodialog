# -*- coding: utf-8 -*-
import os, json, sqlite3, threading, hashlib, hmac, time, html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HOST='0.0.0.0'; PORT=int(os.getenv('PORT','10000')); BOT_TOKEN=os.getenv('BOT_TOKEN',''); DB_PATH=os.getenv('DB_PATH','neurocity.db'); LOCK=threading.RLock()

def db():
    c=sqlite3.connect(DB_PATH,timeout=30,check_same_thread=False); c.row_factory=sqlite3.Row; return c

def init_db():
    with LOCK:
        c=db(); c.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT,name TEXT NOT NULL,coins INTEGER DEFAULT 500,bank INTEGER DEFAULT 0,xp INTEGER DEFAULT 0,level INTEGER DEFAULT 1,streak INTEGER DEFAULT 0,last_bonus INTEGER DEFAULT 0,created_at INTEGER);
        CREATE TABLE IF NOT EXISTS businesses(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_id INTEGER,name TEXT,category TEXT,description TEXT,capital INTEGER DEFAULT 0,level INTEGER DEFAULT 1,rating REAL DEFAULT 5,revenue INTEGER DEFAULT 0,created_at INTEGER);
        CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY AUTOINCREMENT,business_id INTEGER,title TEXT,reward INTEGER,slots INTEGER DEFAULT 1,salary INTEGER DEFAULT 0,created_at INTEGER);
        CREATE TABLE IF NOT EXISTS work(id INTEGER PRIMARY KEY AUTOINCREMENT,job_id INTEGER,user_id INTEGER,created_at INTEGER,UNIQUE(job_id,user_id));
        CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT,seller_id INTEGER,title TEXT,description TEXT,price INTEGER,created_at INTEGER,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS purchases(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER,buyer_id INTEGER,seller_id INTEGER,price INTEGER,created_at INTEGER);
        CREATE TABLE IF NOT EXISTS chat(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,text TEXT,created_at INTEGER);
        CREATE TABLE IF NOT EXISTS follows(follower_id INTEGER,target_id INTEGER,created_at INTEGER,PRIMARY KEY(follower_id,target_id));
        CREATE TABLE IF NOT EXISTS business_reviews(id INTEGER PRIMARY KEY AUTOINCREMENT,business_id INTEGER,user_id INTEGER,rating INTEGER,text TEXT,created_at INTEGER);
        CREATE TABLE IF NOT EXISTS likes(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,business_id INTEGER,created_at INTEGER,UNIQUE(user_id,business_id));
        CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,text TEXT,created_at INTEGER,seen INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS achievements(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,code TEXT,created_at INTEGER,UNIQUE(user_id,code));
        CREATE TABLE IF NOT EXISTS seasons(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,ends_at INTEGER);
        CREATE TABLE IF NOT EXISTS inventory(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,item TEXT,qty INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS comments(id INTEGER PRIMARY KEY AUTOINCREMENT,business_id INTEGER,user_id INTEGER,text TEXT,created_at INTEGER);
        ''');
        if not c.execute('SELECT 1 FROM seasons').fetchone(): c.execute('INSERT INTO seasons(name,ends_at) VALUES(?,?)',('Сезон «Город будущего»',int(time.time())+30*86400))
        c.commit(); c.close()

def validate_init(s):
    if not s:return None
    try:
        pairs={k:v for k,v in (x.split('=',1) for x in s.split('&') if '=' in x)}; raw=pairs.get('user');
        if not raw:return None
        u=json.loads(raw)
        if BOT_TOKEN and 'hash' in pairs:
            check='\n'.join(f'{k}={pairs[k]}' for k in sorted(pairs) if k!='hash'); secret=hmac.new(b'WebAppData',BOT_TOKEN.encode(),hashlib.sha256).digest(); good=hmac.new(secret,check.encode(),hashlib.sha256).hexdigest()
            if not hmac.compare_digest(good,pairs['hash']):return None
        return u
    except:return None

def ensure_user(t):
    uid=int(t.get('id',0));
    if not uid:return None
    name=(' '.join(x for x in [t.get('first_name',''),t.get('last_name','')] if x).strip() or t.get('username') or 'Игрок')
    with LOCK:
        c=db(); r=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
        if not r:c.execute('INSERT INTO users(id,username,name,created_at) VALUES(?,?,?,?)',(uid,t.get('username',''),name,int(time.time())))
        else:c.execute('UPDATE users SET username=?,name=? WHERE id=?',(t.get('username',''),name,uid))
        c.commit(); r=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone(); c.close(); return dict(r)

def current_user(h):return ensure_user(validate_init(h.headers.get('X-Telegram-Init-Data','')) or {'id':1,'first_name':'Гость','username':'demo'})
def body(h):
    n=int(h.headers.get('Content-Length','0')); return json.loads(h.rfile.read(n).decode() or '{}')
def level_for(xp):return max(1,int(xp//500)+1)
def j(o):return json.dumps(o,ensure_ascii=False).encode()

HTML=r'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no"><title>NeuroCity</title><script src="https://telegram.org/js/telegram-web-app.js"></script><style>
:root{--bg:#050b14;--panel:#0b1524;--panel2:#101f32;--line:#1c344c;--text:#f6f8fc;--muted:#8296aa;--blue:#4b8cff;--cyan:#36d9ff;--green:#37d98a;--gold:#ffd15a;--pink:#d779ff}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 50% -10%,#183a63 0,#050b14 43%);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.app{max-width:500px;min-height:100vh;margin:auto;padding-bottom:88px}.top{position:sticky;top:0;z-index:9;display:flex;justify-content:space-between;align-items:center;padding:12px 15px;background:rgba(5,11,20,.9);backdrop-filter:blur(18px);border-bottom:1px solid #142b42}.logo{display:flex;gap:9px;align-items:center}.logoMark{width:38px;height:38px;border-radius:13px;display:grid;place-items:center;background:linear-gradient(135deg,#39d9ff,#6a57ff);box-shadow:0 8px 25px #2250aa66;font-size:21px}.logo b{font-size:17px}.logo small{display:block;color:var(--muted);font-size:9px}.wallet{border:1px solid #4c4a25;background:#211e0b;color:var(--gold);padding:8px 10px;border-radius:12px;font-weight:800}.screen{display:none;padding:14px}.screen.on{display:block}.hero{padding:8px 2px 15px}.hero h1{font-size:28px;line-height:1.05;margin:4px 0 7px}.hero p{color:var(--muted);margin:0;line-height:1.45}.banner{padding:15px;border-radius:20px;background:linear-gradient(135deg,#102d4d,#17203e);border:1px solid #295a86;position:relative;overflow:hidden}.banner:after{content:'✦';position:absolute;right:18px;top:8px;font-size:65px;color:#5b8dff22}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px}.stat,.card,.item{background:linear-gradient(145deg,#0c1929,#091522);border:1px solid var(--line);border-radius:18px;padding:13px}.stat b{font-size:17px}.stat small,.muted{display:block;color:var(--muted);font-size:11px;margin-top:3px}.section{font-weight:850;margin:18px 0 9px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:9px}.tile{min-height:112px;padding:14px;border:1px solid var(--line);border-radius:18px;background:linear-gradient(145deg,#10253a,#0b1827);cursor:pointer}.tile .ico{font-size:25px}.tile b{display:block;margin-top:7px}.tile small{color:var(--muted)}.row{display:flex;gap:9px;align-items:center}.avatar{width:43px;height:43px;border-radius:50%;display:grid;place-items:center;background:linear-gradient(135deg,#4d8cff,#9d50d8);font-weight:900;flex:none}.avatar.big{width:68px;height:68px;font-size:24px}.btn{width:100%;border:0;border-radius:13px;padding:12px;background:linear-gradient(135deg,#3d91ff,#5868ff);color:white;font-weight:850;margin-top:9px}.btn.green{background:linear-gradient(135deg,#159c62,#31c785)}.btn.dark{background:#10273e;border:1px solid #28516f;color:#9dceff}.btn.gold{background:linear-gradient(135deg,#e4a824,#ffce58);color:#241a00}.input{width:100%;padding:12px;border-radius:12px;border:1px solid var(--line);background:#071321;color:#fff;margin:5px 0 8px;outline:none;font:inherit}.tabs{display:flex;gap:6px;overflow:auto;margin:10px 0}.tab{white-space:nowrap;border:1px solid var(--line);background:#091725;color:#8ea3b7;border-radius:11px;padding:8px 11px}.tab.active{background:#174f80;color:#fff}.pill{display:inline-block;background:#112f4a;color:#78c5ff;border-radius:8px;padding:5px 8px;font-size:10px}.coins{color:var(--gold);font-weight:900}.progress{height:7px;background:#122335;border-radius:9px;overflow:hidden}.progress i{display:block;height:100%;background:linear-gradient(90deg,var(--cyan),var(--blue));border-radius:9px}.rank{display:flex;align-items:center;gap:10px;padding:11px 0;border-bottom:1px solid #173048}.rank:last-child{border:0}.place{width:27px;text-align:center;color:var(--gold);font-weight:900}.chat{height:58vh;overflow:auto}.msg{max-width:87%;padding:9px 11px;border-radius:14px;background:#102338;margin:7px 0}.msg.me{margin-left:auto;background:#155f9d}.msg b{color:#75c5ff;font-size:11px}.msg p{margin:4px 0;line-height:1.4}.msg time{color:#6d8398;font-size:9px}.composer{display:flex;gap:7px;position:sticky;bottom:77px;padding-top:7px;background:linear-gradient(transparent,var(--bg) 20%)}.composer .input{margin:0}.nav{position:fixed;bottom:0;left:50%;transform:translateX(-50%);width:min(500px,100%);display:grid;grid-template-columns:repeat(5,1fr);background:rgba(5,12,21,.97);border-top:1px solid #173149;padding:7px 4px calc(7px + env(safe-area-inset-bottom));z-index:12}.nav button{border:0;background:none;color:#70879b;font-size:9px}.nav button span{display:block;font-size:20px;margin-bottom:1px}.nav button.active{color:#55a6ff}.modal{position:fixed;inset:0;background:#0009;display:none;align-items:flex-end;z-index:30}.modal.on{display:flex}.sheet{width:100%;max-width:500px;margin:auto;background:#091725;border:1px solid #24445f;border-radius:24px 24px 0 0;padding:17px;max-height:90vh;overflow:auto}.close{float:right;background:none;border:0;color:#8da1b5;font-size:25px}.toast{position:fixed;bottom:95px;left:50%;transform:translateX(-50%);background:#173450;padding:10px 15px;border-radius:12px;display:none;z-index:50}.feed{border-left:2px solid #1e4768;padding-left:13px}.feed .event{margin:10px 0}.empty{text-align:center;color:var(--muted);padding:28px}.mini{font-size:11px;color:var(--muted)}.two{display:grid;grid-template-columns:1fr 1fr;gap:8px}.price{font-size:20px;font-weight:900;color:var(--gold)}</style></head><body><div class="app">
<header class="top"><div class="logo"><div class="logoMark">✦</div><div><b>NeuroCity</b><small>BUILD • WORK • TRADE</small></div></div><div class="wallet">🪙 <span id="coins">0</span></div></header>
<section id="home" class="screen on"><div class="banner"><div class="pill">СЕЗОН 01</div><h1>Построй свою империю</h1><p>Создавай бизнесы, нанимай людей, торгуй и поднимайся в рейтинге города.</p></div><div class="stats"><div class="stat"><b id="xp">0</b><small>XP</small></div><div class="stat"><b id="level">1</b><small>уровень</small></div><div class="stat"><b id="rank">—</b><small>рейтинг</small></div></div><div class="section">Быстрые действия</div><div class="grid"><div class="tile" onclick="go('business')"><div class="ico">🏢</div><b>Бизнес</b><small>Создать и развивать</small></div><div class="tile" onclick="go('jobs')"><div class="ico">💼</div><b>Работа</b><small>Заработать монеты</small></div><div class="tile" onclick="go('market')"><div class="ico">🛍️</div><b>Рынок</b><small>Торговля игроков</small></div><div class="tile" onclick="go('rating')"><div class="ico">🏆</div><b>Рейтинг</b><small>Лидеры города</small></div></div><div class="section">Ежедневный бонус</div><div class="card"><div class="row"><div style="font-size:30px">🎁</div><div style="flex:1"><b>Бонус за вход</b><div class="mini">Серия: <span id="streak">0</span> дней</div></div><button class="btn gold" style="width:auto;margin:0" onclick="bonus()">Забрать</button></div></div><div class="section">Лента города</div><div class="card feed" id="feed"></div></section>
<section id="business" class="screen"><h2>🏢 Бизнесы</h2><button class="btn" onclick="openBiz()">＋ Создать бизнес</button><div id="businesses"></div></section>
<section id="jobs" class="screen"><h2>💼 Работа</h2><div class="card"><b>Твои навыки</b><div class="progress" style="margin-top:8px"><i id="skillbar" style="width:20%"></i></div><div class="mini" style="margin-top:6px">Чем больше работаешь — тем выше уровень.</div></div><div id="jobsList"></div></section>
<section id="market" class="screen"><h2>🛍️ Рынок</h2><button class="btn dark" onclick="openProduct()">＋ Выставить товар</button><div class="tabs"><button class="tab active">Все</button><button class="tab">Популярное</button><button class="tab">Новинки</button></div><div id="products"></div></section>
<section id="rating" class="screen"><h2>🏆 Рейтинг</h2><div class="tabs"><button class="tab active" onclick="loadRating('coins',this)">🪙 Богатые</button><button class="tab" onclick="loadRating('xp',this)">⚡ XP</button><button class="tab" onclick="loadBizRating(this)">🏢 Бизнес</button></div><div id="ratingList"></div></section>
<section id="chat" class="screen"><h2>💬 Городской чат</h2><div class="card mini">Общайся с жителями NeuroCity. Уважай других игроков.</div><div class="chat" id="chatList"></div><div class="composer"><input class="input" id="chatInput" placeholder="Написать в город..." maxlength="500"><button class="btn" style="width:58px;margin:0" onclick="sendChat()">➤</button></div></section>
<section id="profile" class="screen"><div id="profileCard"></div><div class="section">Мои достижения</div><div id="achievements"></div><div class="section">Мои товары</div><div id="inventory"></div></section>
</div><nav class="nav"><button onclick="go('home')" data-n="home"><span>⌂</span>Главная</button><button onclick="go('business')" data-n="business"><span>🏢</span>Бизнес</button><button onclick="go('market')" data-n="market"><span>🛍️</span>Рынок</button><button onclick="go('chat')" data-n="chat"><span>💬</span>Чат</button><button onclick="go('profile')" data-n="profile"><span>👤</span>Профиль</button></nav>
<div id="modal" class="modal" onclick="if(event.target===this)closeModal()"><div class="sheet"><button class="close" onclick="closeModal()">×</button><div id="modalBody"></div></div></div><div id="toast" class="toast"></div>
<script>
const tg=window.Telegram?.WebApp; if(tg){tg.ready();tg.expand();} const initData=tg?.initData||''; let me=null;
const $=id=>document.getElementById(id), esc=x=>String(x??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
async function api(path,data={}){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Telegram-Init-Data':initData},body:JSON.stringify(data)});const x=await r.json();if(!r.ok||x.error)throw Error(x.error||'Ошибка');return x}
function toast(s){$('toast').textContent=s;$('toast').style.display='block';clearTimeout(window.tt);window.tt=setTimeout(()=>$('toast').style.display='none',2200)}
function go(id){document.querySelectorAll('.screen').forEach(x=>x.classList.remove('on'));$(id).classList.add('on');document.querySelectorAll('.nav button').forEach(b=>b.classList.toggle('active',b.dataset.n===id)); if(id==='business')loadBiz();if(id==='jobs')loadJobs();if(id==='market')loadProducts();if(id==='rating')loadRating('coins');if(id==='chat')loadChat();if(id==='profile')loadProfile();}
async function load(){const x=await api('/api/me');me=x.user;renderMe(x);loadFeed();loadBiz();}
function renderMe(x){$('coins').textContent=x.user.coins.toLocaleString();$('xp').textContent=x.user.xp.toLocaleString();$('level').textContent=x.user.level;$('rank').textContent='#'+x.rank;$('streak').textContent=x.user.streak;$('skillbar').style.width=Math.min(100,(x.user.xp%500)/5)+'%';$('profile').innerHTML=`<div class="row"><div class="avatar">${esc((x.user.name||'И')[0])}</div><div style="flex:1"><b>${esc(x.user.name)}</b><div class="mini">@${esc(x.user.username||'player')} · уровень ${x.user.level}</div></div><span class="coins">🪙 ${x.user.coins.toLocaleString()}</span></div><div style="margin-top:12px"><div class="mini">До уровня ${x.user.level+1}</div><div class="progress"><i style="width:${(x.user.xp%500)/5}%"></i></div></div>`}
async function loadFeed(){let x=await api('/api/feed');$('feed').innerHTML=x.items.length?x.items.map(e=>`<div class="event"><b>${esc(e.title)}</b><div class="mini">${esc(e.text)}</div></div>`).join(''):'<div class="empty">Пока тихо. Создай первое событие!</div>'}
async function loadBiz(){let x=await api('/api/businesses');$('businesses').innerHTML=x.items.map(b=>`<div class="item"><div class="row"><div class="avatar">🏢</div><div style="flex:1"><h3 style="margin:0">${esc(b.name)}</h3><div class="mini">${esc(b.category)} · уровень ${b.level}</div></div><span>⭐ ${Number(b.rating).toFixed(1)}</span></div><p class="muted">${esc(b.description)}</p><div class="row"><span class="pill">👤 ${esc(b.owner_name)}</span><span class="pill">💰 ${b.capital.toLocaleString()}</span><button class="btn dark" style="width:auto;margin:0" onclick="viewBusiness(${b.id})">Открыть</button></div></div>`).join('')||'<div class="empty">Создай первый бизнес.</div>'}
async function viewBusiness(id){let x=await api('/api/business/view',{id});openModal(`<h2>🏢 ${esc(x.business.name)}</h2><div class="row"><div class="avatar">${esc((x.owner.name||'И')[0])}</div><div><b>${esc(x.owner.name)}</b><div class="mini">${x.following?'Вы подписаны':'Подпишись на владельца'}</div></div></div><p class="muted">${esc(x.business.description)}</p><div class="two"><div class="card"><b>⭐ ${Number(x.business.rating).toFixed(1)}</b><div class="mini">рейтинг</div></div><div class="card"><b>🏆 ${x.business.level}</b><div class="mini">уровень</div></div></div><button class="btn dark" onclick="follow(${x.owner.id})">${x.following?'Отписаться':'Подписаться'}</button><h3>💬 Отзывы</h3><div>${x.comments.map(c=>`<div class="item"><b>${esc(c.name)}</b><div class="mini">${'⭐'.repeat(c.rating)}</div><p class="muted">${esc(c.text)}</p></div>`).join('')||'<div class="empty">Пока нет отзывов.</div>'}</div><textarea class="input" id="reviewText" placeholder="Напиши отзыв"></textarea><div class="tabs"><button class="tab active" onclick="setRating(5,this)">5 ⭐</button><button class="tab" onclick="setRating(4,this)">4 ⭐</button><button class="tab" onclick="setRating(3,this)">3 ⭐</button></div><button class="btn" onclick="review(${id})">Оставить отзыв</button>`);window.reviewRating=5}
function setRating(n,b){window.reviewRating=n;document.querySelectorAll('.tabs .tab').forEach(x=>x.classList.remove('active'));b.classList.add('active')}
async function review(id){await api('/api/business/review',{id,rating:window.reviewRating||5,text:$('reviewText').value});toast('Отзыв добавлен');closeModal();loadBiz()}
async function follow(id){let x=await api('/api/follow',{target_id:id});toast(x.following?'Подписка оформлена':'Подписка отменена')}
async function loadJobs(){let x=await api('/api/jobs');$('jobsList').innerHTML=x.items.map(j=>`<div class="item"><div class="row"><div style="flex:1"><h3>${esc(j.title)}</h3><div class="mini">${esc(j.business_name)} · осталось ${j.slots}</div></div><span class="coins">+${j.reward} 🪙</span></div><button class="btn green" onclick="work(${j.id})">Выполнить работу</button></div>`).join('')||'<div class="empty">Вакансий пока нет.</div>'}
async function work(id){try{let x=await api('/api/work',{job_id:id});toast(x.message);load();loadJobs()}catch(e){toast(e.message)}}
async function loadProducts(){let x=await api('/api/products');$('products').innerHTML=x.items.map(p=>`<div class="item"><div class="row"><div style="flex:1"><h3>${esc(p.title)}</h3><div class="mini">от ${esc(p.seller_name)}</div></div><div class="price">${p.price.toLocaleString()} 🪙</div></div><p class="muted">${esc(p.description)}</p><button class="btn" onclick="buy(${p.id})">Купить</button></div>`).join('')||'<div class="empty">Рынок пуст.</div>'}
async function buy(id){try{let x=await api('/api/buy',{product_id:id});toast(x.message);load();loadProducts()}catch(e){toast(e.message)}}
async function loadRating(kind='coins',el){let x=await api('/api/rating',{kind});$('ratingList').innerHTML=x.items.map((u,i)=>`<div class="rank"><div class="place">${i+1}</div><div class="avatar">${esc((u.name||'И')[0])}</div><div style="flex:1"><b>${esc(u.name)}</b><div class="mini">уровень ${u.level} · @${esc(u.username||'player')}</div></div><b class="coins">${(kind==='coins'?u.coins:u.xp).toLocaleString()} ${kind==='coins'?'🪙':'XP'}</b></div>`).join('')}
async function loadBizRating(){let x=await api('/api/business/rating');$('ratingList').innerHTML=x.items.map((b,i)=>`<div class="rank"><div class="place">${i+1}</div><div class="avatar">🏢</div><div style="flex:1"><b>${esc(b.name)}</b><div class="mini">${esc(b.owner_name)}</div></div><b>⭐ ${Number(b.rating).toFixed(1)}</b></div>`).join('')}
async function loadChat(){let x=await api('/api/chat');$('chatList').innerHTML=x.items.map(m=>`<div class="msg ${m.user_id===me?.id?'me':''}"><b>${esc(m.name)}</b><p>${esc(m.text)}</p><time>${new Date(m.created_at*1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}</time></div>`).join('');$('chatList').scrollTop=$('chatList').scrollHeight}
async function sendChat(){let t=$('chatInput').value.trim();if(!t)return;try{await api('/api/chat/send',{text:t});$('chatInput').value='';loadChat()}catch(e){toast(e.message)}}
async function bonus(){try{let x=await api('/api/bonus');toast(x.message);load()}catch(e){toast(e.message)}}
async function loadProfile(){let x=await api('/api/profile');$('profileCard').innerHTML=`<div class="card"><div class="row"><div class="avatar big">${esc((x.user.name||'И')[0])}</div><div style="flex:1"><h2 style="margin:0">${esc(x.user.name)}</h2><div class="mini">@${esc(x.user.username||'player')} · уровень ${x.user.level}</div></div></div><div class="two" style="margin-top:12px"><div class="stat"><b>🪙 ${x.user.coins.toLocaleString()}</b><small>кошелёк</small></div><div class="stat"><b>🏦 ${x.user.bank.toLocaleString()}</b><small>банк</small></div></div><button class="btn dark" onclick="bank()">🏦 Управление банком</button></div>`;$('achievements').innerHTML=x.achievements.map(a=>`<div class="item"><b>${a.done?'🏆':'🔒'} ${esc(a.title)}</b><div class="mini">${esc(a.text)}</div></div>`).join('');$('inventory').innerHTML=x.inventory.map(i=>`<div class="item"><b>📦 ${esc(i.item)}</b><span class="coins"> ×${i.qty}</span></div>`).join('')||'<div class="empty">Инвентарь пуст.</div>'}
async function bank(){let x=await api('/api/bank');openModal(`<h2>🏦 Банк</h2><p class="muted">В банке: <b>${x.bank.toLocaleString()} 🪙</b></p><input class="input" id="bankAmt" type="number" min="1" placeholder="Сумма"><div class="two"><button class="btn" onclick="bankMove('deposit')">Положить</button><button class="btn dark" onclick="bankMove('withdraw')">Снять</button></div>`)}
async function bankMove(type){try{await api('/api/bank/move',{type,amount:+$('bankAmt').value});closeModal();load();loadProfile();toast('Готово')}catch(e){toast(e.message)}}
function openModal(body){$('modalBody').innerHTML=body;$('modal').classList.add('on')}function closeModal(){$('modal').classList.remove('on')}
function openBiz(){openModal(`<h2>🏢 Новый бизнес</h2><input class="input" id="bn" placeholder="Название бизнеса"><input class="input" id="bc" placeholder="Категория"><textarea class="input" id="bd" placeholder="Описание" style="height:90px"></textarea><input class="input" id="bp" type="number" min="50" value="100" placeholder="Стартовый капитал"><input class="input" id="jt" placeholder="Вакансия"><input class="input" id="jr" type="number" min="1" value="50" placeholder="Награда"><button class="btn" onclick="createBiz()">🚀 Запустить бизнес</button>`)}
async function createBiz(){try{await api('/api/business/create',{name:$('bn').value,category:$('bc').value,description:$('bd').value,capital:+$('bp').value,job_title:$('jt').value,job_reward:+$('jr').value});closeModal();toast('Бизнес создан!');load();loadBiz()}catch(e){toast(e.message)}}
function openProduct(){openModal(`<h2>🛍️ Новый товар</h2><input class="input" id="pt" placeholder="Название"><textarea class="input" id="pd" placeholder="Описание" style="height:90px"></textarea><input class="input" id="pp" type="number" min="1" placeholder="Цена"><button class="btn" onclick="createProduct()">Выставить на рынок</button>`)}
async function createProduct(){try{await api('/api/product/create',{title:$('pt').value,description:$('pd').value,price:+$('pp').value});closeModal();loadProducts();toast('Товар выставлен!')}catch(e){toast(e.message)}}
load().catch(e=>toast(e.message));setInterval(()=>{if($('chat').classList.contains('on'))loadChat()},5000);
</script></body></html>'''

def handle_user(h):return current_user(h)
class Handler(BaseHTTPRequestHandler):
    def send_json(self,o,status=200):
        b=j(o);self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Access-Control-Allow-Origin','*');self.end_headers();self.wfile.write(b)
    def do_OPTIONS(self):self.send_response(204);self.send_header('Access-Control-Allow-Origin','*');self.send_header('Access-Control-Allow-Headers','Content-Type,X-Telegram-Init-Data');self.send_header('Access-Control-Allow-Methods','GET,POST,OPTIONS');self.end_headers()
    def do_GET(self):
        p=urlparse(self.path).path
        if p in ('/','/index.html'):b=HTML.encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(b)
        elif p=='/health':self.send_json({'ok':True,'app':'NeuroCity','version':'2.0'})
        else:self.send_error(404)
    def do_POST(self):
        try:
            p=urlparse(self.path).path;u=handle_user(self);d=body(self)
            with LOCK:
                c=db(); now=int(time.time())
                if p=='/api/me':
                    rank=c.execute('SELECT COUNT(*)+1 n FROM users WHERE coins>(SELECT coins FROM users WHERE id=?)',(u['id'],)).fetchone()['n'];self.send_json({'user':u,'rank':rank});return
                if p=='/api/feed':
                    bs=c.execute('SELECT b.name,u.name owner FROM businesses b JOIN users u ON u.id=b.owner_id ORDER BY b.id DESC LIMIT 8').fetchall();items=[{'title':'🏢 Новый бизнес','text':f'{r["owner"]} открыл «{r["name"]}»'} for r in bs];self.send_json({'items':items});return
                if p=='/api/businesses':
                    rows=c.execute('SELECT b.*,u.name owner_name FROM businesses b JOIN users u ON u.id=b.owner_id ORDER BY b.id DESC').fetchall();self.send_json({'items':[dict(r) for r in rows]});return
                if p=='/api/business/create':
                    name=str(d.get('name','')).strip();cat=str(d.get('category','')).strip();desc=str(d.get('description','')).strip();cap=max(50,int(d.get('capital',50)));jt=str(d.get('job_title','')).strip();jr=max(1,int(d.get('job_reward',1)))
                    if not name or not cat or not desc:raise ValueError('Заполни название, категорию и описание.')
                    if cap>u['coins']:raise ValueError('Не хватает монет.')
                    c.execute('INSERT INTO businesses(owner_id,name,category,description,capital,created_at) VALUES(?,?,?,?,?,?)',(u['id'],name,cat,desc,cap,now));bid=c.lastrowid
                    if jt:c.execute('INSERT INTO jobs(business_id,title,reward,slots,salary,created_at) VALUES(?,?,?,?,?,?)',(bid,jt,jr,5,jr,now))
                    c.execute('UPDATE users SET coins=coins-?,xp=xp+150 WHERE id=?',(cap,u['id']));c.commit();self.send_json({'ok':True});return
                if p=='/api/business/view':
                    bid=int(d['id']);b=c.execute('SELECT b.*,u.id owner_id,u.name owner FROM businesses b JOIN users u ON u.id=b.owner_id WHERE b.id=?',(bid,)).fetchone();
                    if not b:raise ValueError('Бизнес не найден')
                    comments=c.execute('SELECT c.*,u.name FROM comments c JOIN users u ON u.id=c.user_id WHERE c.business_id=? ORDER BY c.id DESC LIMIT 20',(bid,)).fetchall();following=bool(c.execute('SELECT 1 FROM follows WHERE follower_id=? AND target_id=?',(u['id'],b['owner_id'])).fetchone());self.send_json({'business':dict(b),'owner':{'id':b['owner_id'],'name':b['owner']},'following':following,'comments':[dict(x) for x in comments]});return
                if p=='/api/business/review':
                    bid=int(d['id']);rating=max(1,min(5,int(d.get('rating',5))));text=str(d.get('text','')).strip();
                    if not text:raise ValueError('Напиши текст отзыва')
                    c.execute('INSERT INTO comments(business_id,user_id,text,created_at) VALUES(?,?,?,?)',(bid,u['id'],text,now));c.execute('INSERT INTO business_reviews(business_id,user_id,rating,text,created_at) VALUES(?,?,?,?,?)',(bid,u['id'],rating,text,now));avg=c.execute('SELECT AVG(rating) a FROM business_reviews WHERE business_id=?',(bid,)).fetchone()['a'];c.execute('UPDATE businesses SET rating=? WHERE id=?',(avg,bid));c.commit();self.send_json({'ok':True});return
                if p=='/api/business/rating':rows=c.execute('SELECT b.*,u.name owner_name FROM businesses b JOIN users u ON u.id=b.owner_id ORDER BY rating DESC,level DESC LIMIT 30').fetchall();self.send_json({'items':[dict(x) for x in rows]});return
                if p=='/api/jobs':rows=c.execute('SELECT j.*,b.name business_name FROM jobs j JOIN businesses b ON b.id=j.business_id WHERE j.slots>0 ORDER BY j.id DESC').fetchall();self.send_json({'items':[dict(x) for x in rows]});return
                if p=='/api/work':
                    jid=int(d['job_id']);job=c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone();
                    if not job or job['slots']<=0:raise ValueError('Вакансия закрыта')
                    if c.execute('SELECT 1 FROM work WHERE job_id=? AND user_id=?',(jid,u['id'])).fetchone():raise ValueError('Ты уже выполнял эту работу')
                    c.execute('INSERT INTO work(job_id,user_id,created_at) VALUES(?,?,?)',(jid,u['id'],now));c.execute('UPDATE jobs SET slots=slots-1 WHERE id=?',(jid,));c.execute('UPDATE users SET coins=coins+?,xp=xp+40 WHERE id=?',(job['reward'],u['id']));c.commit();self.send_json({'ok':True,'message':f'+{job["reward"]} 🪙 и +40 XP'});return
                if p=='/api/products':rows=c.execute('SELECT p.*,u.name seller_name FROM products p JOIN users u ON u.id=p.seller_id WHERE active=1 ORDER BY id DESC').fetchall();self.send_json({'items':[dict(x) for x in rows]});return
                if p=='/api/product/create':
                    title=str(d.get('title','')).strip();desc=str(d.get('description','')).strip();price=int(d.get('price',0));
                    if not title or not desc or price<1:raise ValueError('Заполни товар и цену')
                    c.execute('INSERT INTO products(seller_id,title,description,price,created_at) VALUES(?,?,?,?,?)',(u['id'],title,desc,price,now));c.commit();self.send_json({'ok':True});return
                if p=='/api/buy':
                    pid=int(d['product_id']);pr=c.execute('SELECT * FROM products WHERE id=? AND active=1',(pid,)).fetchone();
                    if not pr:raise ValueError('Товар недоступен')
                    if pr['seller_id']==u['id']:raise ValueError('Нельзя купить свой товар')
                    if u['coins']<pr['price']:raise ValueError('Не хватает монет')
                    c.execute('UPDATE users SET coins=coins-?,xp=xp+10 WHERE id=?',(pr['price'],u['id']));c.execute('UPDATE users SET coins=coins+?,xp=xp+10 WHERE id=?',(pr['price'],pr['seller_id']));c.execute('UPDATE products SET active=0 WHERE id=?',(pid,));c.execute('INSERT INTO purchases(product_id,buyer_id,seller_id,price,created_at) VALUES(?,?,?,?,?)',(pid,u['id'],pr['seller_id'],pr['price'],now));c.execute('INSERT INTO inventory(user_id,item,qty) VALUES(?,?,1)',(u['id'],pr['title']));c.commit();self.send_json({'ok':True,'message':f'Куплено за {pr["price"]} 🪙'});return
                if p=='/api/rating':
                    col='xp' if d.get('kind')=='xp' else 'coins';rows=c.execute(f'SELECT id,name,username,coins,xp,level FROM users ORDER BY {col} DESC LIMIT 30').fetchall();self.send_json({'items':[dict(x) for x in rows]});return
                if p=='/api/chat':rows=c.execute('SELECT ch.*,u.name FROM chat ch JOIN users u ON u.id=ch.user_id ORDER BY ch.id DESC LIMIT 100').fetchall();self.send_json({'items':[dict(x) for x in reversed(rows)]});return
                if p=='/api/chat/send':
                    text=str(d.get('text','')).strip();
                    if not text or len(text)>500:raise ValueError('Сообщение пустое или слишком длинное')
                    c.execute('INSERT INTO chat(user_id,text,created_at) VALUES(?,?,?)',(u['id'],text,now));c.commit();self.send_json({'ok':True});return
                if p=='/api/follow':
                    tid=int(d['target_id']);ex=c.execute('SELECT 1 FROM follows WHERE follower_id=? AND target_id=?',(u['id'],tid)).fetchone()
                    if ex:c.execute('DELETE FROM follows WHERE follower_id=? AND target_id=?',(u['id'],tid));following=False
                    else:c.execute('INSERT OR IGNORE INTO follows VALUES(?,?,?)',(u['id'],tid,now));following=True
                    c.commit();self.send_json({'following':following});return
                if p=='/api/bonus':
                    if now-u['last_bonus']<20*3600:raise ValueError('Бонус уже забран. Возвращайся завтра!')
                    streak=u['streak']+1;reward=min(500,100+streak*25);c.execute('UPDATE users SET coins=coins+?,xp=xp+50,streak=?,last_bonus=? WHERE id=?',(reward,streak,now,u['id']));c.commit();self.send_json({'message':f'+{reward} 🪙 и +50 XP'});return
                if p=='/api/profile':
                    a=[('first_business','Первый бизнес','Создай свой первый бизнес'),('worker','Трудяга','Выполни 3 работы'),('trader','Торговец','Совершить покупку'),('rich','Капиталист','Накопить 5000 🪙')];done=[]
                    for code,title,txt in a:
                        if code=='first_business':ok=bool(c.execute('SELECT 1 FROM businesses WHERE owner_id=?',(u['id'],)).fetchone())
                        elif code=='worker':ok=c.execute('SELECT COUNT(*) n FROM work WHERE user_id=?',(u['id'],)).fetchone()['n']>=3
                        elif code=='trader':ok=bool(c.execute('SELECT 1 FROM purchases WHERE buyer_id=?',(u['id'],)).fetchone())
                        else:ok=u['coins']>=5000
                        done.append({'title':title,'text':txt,'done':ok})
                    inv=c.execute('SELECT item,qty FROM inventory WHERE user_id=? ORDER BY id DESC',(u['id'],)).fetchall();self.send_json({'user':u,'achievements':done,'inventory':[dict(x) for x in inv]});return
                if p=='/api/bank':self.send_json({'bank':u['bank'],'coins':u['coins']});return
                if p=='/api/bank/move':
                    amt=max(1,int(d.get('amount',0)));typ=d.get('type');
                    if typ=='deposit':
                        if amt>u['coins']:raise ValueError('Недостаточно монет');c.execute('UPDATE users SET coins=coins-?,bank=bank+? WHERE id=?',(amt,amt,u['id']))
                    else:
                        if amt>u['bank']:raise ValueError('Недостаточно средств в банке');c.execute('UPDATE users SET bank=bank-?,coins=coins+? WHERE id=?',(amt,amt,u['id']))
                    c.commit();self.send_json({'ok':True});return
                self.send_json({'error':'not found'},404)
        except Exception as e:self.send_json({'error':str(e)},400)
    def log_message(self,fmt,*args):print('[WEB]',fmt%args)

def tg_loop():
    if not BOT_TOKEN:return
    import urllib.request
    try:urllib.request.urlopen(f'https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true',timeout=10).read()
    except:pass
    offset=0
    while True:
        try:
            req=urllib.request.Request(f'https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?timeout=25&offset={offset}')
            data=json.loads(urllib.request.urlopen(req,timeout=35).read().decode())
            for up in data.get('result',[]):
                offset=up['update_id']+1;m=up.get('message',{});chat=m.get('chat',{}).get('id');text=m.get('text','')
                if chat and text.startswith('/start'):
                    url=os.getenv('WEB_APP_URL','')
                    markup={'inline_keyboard':[[{'text':'🚀 Открыть NeuroCity','web_app':{'url':url}}]]} if url else None
                    payload={'chat_id':chat,'text':'🌐 Добро пожаловать в NeuroCity!\n\nСтрой бизнес, работай, торгуй и поднимайся в рейтинге города.','reply_markup':markup} if markup else {'chat_id':chat,'text':'NeuroCity запущен. Укажи WEB_APP_URL.'}
                    r=urllib.request.Request(f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'});urllib.request.urlopen(r,timeout=10).read()
        except Exception as e:print('[TG]',e);time.sleep(2)

def main():
    init_db();print('NeuroCity 2.0 on',HOST,PORT);threading.Thread(target=lambda:ThreadingHTTPServer((HOST,PORT),Handler).serve_forever(),daemon=True).start();tg_loop()
if __name__=='__main__':main()
