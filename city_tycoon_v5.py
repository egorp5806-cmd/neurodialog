# -*- coding: utf-8 -*-
import os,json,time,random,hmac,hashlib,urllib.parse,urllib.request,threading
from flask import Flask,request,jsonify,Response
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor,Json

BOT_TOKEN=os.getenv('BOT_TOKEN',''); DATABASE_URL=os.getenv('DATABASE_URL',''); WEB_APP_URL=os.getenv('WEB_APP_URL','')
ADMIN_IDS={int(x.strip()) for x in os.getenv('ADMIN_IDS','').split(',') if x.strip().isdigit()}
DEMO=os.getenv('ALLOW_BROWSER_DEMO','false').lower()=='true'; MAXAGE=int(os.getenv('INIT_DATA_MAX_AGE','86400')); PORT=int(os.getenv('PORT','10000'))
if not DATABASE_URL: raise RuntimeError('DATABASE_URL is not set.')
app=Flask(__name__); pool=ThreadedConnectionPool(1,int(os.getenv('DB_POOL_MAX','12')),DATABASE_URL)

B=[
('СТАРТ','start',0,''),('Сосновая','property',600,'green'),('Шанс','chance',0,''),('Лазурная','property',700,'green'),('Налог города','tax',500,''),('Метро Север','station',1200,''),('Озерная','property',900,'blue'),('Шанс','chance',0,''),('Центральная','property',1000,'blue'),('Речная','property',1100,'blue'),('Парк отдыха','free',0,''),('Неоновая','property',1300,'pink'),('Электростанция','utility',1500,''),('Фестивальная','property',1400,'pink'),('Башенная','property',1500,'pink'),('Метро Юг','station',1200,''),('Кленовая','property',1700,'orange'),('Шанс','chance',0,''),('Солнечная','property',1800,'orange'),('Марсовая','property',1900,'orange'),('Свободная площадь','free',0,''),('Вишневая','property',2100,'red'),('Шанс','chance',0,''),('Городская','property',2200,'red'),('Имперская','property',2300,'red'),('Метро Восток','station',1200,''),('Космическая','property',2500,'yellow'),('Садовая','property',2600,'yellow'),('Водоканал','utility',1500,''),('Панорамная','property',2700,'yellow'),('Штрафная зона','jail',0,''),('Алмазная','property',2900,'purple'),('Риверсайд','property',3000,'purple'),('Шанс','chance',0,''),('Империал Парк','property',3200,'purple'),('Метро Запад','station',1200,''),('Событие','chance',0,''),('Небесная','property',3500,'black'),('Налог на роскошь','tax',1000,''),('Метрополис','property',4000,'black')]
COL={'green':'#34d399','blue':'#60a5fa','pink':'#f472b6','orange':'#fb923c','red':'#f87171','yellow':'#facc15','purple':'#c084fc','black':'#94a3b8'}
RENT={'property':[60,120,360,900,1600,2500],'station':[100,200,400,800,1600,3200],'utility':[120,240,480,960,1920,3840]}

CHANCE_CARDS=[
 ('Городской грант',1800,'self'),('Ремонт дорог',-700,'self'),('Удачная сделка',1200,'self'),('Штраф за парковку',-500,'self'),('Инвестор',2500,'self'),('Авария',-1200,'self'),('Дивиденды соседей',900,'self'),('Муниципальный бонус',1400,'self')
]
BADGES={
 'first_roll':'🎲 Первый ход','double':'⚡ Дубль','builder':'🏗️ Строитель','collector':'🏠 Коллекционер','rich':'💎 Капиталист','auction':'🔨 Аукционист','jailbreak':'🚔 Освобождение'
}


def conn(): return pool.getconn()
def put(c): pool.putconn(c)
def initdb():
 c=conn()
 try:
  with c.cursor() as x:
   x.execute('CREATE TABLE IF NOT EXISTS players(user_id BIGINT PRIMARY KEY,name TEXT,last_seen TIMESTAMPTZ DEFAULT now())')
   x.execute('CREATE TABLE IF NOT EXISTS rooms(code TEXT PRIMARY KEY,host_id BIGINT,status TEXT DEFAULT \'waiting\',turn INT DEFAULT 0,state JSONB DEFAULT \'{}\',updated_at TIMESTAMPTZ DEFAULT now())')
   x.execute('''CREATE TABLE IF NOT EXISTS room_players(room_code TEXT REFERENCES rooms(code) ON DELETE CASCADE,user_id BIGINT REFERENCES players(user_id),slot INT,name TEXT,money BIGINT DEFAULT 15000,pos INT DEFAULT 0,props JSONB DEFAULT '[]',houses JSONB DEFAULT '{}',bankrupt BOOL DEFAULT false,avatar TEXT DEFAULT '🧑‍💼',xp BIGINT DEFAULT 0,wins INT DEFAULT 0,PRIMARY KEY(room_code,user_id),UNIQUE(room_code,slot))''')
   x.execute('''CREATE TABLE IF NOT EXISTS room_messages(id BIGSERIAL PRIMARY KEY,room_code TEXT REFERENCES rooms(code) ON DELETE CASCADE,user_id BIGINT REFERENCES players(user_id),name TEXT,message TEXT,created_at TIMESTAMPTZ DEFAULT now())''')
   x.execute('''CREATE TABLE IF NOT EXISTS trades(id BIGSERIAL PRIMARY KEY,room_code TEXT REFERENCES rooms(code) ON DELETE CASCADE,from_user BIGINT REFERENCES players(user_id),to_user BIGINT REFERENCES players(user_id),offer_money BIGINT DEFAULT 0,want_money BIGINT DEFAULT 0,offer_props JSONB DEFAULT '[]',want_props JSONB DEFAULT '[]',status TEXT DEFAULT 'pending',created_at TIMESTAMPTZ DEFAULT now())''')
   x.execute('CREATE INDEX IF NOT EXISTS idx_room_messages_code ON room_messages(room_code,id)')
   x.execute('CREATE INDEX IF NOT EXISTS idx_trades_room_status ON trades(room_code,status)')
   x.execute('''CREATE TABLE IF NOT EXISTS required_channels(id BIGSERIAL PRIMARY KEY,chat_id TEXT UNIQUE NOT NULL,username TEXT,title TEXT NOT NULL,invite_url TEXT,active BOOL DEFAULT true,created_at TIMESTAMPTZ DEFAULT now())''')
   x.execute("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now()")
   x.execute("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS turn_started_at BIGINT DEFAULT 0")
   x.execute("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS max_turns INT DEFAULT 0")
   x.execute("ALTER TABLE room_players ADD COLUMN IF NOT EXISTS jail_turns INT DEFAULT 0")
   x.execute("ALTER TABLE room_players ADD COLUMN IF NOT EXISTS jailed BOOL DEFAULT false")
   x.execute("ALTER TABLE room_players ADD COLUMN IF NOT EXISTS mortgages JSONB DEFAULT '{}'")
   x.execute("ALTER TABLE room_players ADD COLUMN IF NOT EXISTS badges JSONB DEFAULT '[]'")
   x.execute("CREATE TABLE IF NOT EXISTS room_auctions(id BIGSERIAL PRIMARY KEY,room_code TEXT REFERENCES rooms(code) ON DELETE CASCADE,cell_id INT NOT NULL,started_by BIGINT,ends_at BIGINT NOT NULL,status TEXT DEFAULT 'open',winner BIGINT,bid BIGINT DEFAULT 0)")
   x.execute("CREATE TABLE IF NOT EXISTS auction_bids(id BIGSERIAL PRIMARY KEY,auction_id BIGINT REFERENCES room_auctions(id) ON DELETE CASCADE,user_id BIGINT,bid BIGINT,created_at BIGINT)")
   x.execute("CREATE INDEX IF NOT EXISTS idx_auctions_room_status ON room_auctions(room_code,status)")
   x.execute("ALTER TABLE room_players ADD COLUMN IF NOT EXISTS avatar TEXT DEFAULT '🧑‍💼'")
   x.execute("ALTER TABLE room_players ADD COLUMN IF NOT EXISTS xp BIGINT DEFAULT 0")
   x.execute("ALTER TABLE room_players ADD COLUMN IF NOT EXISTS wins INT DEFAULT 0")
  c.commit()
 finally: put(c)

def tg_user():
 s=request.headers.get('X-Telegram-Init-Data','')
 if s and BOT_TOKEN:
  try:
   d=urllib.parse.parse_qs(s,keep_blank_values=True); hh=d.pop('hash')[0]; check='\n'.join(f'{k}={d[k][0]}' for k in sorted(d)); sec=hmac.new(b'WebAppData',BOT_TOKEN.encode(),hashlib.sha256).digest(); calc=hmac.new(sec,check.encode(),hashlib.sha256).hexdigest(); ad=int(d.get('auth_date',['0'])[0])
   if hmac.compare_digest(calc,hh) and time.time()-ad<=MAXAGE:
    u=json.loads(d['user'][0]); return int(u['id']),u.get('username') or u.get('first_name') or 'Player'
  except Exception: pass
 if DEMO:return 1000000001,'Demo Player'
 return None,None

def is_admin(uid):
 return bool(uid and uid in ADMIN_IDS)

def bot_api(method,data=None):
 if not BOT_TOKEN:return None
 try:
  req=urllib.request.Request(f'https://api.telegram.org/bot{BOT_TOKEN}/{method}',data=json.dumps(data or {}).encode(),headers={'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=12) as r:return json.loads(r.read().decode())
 except Exception as e:
  print('[Telegram]',method,e); return None

def required_channels(active_only=True):
 c=conn()
 try:
  with c.cursor(cursor_factory=RealDictCursor) as x:
   x.execute('SELECT id,chat_id,username,title,invite_url,active FROM required_channels '+('WHERE active=true ' if active_only else '')+'ORDER BY id')
   return [dict(r) for r in x.fetchall()]
 finally:put(c)

def subscription_status(uid):
 result=[]
 for ch in required_channels():
  r=bot_api('getChatMember',{'chat_id':ch['chat_id'],'user_id':uid}); ok=False; status='unknown'
  if r and r.get('ok'):
   status=r.get('result',{}).get('status','')
   ok=status in ('creator','administrator','member') or (status=='restricted' and r.get('result',{}).get('is_member',False))
  result.append({**ch,'subscribed':ok,'status':status})
 return {'ok':all(x['subscribed'] for x in result),'channels':result}

def subscription_gate(uid):
 if not uid or is_admin(uid): return None
 st=subscription_status(uid)
 return None if st['ok'] else st

def auth():
 uid,name=tg_user()
 if uid:
  c=conn()
  try:
   with c.cursor() as x:x.execute('INSERT INTO players(user_id,name) VALUES(%s,%s) ON CONFLICT(user_id) DO UPDATE SET name=EXCLUDED.name,last_seen=now()',(uid,name))
   c.commit()
  finally:put(c)
 return uid,name

def code():
 while 1:
  s=''.join(random.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(6)); c=conn()
  try:
   with c.cursor() as x:x.execute('SELECT 1 FROM rooms WHERE code=%s',(s,));
   if not x.fetchone(): return s
  finally:put(c)

def snapshot(code,uid):
 c=conn()
 try:
  with c.cursor(cursor_factory=RealDictCursor) as x:
   x.execute('SELECT * FROM rooms WHERE code=%s',(code,)); r=x.fetchone()
   if not r:return None
   x.execute('SELECT user_id,slot,name,money,pos,props,houses,bankrupt,avatar,xp,wins,jail_turns,jailed,mortgages,badges FROM room_players WHERE room_code=%s ORDER BY slot',(code,)); ps=x.fetchall()
   x.execute('SELECT id,user_id,name,message,created_at FROM room_messages WHERE room_code=%s ORDER BY id DESC LIMIT 50',(code,)); msgs=x.fetchall()
   x.execute("SELECT id,from_user,to_user,offer_money,want_money,offer_props,want_props,status FROM trades WHERE room_code=%s AND status='pending' ORDER BY id DESC LIMIT 20",(code,)); trades=x.fetchall()
   board=[{'id':i,'name':n,'type':t,'price':p,'group':g} for i,(n,t,p,g) in enumerate(B)]
   return {'code':code,'host_id':r['host_id'],'status':r['status'],'turn':r['turn'],'state':r['state'] or {},'players':ps,'board':board,'colors':COL,'me':uid,'messages':msgs,'trades':trades}
 finally:put(c)

def owner(x,code,pid):
 x.execute("SELECT user_id FROM room_players WHERE room_code=%s AND props ? %s",(code,str(pid))); r=x.fetchone(); return int(r['user_id']) if r else None

def rent(x,code,pid,uid):
 o=owner(x,code,pid)
 if not o or o==uid:return 0,None
 x.execute('SELECT props,houses FROM room_players WHERE room_code=%s AND user_id=%s',(code,o)); r=x.fetchone(); props=r['props'] or []; houses=r['houses'] or {}; p=B[pid]; lev=int(houses.get(str(pid),0))
 if p[1]=='station':return 100*(2**max(0,sum(B[int(q)][1]=='station' for q in props)-1)),o
 if p[1]=='utility':return (500 if sum(B[int(q)][1]=='utility' for q in props)==2 else 240),o
 return RENT['property'][min(lev,5)],o

@app.before_request
def enforce_subscription():
 if request.path.startswith('/api/') and request.path not in ('/api/subscription','/api/subscription/check') and not request.path.startswith('/api/admin/'):
  u,n=tg_user()
  if u and not is_admin(u):
   gate=subscription_gate(u)
   if gate:return jsonify(error='Нужно подписаться на обязательные каналы',subscription_required=True,**gate),403
@app.get('/')
def home():return Response(HTML,mimetype='text/html')
@app.get('/health')
def health():
 c=conn()
 try:
  with c.cursor() as x:x.execute('SELECT 1')
  return jsonify(ok=True,game='City Tycoon')
 finally:put(c)
@app.get('/api/me')
def me():
 u,n=auth()
 if not u:return jsonify(error='Telegram authorization required'),401
 gate=subscription_gate(u)
 if gate:return jsonify(error='Нужно подписаться на обязательные каналы',subscription_required=True,**gate),403
 return jsonify(user_id=u,name=n,is_admin=is_admin(u))

@app.get('/api/subscription')
def subscription():
 u,n=auth()
 if not u:return jsonify(error='Telegram authorization required'),401
 return jsonify(subscription_status(u))

@app.post('/api/subscription/check')
def subscription_check():
 u,n=auth()
 if not u:return jsonify(error='Telegram authorization required'),401
 return jsonify(subscription_status(u))

@app.get('/api/admin/channels')
def admin_channels():
 u,n=auth()
 if not is_admin(u):return jsonify(error='Доступ только для администратора'),403
 return jsonify(channels=required_channels(False))

@app.post('/api/admin/channels')
def admin_add_channel():
 u,n=auth()
 if not is_admin(u):return jsonify(error='Доступ только для администратора'),403
 d=request.json or {}; raw=str(d.get('chat_id','')).strip(); title=str(d.get('title','')).strip(); invite=str(d.get('invite_url','')).strip()
 chat_id=raw
 if not chat_id:return jsonify(error='Укажи @username или numeric chat_id'),400
 info=bot_api('getChat',{'chat_id':chat_id})
 if not info or not info.get('ok'):return jsonify(error='Бот не видит канал. Добавь бота в канал и проверь @username/chat_id.'),400
 chat=info['result']; chat_id=str(chat.get('id')); title=title or chat.get('title') or chat_id
 if not invite and chat.get('username'): invite='https://t.me/'+chat['username']
 c=conn()
 try:
  with c.cursor() as x:x.execute('INSERT INTO required_channels(chat_id,username,title,invite_url,active) VALUES(%s,%s,%s,%s,true) ON CONFLICT(chat_id) DO UPDATE SET username=EXCLUDED.username,title=EXCLUDED.title,invite_url=EXCLUDED.invite_url,active=true',(chat_id,chat.get('username') or '',title,invite))
  c.commit();return jsonify(ok=True,channels=required_channels(False))
 finally:put(c)

@app.delete('/api/admin/channels/<int:cid>')
def admin_delete_channel(cid):
 u,n=auth()
 if not is_admin(u):return jsonify(error='Доступ только для администратора'),403
 c=conn()
 try:
  with c.cursor() as x:x.execute('DELETE FROM required_channels WHERE id=%s',(cid,))
  c.commit();return jsonify(ok=True,channels=required_channels(False))
 finally:put(c)

@app.post('/api/admin/channels/<int:cid>/toggle')
def admin_toggle_channel(cid):
 u,n=auth()
 if not is_admin(u):return jsonify(error='Доступ только для администратора'),403
 c=conn()
 try:
  with c.cursor() as x:x.execute('UPDATE required_channels SET active=NOT active WHERE id=%s RETURNING active',(cid,)); r=x.fetchone()
  if not r:return jsonify(error='Канал не найден'),404
  c.commit();return jsonify(ok=True,channels=required_channels(False))
 finally:put(c)

@app.get('/api/admin/stats')
def admin_stats():
 u,n=auth()
 if not is_admin(u):return jsonify(error='Доступ только для администратора'),403
 c=conn()
 try:
  with c.cursor() as x:
   x.execute('SELECT COUNT(*) FROM players'); players=x.fetchone()[0]
   x.execute("SELECT COUNT(*) FROM rooms WHERE status='waiting'"); rooms=x.fetchone()[0]
   x.execute("SELECT COUNT(*) FROM rooms WHERE status='playing'"); games=x.fetchone()[0]
  return jsonify(players=players,waiting_rooms=rooms,playing_games=games)
 finally:put(c)
@app.post('/api/rooms')
def create():
 u,n=auth()
 if not u:return jsonify(error='Telegram authorization required'),401
 cd=code();c=conn()
 try:
  with c.cursor() as x:
   x.execute('INSERT INTO rooms(code,host_id,state) VALUES(%s,%s,%s)',(cd,u,Json({'log':[f'{n} создал комнату']})))
   x.execute('INSERT INTO room_players(room_code,user_id,slot,name,avatar) VALUES(%s,%s,0,%s,%s)',(cd,u,n,'🧑‍💼'))
  c.commit();return jsonify(snapshot(cd,u))
 finally:put(c)
@app.get('/api/rooms/list')
def rooms_list():
 u,n=auth()
 if not u:return jsonify(error='Telegram authorization required'),401
 c=conn()
 try:
  with c.cursor(cursor_factory=RealDictCursor) as x:
   x.execute('''SELECT r.code,r.host_id,r.created_at,r.updated_at,
                       COUNT(rp.user_id) AS players,
                       MAX(CASE WHEN rp.slot=0 THEN rp.name END) AS host_name
                FROM rooms r
                LEFT JOIN room_players rp ON rp.room_code=r.code
                WHERE r.status='waiting'
                GROUP BY r.code,r.host_id,r.created_at,r.updated_at
                HAVING COUNT(rp.user_id) < 6
                ORDER BY r.updated_at DESC
                LIMIT 30''')
   rows=x.fetchall()
   return jsonify(rooms=[dict(r) for r in rows])
 finally:put(c)

@app.post('/api/rooms/join')
def join():
 u,n=auth(); cd=str((request.json or {}).get('code','')).upper()
 if not u:return jsonify(error='Telegram authorization required'),401
 c=conn()
 try:
  with c.cursor(cursor_factory=RealDictCursor) as x:
   x.execute('SELECT * FROM rooms WHERE code=%s FOR UPDATE',(cd,));r=x.fetchone()
   if not r:return jsonify(error='Комната не найдена'),404
   if r['status']!='waiting':return jsonify(error='Игра уже началась'),400
   x.execute('SELECT COUNT(*) n FROM room_players WHERE room_code=%s',(cd,));nplayers=x.fetchone()['n']
   if nplayers>=6:return jsonify(error='Комната заполнена'),400
   x.execute('INSERT INTO room_players(room_code,user_id,slot,name,avatar) VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',(cd,u,nplayers,n,'🧑‍💼'))
  c.commit();return jsonify(snapshot(cd,u))
 finally:put(c)
@app.post('/api/rooms/start')
def start():
 u,n=auth();cd=str((request.json or {}).get('code','')).upper();c=conn()
 try:
  with c.cursor(cursor_factory=RealDictCursor) as x:
   x.execute('SELECT * FROM rooms WHERE code=%s FOR UPDATE',(cd,));r=x.fetchone()
   if not r:return jsonify(error='Комната не найдена'),404
   if int(r['host_id'])!=u:return jsonify(error='Только создатель может начать'),403
   x.execute('SELECT COUNT(*) n FROM room_players WHERE room_code=%s',(cd,));nplayers=x.fetchone()['n']
   if nplayers<2:return jsonify(error='Нужно минимум 2 игрока'),400
   st=dict(r['state'] or {});st['log']=(st.get('log') or [])+['🎲 Игра началась!'];x.execute("UPDATE rooms SET status='playing',state=%s WHERE code=%s",(Json(st),cd))
  c.commit();return jsonify(snapshot(cd,u))
 finally:put(c)
@app.get('/api/rooms/<cd>')
def get(cd):
 u,n=auth();s=snapshot(cd.upper(),u) if u else None
 return (jsonify(s) if s else (jsonify(error='Комната не найдена'),404))
@app.post('/api/rooms/roll')
def roll():
 u,n=auth();cd=str((request.json or {}).get('code','')).upper();c=conn()
 try:
  with c.cursor(cursor_factory=RealDictCursor) as x:
   x.execute('SELECT * FROM rooms WHERE code=%s FOR UPDATE',(cd,));r=x.fetchone()
   if not r:return jsonify(error='Комната не найдена'),404
   if r['status']!='playing':return jsonify(error='Игра не активна'),400
   x.execute('SELECT * FROM room_players WHERE room_code=%s ORDER BY slot',(cd,));ps=x.fetchall()
   idx=int(r['turn']);a=ps[idx%len(ps)]
   if int(a['user_id'])!=u:return jsonify(error='Сейчас ход другого игрока'),400
   if a['bankrupt']:return jsonify(error='Вы банкрот'),400
   d1,d2=random.randint(1,6),random.randint(1,6);steps=d1+d2;old=int(a['pos']);new=(old+steps)%40;money=int(a['money'])+(2000 if new<old else 0)
   path=[(old+i)%40 for i in range(1,steps+1)]
   x.execute('UPDATE room_players SET pos=%s,money=%s,xp=xp+%s WHERE room_code=%s AND user_id=%s',(new,money,50+steps*5,cd,u))
   p=B[new];st=dict(r['state'] or {});log=list(st.get('log') or []);log.append(f"{a['name']} выбросил {d1}+{d2} и попал на «{p[0]}».")
   if new<old:log.append(f"{a['name']} получил 2000 🪙 за старт.")
   if p[1]=='tax':
    money=max(0,money-p[2]);x.execute('UPDATE room_players SET money=%s WHERE room_code=%s AND user_id=%s',(money,cd,u));log.append(f"Налог: -{p[2]} 🪙")
   elif p[1]=='chance':
    text,delta,_=random.choice(CHANCE_CARDS)
    money=max(0,money+delta);x.execute('UPDATE room_players SET money=%s WHERE room_code=%s AND user_id=%s',(money,cd,u));log.append(f"🎴 {text}: {'+' if delta>=0 else ''}{delta} 🪙")
   elif p[1] in ('property','station','utility'):
    o=owner(x,cd,new,u)
    if o and o!=u:
     rr,oid=rent(x,cd,new,u);paid=min(money,rr);money-=paid
     x.execute('UPDATE room_players SET money=%s WHERE room_code=%s AND user_id=%s',(money,cd,u));x.execute('UPDATE room_players SET money=money+%s WHERE room_code=%s AND user_id=%s',(paid,cd,oid));log.append(f"💸 Аренда: -{paid} 🪙")
     if paid<rr:
      x.execute('SELECT props,houses,mortgages FROM room_players WHERE room_code=%s AND user_id=%s FOR UPDATE',(cd,u)); bp=x.fetchone();
      if oid:
       x.execute('SELECT props,houses,mortgages FROM room_players WHERE room_code=%s AND user_id=%s FOR UPDATE',(cd,oid)); op=x.fetchone();
       pp=list(op['props'] or [])+[q for q in (bp['props'] or []) if q not in list(op['props'] or [])]; oh=dict(op['houses'] or {}); oh.update(bp['houses'] or {}); om=dict(op['mortgages'] or {}); om.update(bp['mortgages'] or {}); x.execute('UPDATE room_players SET props=%s,houses=%s,mortgages=%s WHERE room_code=%s AND user_id=%s',(Json(pp),Json(oh),Json(om),cd,oid))
      x.execute("UPDATE room_players SET bankrupt=true,props='[]',houses='{}',mortgages='{}' WHERE room_code=%s AND user_id=%s",(cd,u));log.append(f"💥 {a['name']} — банкрот, активы переданы кредитору.")
   # badges
   x.execute('SELECT badges FROM room_players WHERE room_code=%s AND user_id=%s FOR UPDATE',(cd,u,)); badges=list((x.fetchone() or {}).get('badges') or [])
   def badge(k):
    if k not in badges: badges.append(k)
   badge('first_roll')
   if d1==d2: badge('double')
   if p[1] in ('property','station','utility') and owner(x,cd,new,u): badge('collector')
   if len([q for q in (a['props'] or [])])>=4: badge('collector')
   x.execute('UPDATE room_players SET badges=%s WHERE room_code=%s AND user_id=%s',(Json(badges),cd,u))
   x.execute("SELECT COUNT(*) n FROM room_players WHERE room_code=%s AND bankrupt=false",(cd,));alive=int(x.fetchone()['n']);winner=None
   if alive<=1:
    x.execute("SELECT user_id,name FROM room_players WHERE room_code=%s AND bankrupt=false LIMIT 1",(cd,));wr=x.fetchone();winner=wr['name'] if wr else None
    if wr:x.execute("UPDATE room_players SET wins=wins+1,xp=xp+1000 WHERE room_code=%s AND user_id=%s",(cd,wr['user_id']))
    log.append(f"🏆 Победитель: {winner}" if winner else "🏁 Игра завершена.");status='finished';nxt=idx
   else:
    status='playing';nxt=idx if d1==d2 else (idx+1)%len(ps)
    for _ in range(len(ps)):
     if not ps[nxt]['bankrupt']:break
     nxt=(nxt+1)%len(ps)
   st['log']=log[-40:];st['last_roll']={'d1':d1,'d2':d2,'path':path,'from':old,'to':new,'player':u,'doubles':d1==d2,'ts':int(time.time())}
   if winner:st['winner']=winner
   x.execute('UPDATE rooms SET turn=%s,status=%s,state=%s,updated_at=now() WHERE code=%s',(nxt,status,Json(st),cd))
  c.commit();return jsonify(snapshot(cd,u))
 finally:put(c)
@app.post('/api/rooms/buy')
def buy():
 u,n=auth();body=request.json or {};cd=str(body.get('code','')).upper();pid=int(body.get('property_id',-1));p=B[pid] if 0<=pid<40 else None
 if not p or p[1] not in ('property','station','utility'):return jsonify(error='Эту клетку нельзя купить'),400
 c=conn()
 try:
  with c.cursor(cursor_factory=RealDictCursor) as x:
   x.execute('SELECT * FROM rooms WHERE code=%s FOR UPDATE',(cd,));r=x.fetchone();x.execute('SELECT * FROM room_players WHERE room_code=%s AND user_id=%s FOR UPDATE',(cd,u));me=x.fetchone()
   if not me:return jsonify(error='Вы не в комнате'),403
   if int(me['pos'])!=pid:return jsonify(error='Вы не на этом участке'),400
   if int(me['money'])<p[2]:return jsonify(error='Недостаточно денег'),400
   if owner(x,cd,pid):return jsonify(error='Участок уже куплен'),400
   props=list(me['props'] or []);props.append(pid);x.execute('UPDATE room_players SET money=money-%s,props=%s WHERE room_code=%s AND user_id=%s',(p[2],Json(props),cd,u));st=dict(r['state'] or {});log=list(st.get('log') or []);log.append(f'🏠 {n} купил «{p[0]}» за {p[2]} 🪙');x.execute('UPDATE rooms SET state=%s WHERE code=%s',(Json({'log':log[-30:]}),cd))
  c.commit();return jsonify(snapshot(cd,u))
 finally:put(c)
@app.post('/api/rooms/build')
def build():
 u,n=auth();body=request.json or {};cd=str(body.get('code','')).upper();pid=int(body.get('property_id',-1));p=B[pid] if 0<=pid<40 else None
 if not p or p[1]!='property':return jsonify(error='Здесь нельзя строить'),400
 cost=max(500,int(p[2]*.35));c=conn()
 try:
  with c.cursor(cursor_factory=RealDictCursor) as x:
   x.execute('SELECT * FROM rooms WHERE code=%s FOR UPDATE',(cd,));r=x.fetchone();x.execute('SELECT * FROM room_players WHERE room_code=%s AND user_id=%s FOR UPDATE',(cd,u));me=x.fetchone();props=[int(q) for q in (me['props'] or [])]
   if pid not in props:return jsonify(error='Сначала купите участок'),400
   hs=dict(me['houses'] or {});lev=int(hs.get(str(pid),0))
   if lev>=5:return jsonify(error='Максимальный уровень — 5'),400
   if int(me['money'])<cost:return jsonify(error=f'Нужно {cost} 🪙'),400
   hs[str(pid)]=lev+1; badges=list(me['badges'] or []); badges.append('builder') if 'builder' not in badges else None; x.execute('UPDATE room_players SET money=money-%s,houses=%s,badges=%s WHERE room_code=%s AND user_id=%s',(cost,Json(hs),Json(badges),cd,u));st=dict(r['state'] or {});log=list(st.get('log') or []);log.append(f'🏗️ {n} улучшил «{p[0]}» до уровня {lev+1}');x.execute('UPDATE rooms SET state=%s WHERE code=%s',(Json({'log':log[-30:]}),cd))
  c.commit();return jsonify(snapshot(cd,u))
 finally:put(c)


@app.post('/api/rooms/chat')
def chat():
 u,n=auth();body=request.json or {};cd=str(body.get('code','')).upper();msg=str(body.get('message','')).strip()
 if not u:return jsonify(error='Telegram authorization required'),401
 if not msg:return jsonify(error='Пустое сообщение'),400
 c=conn()
 try:
  with c.cursor() as x:
   x.execute('SELECT 1 FROM room_players WHERE room_code=%s AND user_id=%s',(cd,u))
   if not x.fetchone():return jsonify(error='Вы не в комнате'),403
   x.execute('INSERT INTO room_messages(room_code,user_id,name,message) VALUES(%s,%s,%s,%s)',(cd,u,n,msg[:240]))
  c.commit();return jsonify(snapshot(cd,u))
 finally:put(c)

@app.post('/api/rooms/trade')
def trade_offer():
 u,n=auth();b=request.json or {};cd=str(b.get('code','')).upper();to=int(b.get('to_user',0));om=max(0,int(b.get('offer_money',0)));wm=max(0,int(b.get('want_money',0)));op=[int(x) for x in (b.get('offer_props') or [])][:5];wp=[int(x) for x in (b.get('want_props') or [])][:5]
 if not u:return jsonify(error='Telegram authorization required'),401
 if to==u:return jsonify(error='Нельзя торговать с собой'),400
 c=conn()
 try:
  with c.cursor(cursor_factory=RealDictCursor) as x:
   x.execute('SELECT * FROM room_players WHERE room_code=%s AND user_id IN (%s,%s) FOR UPDATE',(cd,u,to));rows=x.fetchall()
   if len(rows)!=2:return jsonify(error='Игрок не найден'),404
   me=next(z for z in rows if int(z['user_id'])==u);other=next(z for z in rows if int(z['user_id'])==to);mp=[int(q) for q in (me['props'] or [])];tp=[int(q) for q in (other['props'] or [])]
   if om>int(me['money']) or wm>int(other['money']):return jsonify(error='Недостаточно денег для обмена'),400
   if any(q not in mp for q in op) or any(q not in tp for q in wp):return jsonify(error='Одна из улиц недоступна'),400
   x.execute('INSERT INTO trades(room_code,from_user,to_user,offer_money,want_money,offer_props,want_props) VALUES(%s,%s,%s,%s,%s,%s,%s)',(cd,u,to,om,wm,Json(op),Json(wp)))
  c.commit();return jsonify(snapshot(cd,u))
 finally:put(c)

@app.post('/api/rooms/trade/<int:tid>/accept')
def accept_trade(tid):
 u,n=auth();c=conn()
 try:
  with c.cursor(cursor_factory=RealDictCursor) as x:
   x.execute('SELECT * FROM trades WHERE id=%s FOR UPDATE',(tid,));t=x.fetchone()
   if not t:return jsonify(error='Предложение не найдено'),404
   if int(t['to_user'])!=u or t['status']!='pending':return jsonify(error='Предложение недоступно'),400
   cd=t['room_code'];a=int(t['from_user']);b=int(t['to_user']);x.execute('SELECT * FROM room_players WHERE room_code=%s AND user_id IN (%s,%s) FOR UPDATE',(cd,a,b));rows=x.fetchall()
   A=next(z for z in rows if int(z['user_id'])==a);BB=next(z for z in rows if int(z['user_id'])==b);om=int(t['offer_money']);wm=int(t['want_money']);op=[int(q) for q in (t['offer_props'] or [])];wp=[int(q) for q in (t['want_props'] or [])];ap=[int(q) for q in (A['props'] or [])];bp=[int(q) for q in (BB['props'] or [])]
   if int(A['money'])<om or int(BB['money'])<wm or any(q not in ap for q in op) or any(q not in bp for q in wp):return jsonify(error='Обмен больше нельзя выполнить'),400
   ap=[q for q in ap if q not in op]+wp;bp=[q for q in bp if q not in wp]+op;ah=dict(A['houses'] or {});bh=dict(BB['houses'] or {})
   for q in op:bh[str(q)]=ah.pop(str(q),0)
   for q in wp:ah[str(q)]=bh.pop(str(q),0)
   x.execute('UPDATE room_players SET money=money-%s+%s,props=%s,houses=%s WHERE room_code=%s AND user_id=%s',(om,wm,Json(ap),Json(ah),cd,a));x.execute('UPDATE room_players SET money=money-%s+%s,props=%s,houses=%s WHERE room_code=%s AND user_id=%s',(wm,om,Json(bp),Json(bh),cd,b));x.execute("UPDATE trades SET status='accepted' WHERE id=%s",(tid,));x.execute('INSERT INTO room_messages(room_code,user_id,name,message) VALUES(%s,%s,%s,%s)',(cd,u,n,'🤝 Обмен принят'))
  c.commit();return jsonify(snapshot(cd,u))
 finally:put(c)

@app.post('/api/rooms/trade/<int:tid>/reject')
def reject_trade(tid):
 u,n=auth();c=conn()
 try:
  with c.cursor() as x:x.execute("UPDATE trades SET status='rejected' WHERE id=%s AND to_user=%s AND status='pending'",(tid,u))
  c.commit();return jsonify(snapshot(str((request.json or {}).get('code','')).upper(),u))
 finally:put(c)

@app.post('/api/rooms/profile')
def room_profile():
 u,n=auth(); b=request.json or {}; cd=str(b.get('code','')).upper()
 avatar=str(b.get('avatar','🧑‍💼'))[:8]
 allowed=['🧑‍💼','🧑‍🚀','🧑‍🎨','🧑‍🔬','🧑‍💻','🧑‍🍳','🦊','🐯','🐼','🤖','👽','🦸']
 if avatar not in allowed:return jsonify(error='Недопустимый персонаж'),400
 c=conn()
 try:
  with c.cursor() as x:
   x.execute('UPDATE room_players SET avatar=%s WHERE room_code=%s AND user_id=%s',(avatar,cd,u))
  c.commit(); return jsonify(snapshot(cd,u))
 finally: put(c)

@app.get('/api/rooms/<cd>/leaderboard')
def leaderboard(cd):
 u,n=auth()
 if not u:return jsonify(error='Telegram authorization required'),401
 c=conn()
 try:
  with c.cursor(cursor_factory=RealDictCursor) as x:
   x.execute('SELECT user_id,name,money,props,houses,bankrupt,wins,xp,avatar FROM room_players WHERE room_code=%s ORDER BY money DESC',(cd.upper(),))
   rows=x.fetchall(); result=[]
   for r in rows:
    props=[int(q) for q in (r['props'] or [])]
    house_value=sum(max(500,int(B[i][2]*.35))*int((r['houses'] or {}).get(str(i),0)) for i in props if B[i][1]=='property')
    property_value=sum(int(B[i][2]) for i in props)
    result.append(dict(r)|{'net_worth':int(r['money'])+property_value+house_value})
   return jsonify(players=result)
 finally: put(c)


@app.post('/api/rooms/mortgage')
def mortgage():
 u,n=auth(); b=request.json or {}; cd=str(b.get('code','')).upper(); cell=int(b.get('cell',-1))
 c=conn()
 try:
  with c.cursor() as x:
   x.execute('SELECT money,props,mortgages FROM room_players WHERE room_code=%s AND user_id=%s FOR UPDATE',(cd,u)); p=x.fetchone()
   if not p:return jsonify(error='Игрок не найден'),404
   props=[int(q) for q in (p['props'] or [])]
   if cell not in props or B[cell][1] != 'property':return jsonify(error='Эту улицу нельзя заложить'),400
   houses=dict((p['houses'] or {}));
   if int(houses.get(str(cell),0))>0:return jsonify(error='Сначала продайте улучшения'),400
   mortgages=dict(p['mortgages'] or {})
   if mortgages.get(str(cell)):return jsonify(error='Улица уже заложена'),400
   value=max(1,int(B[cell][2]*0.5)); mortgages[str(cell)]=value
   x.execute('UPDATE room_players SET money=money+%s,mortgages=%s WHERE room_code=%s AND user_id=%s',(value,mortgages,cd,u))
  c.commit(); return jsonify(snapshot(cd,u))
 finally: put(c)

@app.post('/api/rooms/unmortgage')
def unmortgage():
 u,n=auth(); b=request.json or {}; cd=str(b.get('code','')).upper(); cell=int(b.get('cell',-1))
 c=conn()
 try:
  with c.cursor() as x:
   x.execute('SELECT money,mortgages FROM room_players WHERE room_code=%s AND user_id=%s FOR UPDATE',(cd,u)); p=x.fetchone()
   mortgages=dict(p['mortgages'] or {}) if p else {}
   value=int(mortgages.get(str(cell),0))
   if not value:return jsonify(error='Улица не заложена'),400
   cost=int(value*1.10)
   if int(p['money'])<cost:return jsonify(error='Недостаточно денег'),400
   mortgages.pop(str(cell),None)
   x.execute('UPDATE room_players SET money=money-%s,mortgages=%s WHERE room_code=%s AND user_id=%s',(cost,mortgages,cd,u))
  c.commit(); return jsonify(snapshot(cd,u))
 finally: put(c)

@app.post('/api/rooms/jail')
def jail_action():
 u,n=auth(); b=request.json or {}; cd=str(b.get('code','')).upper(); action=b.get('action')
 if action not in ('pay','skip'):return jsonify(error='Неверное действие'),400
 c=conn()
 try:
  with c.cursor() as x:
   x.execute('SELECT money,jail_turns,jailed FROM room_players WHERE room_code=%s AND user_id=%s FOR UPDATE',(cd,u)); p=x.fetchone()
   if not p or not p['jailed']:return jsonify(error='Игрок не в тюрьме'),400
   if action=='pay':
    if int(p['money'])<500:return jsonify(error='Нужно 500 🪙'),400
    x.execute('UPDATE room_players SET money=money-500,jailed=false,jail_turns=0 WHERE room_code=%s AND user_id=%s',(cd,u))
   else:
    turns=int(p['jail_turns'])+1
    if turns>=3:x.execute('UPDATE room_players SET jailed=false,jail_turns=0 WHERE room_code=%s AND user_id=%s',(cd,u))
    else:x.execute('UPDATE room_players SET jail_turns=%s WHERE room_code=%s AND user_id=%s',(turns,cd,u))
  c.commit(); return jsonify(snapshot(cd,u))
 finally: put(c)

@app.post('/api/rooms/auction')
def auction_create():
 u,n=auth(); b=request.json or {}; cd=str(b.get('code','')).upper(); cell=int(b.get('cell',-1))
 c=conn()
 try:
  with c.cursor() as x:
   x.execute("SELECT status FROM rooms WHERE code=%s",(cd,)); r=x.fetchone()
   if not r:return jsonify(error='Комната не найдена'),404
   if cell<0 or cell>=40 or B[cell][1] not in ('property','station','utility'):return jsonify(error='Эту клетку нельзя выставить'),400
   x.execute("SELECT 1 FROM room_players WHERE room_code=%s AND props @> %s::jsonb",(cd,'['+str(cell)+']')); owned=x.fetchone()
   if owned:return jsonify(error='Недвижимость уже принадлежит игроку'),400
   x.execute("SELECT id FROM room_auctions WHERE room_code=%s AND cell_id=%s AND status='open'",(cd,cell))
   if x.fetchone():return jsonify(error='Аукцион уже идёт'),400
   ends=int(time.time())+90
   x.execute("INSERT INTO room_auctions(room_code,cell_id,started_by,ends_at) VALUES(%s,%s,%s,%s) RETURNING id",(cd,cell,u,ends))
   aid=x.fetchone()['id']
  c.commit(); return jsonify(auction_id=aid,ends_at=ends)
 finally: put(c)

@app.post('/api/rooms/auction/bid')
def auction_bid():
 u,n=auth(); b=request.json or {}; cd=str(b.get('code','')).upper(); aid=int(b.get('auction_id',0)); bid=int(b.get('bid',0))
 if bid<=0:return jsonify(error='Ставка должна быть больше 0'),400
 c=conn()
 try:
  with c.cursor() as x:
   x.execute("SELECT * FROM room_auctions WHERE id=%s AND room_code=%s AND status='open' FOR UPDATE",(aid,cd)); a=x.fetchone()
   if not a:return jsonify(error='Аукцион не найден'),404
   if int(a['ends_at'])<=int(time.time()):return jsonify(error='Аукцион завершён'),400
   x.execute("SELECT money FROM room_players WHERE room_code=%s AND user_id=%s FOR UPDATE",(cd,u)); p=x.fetchone()
   if not p or int(p['money'])<bid:return jsonify(error='Недостаточно денег'),400
   if bid<=int(a['bid']):return jsonify(error='Ставка должна быть выше текущей'),400
   x.execute("UPDATE room_auctions SET bid=%s,winner=%s WHERE id=%s",(bid,u,aid))
   x.execute("INSERT INTO auction_bids(auction_id,user_id,bid,created_at) VALUES(%s,%s,%s,%s)",(aid,u,bid,int(time.time())))
  c.commit(); return jsonify(ok=True)
 finally: put(c)

@app.post('/api/rooms/auction/finish')
def auction_finish():
 u,n=auth(); b=request.json or {}; cd=str(b.get('code','')).upper(); aid=int(b.get('auction_id',0))
 c=conn()
 try:
  with c.cursor() as x:
   x.execute("SELECT * FROM room_auctions WHERE id=%s AND room_code=%s AND status='open' FOR UPDATE",(aid,cd)); a=x.fetchone()
   if not a:return jsonify(error='Аукцион уже завершён'),400
   if int(a['ends_at'])>int(time.time()):return jsonify(error='Аукцион ещё идёт'),400
   if a['winner']:
    x.execute("SELECT money,props FROM room_players WHERE room_code=%s AND user_id=%s FOR UPDATE",(cd,a['winner'])); p=x.fetchone()
    if p and int(p['money'])>=int(a['bid']):
     props=list(p['props'] or []); props.append(int(a['cell']))
     x.execute("UPDATE room_players SET money=money-%s,props=%s,xp=xp+150 WHERE room_code=%s AND user_id=%s",(a['bid'],props,cd,a['winner']))
   x.execute("UPDATE room_auctions SET status='finished' WHERE id=%s",(aid,))
  c.commit(); return jsonify(snapshot(cd,u))
 finally: put(c)

@app.get('/api/rooms/<cd>/auctions')
def auctions(cd):
 u,n=auth()
 c=conn()
 try:
  with c.cursor(cursor_factory=RealDictCursor) as x:
   x.execute("SELECT id,cell_id,ends_at,bid,winner FROM room_auctions WHERE room_code=%s AND status='open' ORDER BY id DESC",(cd.upper(),))
   return jsonify(auctions=x.fetchall())
 finally: put(c)


@app.post('/api/rooms/rematch')
def rematch():
 u,n=auth(); b=request.json or {}; cd=str(b.get('code','')).upper(); c=conn()
 try:
  with c.cursor(cursor_factory=RealDictCursor) as x:
   x.execute('SELECT * FROM rooms WHERE code=%s FOR UPDATE',(cd,)); r=x.fetchone()
   if not r:return jsonify(error='Комната не найдена'),404
   if int(r['host_id'])!=u:return jsonify(error='Только создатель может начать реванш'),403
   x.execute('SELECT user_id FROM room_players WHERE room_code=%s ORDER BY slot',(cd,)); rows=x.fetchall()
   if len(rows)<2:return jsonify(error='Нужно минимум 2 игрока'),400
   x.execute('SELECT * FROM rooms WHERE code=%s FOR UPDATE',(cd,)); r=x.fetchone()
   x.execute("UPDATE room_players SET money=15000,pos=0,props='[]',houses='{}',bankrupt=false,mortgages='{}',jail_turns=0,jailed=false WHERE room_code=%s",(cd,))
   x.execute("DELETE FROM trades WHERE room_code=%s",(cd,)); x.execute("DELETE FROM room_auctions WHERE room_code=%s",(cd,))
   st={'log':['🔁 Реванш начался!'],'winner':None}
   x.execute("UPDATE rooms SET status='playing',turn=0,state=%s,updated_at=now() WHERE code=%s",(Json(st),cd))
  c.commit(); return jsonify(snapshot(cd,u))
 finally: put(c)

@app.get('/api/rooms/<cd>/achievements')
def achievements(cd):
 u,n=auth(); c=conn()
 try:
  with c.cursor(cursor_factory=RealDictCursor) as x:
   x.execute('SELECT user_id,name,badges,xp,wins FROM room_players WHERE room_code=%s ORDER BY xp DESC',(cd.upper(),)); return jsonify(players=x.fetchall(),badges=BADGES)
 finally: put(c)


def bot():
 if not BOT_TOKEN or not WEB_APP_URL:return
 def call(m,p):
  try:
   req=urllib.request.Request(f'https://api.telegram.org/bot{BOT_TOKEN}/{m}',data=json.dumps(p).encode(),headers={'Content-Type':'application/json'});return json.loads(urllib.request.urlopen(req,timeout=30).read())
  except Exception:return None
 call('deleteWebhook',{'drop_pending_updates':False});off=0
 while True:
  r=call('getUpdates',{'timeout':20,'offset':off})
  if not r or not r.get('ok'):time.sleep(2);continue
  for q in r.get('result',[]):
   off=q['update_id']+1;m=q.get('message') or {};chat=m.get('chat',{}).get('id');t=m.get('text','')
   if chat and t.startswith('/start'):call('sendMessage',{'chat_id':chat,'text':'🏙️ Добро пожаловать в City Tycoon! Создай комнату и пригласи друзей.','reply_markup':{'inline_keyboard':[[{'text':'🎲 Открыть игру','web_app':{'url':WEB_APP_URL}}]]}})
threading.Thread(target=bot,daemon=True).start();initdb()

HTML=r'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no"><title>City Tycoon</title><script src="https://telegram.org/js/telegram-web-app.js"></script><style>
*{box-sizing:border-box}body{margin:0;background:#050811;color:#f8faff;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.app{max-width:500px;margin:auto;min-height:100vh;background:radial-gradient(circle at 50% 0,#1a2450,#050811 48%);padding-bottom:90px}.head{position:sticky;top:0;z-index:8;padding:15px 16px;border-bottom:1px solid #24314a;background:#070b14ee;backdrop-filter:blur(16px)}.logo{display:flex;align-items:center;gap:12px}.ico{width:48px;height:48px;border-radius:15px;background:linear-gradient(135deg,#8b5cf6,#4f46e5);display:grid;place-items:center;font-size:24px}.logo b{font-size:20px}.logo small{display:block;color:#8d9ab1}.screen{display:none;padding:16px}.on{display:block}.title{font-size:30px;font-weight:950;margin:7px 0}.sub{color:#93a1b7}.card{background:#0f1828ec;border:1px solid #273754;border-radius:22px;padding:15px;margin:12px 0}.primary,.secondary{width:100%;border:0;padding:15px;border-radius:16px;font-weight:900;font-size:16px}.primary{background:linear-gradient(135deg,#8064ff,#4d49e8);color:white}.secondary{background:#19263d;color:#e6ecf7;margin-top:9px}input,select{width:100%;padding:14px;border-radius:14px;background:#09111f;border:1px solid #31415c;color:white;margin:6px 0;outline:0}.row{display:grid;grid-template-columns:1fr 1fr;gap:9px}.code{font-size:38px;letter-spacing:8px;text-align:center;font-weight:1000;color:#b8adff}.players{display:grid;gap:8px}.pl{display:flex;gap:10px;align-items:center;padding:10px;border-radius:15px;background:#091220;border:1px solid #1e2b41}.av{width:38px;height:38px;border-radius:12px;background:linear-gradient(135deg,#38bdf8,#8b5cf6);display:grid;place-items:center;font-weight:900}.board{display:grid;grid-template-columns:repeat(5,1fr);gap:4px;background:#060a12;padding:6px;border-radius:18px}.cell{min-height:70px;border:1px solid #2a3850;border-radius:9px;background:#111a2a;padding:5px;transition:.25s}.cell.active{animation:pulse .7s}.cell.me{box-shadow:inset 0 0 0 2px #7c5cff}.bar{height:5px;border-radius:5px;margin:-5px -5px 4px}.cell b{font-size:9px;line-height:1.03;display:block}.cell small{font-size:8px;color:#8e9db3}.tok{transition:transform .35s ease,filter .35s ease;animation:tokpulse 1.8s infinite}@keyframes tokpulse{50%{transform:scale(1.12)}}.tok{display:inline-block;font-size:15px;animation:float 1.2s infinite}.level{font-size:8px;color:#62e6a3;font-weight:900}.money{font-size:23px;font-weight:950}.log,.chatbox{max-height:190px;overflow:auto}.log div,.chatmsg{padding:7px 0;border-bottom:1px solid #1a2537;color:#bbc8db;font-size:13px}.chatmsg b{color:#b5a8ff}.dicebox{text-align:center}.dice{font-size:58px;display:inline-block;min-width:85px}.rolling{animation:dice .5s ease-in-out 2}.winner{padding:16px;text-align:center;border:1px solid #8a6cff55;background:#7c5cff18;border-radius:18px;font-size:19px;font-weight:900}.tabs{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}.tab{padding:9px;border-radius:12px;background:#0b1422;color:#8f9db3;text-align:center;font-weight:800;font-size:12px}.tab.active{background:#25204a;color:#c6bcff}.nav{position:fixed;bottom:0;left:50%;transform:translateX(-50%);width:min(500px,100%);display:grid;grid-template-columns:repeat(3,1fr);background:#080d18f5;border-top:1px solid #202d43;padding:8px;z-index:10}.nav button{background:none;color:#72809a;border:0}.nav i{font-style:normal;font-size:20px;display:block}.nav b{font-size:11px}.toast{position:fixed;bottom:92px;left:50%;transform:translate(-50%,20px);background:#1d2b43;border:1px solid #3b4e70;padding:12px 16px;border-radius:15px;opacity:0;transition:.2s;z-index:30;max-width:90%;text-align:center}.toast.show{opacity:1;transform:translate(-50%,0)}button:disabled{opacity:.45}@keyframes dice{25%{transform:rotate(-15deg) scale(1.15)}50%{transform:rotate(15deg) scale(.9)}75%{transform:rotate(-8deg) scale(1.15)}}@keyframes float{50%{transform:translateY(-5px)}}@keyframes pulse{50%{transform:scale(1.08);box-shadow:0 0 25px #8064ff77}}
.float{animation:floaty .35s ease}@keyframes floaty{from{transform:scale(.92);opacity:.5}to{transform:scale(1);opacity:1}} .hotel{font-size:12px} .ach{display:flex;gap:5px;flex-wrap:wrap;margin-top:6px}
</style></head><body><div class="app"><header class="head"><div class="logo"><div class="ico">🏙️</div><div><b>CITY TYCOON</b><small>Multiplayer • Strategy • Trade</small></div></div></header>
<section id="subscribe" class="screen"><div class="title">📢 Подпишись, чтобы играть</div><div class="sub">Для доступа к City Tycoon нужно подписаться на все обязательные каналы.</div><div id="subList" class="players" style="margin-top:12px"></div><button class="primary" onclick="checkSubscription()">✅ Я подписался — проверить</button></section>
<section id="admin" class="screen"><div class="title">🛠 Админ-панель</div><div class="card"><b>📊 Статистика</b><div id="adminStats" class="sub" style="line-height:1.8;margin-top:8px"></div></div><div class="card"><b>➕ Добавить обязательный канал</b><input id="chId" placeholder="@channel или -1001234567890"><input id="chTitle" placeholder="Название (необязательно)"><input id="chInvite" placeholder="Ссылка t.me (для приватного канала)"><button class="primary" onclick="addChannel()">Добавить канал</button></div><div class="card"><b>📢 Обязательные каналы</b><div id="adminChannels" class="players" style="margin-top:10px"></div></div></section>
<section id="home" class="screen on"><div class="title">Твой город. Твоя стратегия.</div><div class="sub">Покупай районы, строй дома, торгуй и собери самый большой капитал.</div><div id="adminEntry" style="display:none" class="card"><button class="secondary" onclick="show('admin');loadAdmin()">🛠 Админ-панель</button></div><div class="card"><button class="primary" onclick="createRoom()">🎲 Создать комнату</button><button class="secondary" onclick="show('join')">🔑 Войти по коду</button></div><div class="card"><div style="display:flex;align-items:center;justify-content:space-between;gap:8px"><b>🌐 Открытые комнаты</b><button class="secondary" style="width:auto;padding:9px 12px;margin:0" onclick="loadRooms()">↻ Обновить</button></div><div id="roomList" class="players" style="margin-top:10px"><div class="sub">Загрузка комнат...</div></div></div><div class="card"><b>Новое обновление</b><div class="sub" style="line-height:1.55;margin-top:8px">🏗️ 5 уровней зданий • 🤝 обмен • 💬 чат • 🎴 события • 🏆 победитель • 🎲 анимация кубиков.</div></div></section>
<section id="join" class="screen"><div class="title">Войти в игру</div><div class="card"><input id="joinCode" maxlength="6" placeholder="ABC123"><button class="primary" onclick="joinRoom()">🚪 Войти</button></div></section>
<section id="room" class="screen"><div class="title">Комната</div><div class="card"><div class="code" id="roomCode">------</div><div class="sub" style="text-align:center">Отправь код друзьям</div></div><div class="card"><b>Игроки</b><div id="players" class="players" style="margin-top:10px"></div><button id="startBtn" class="primary" style="margin-top:12px" onclick="startGame()">🚀 Начать игру</button></div></section>
<section id="game" class="screen"><div id="winnerBox"></div><div class="card"><div class="sub">🏅 Достижения</div><div id="achievements" class="ach"></div></div><div class="row"><div class="card"><div class="sub">Капитал</div><div id="money" class="money">0 🪙</div></div><div class="card"><div class="sub">Ход игрока</div><div id="turn" class="money" style="font-size:16px">—</div></div></div><div class="card dicebox"><div id="dice" class="dice">🎲</div><div id="diceText" class="sub">Нажми «Бросить»</div><div id="jailActions"></div></div><div class="card" style="padding:7px"><div id="board" class="board"></div></div><div class="card"><div class="sub">Ваша клетка</div><b id="pos">—</b><div id="info" class="sub"></div><div id="propertyDetail" class="sub" style="margin-top:8px"></div><div id="cellActions" style="display:flex;gap:7px;flex-wrap:wrap;margin-top:10px"></div>
<div id="auctionBox" class="sub" style="margin-top:8px"></div></div><div class="row"><button id="rollBtn" class="primary" onclick="doRoll()">🎲 Бросить</button><button class="secondary" onclick="buyHere()">🏠 Купить</button></div><button class="secondary" onclick="buildHere()">🏗️ Построить / улучшить</button>
<div class="card"><div class="tabs"><div id="tabLog" class="tab active" onclick="tab('log')">📜 События</div><div id="tabChat" class="tab" onclick="tab('chat')">💬 Чат</div><div id="tabTrade" class="tab" onclick="tab('trade')">🤝 Обмен</div></div><div id="panelLog"><div id="log" class="log"></div></div><div id="panelChat" style="display:none"><div id="chatbox" class="chatbox"></div><div class="row"><input id="chatInput" placeholder="Написать..." maxlength="240"><button class="primary" onclick="sendChat()">➤</button></div></div><div id="panelTrade" style="display:none"><select id="tradeTo"></select><input id="offerMoney" type="number" min="0" placeholder="Дать денег"><input id="wantMoney" type="number" min="0" placeholder="Получить денег"><select id="offerProp"><option value="">Не отдавать улицу</option></select><select id="wantProp"><option value="">Получить улицу</option></select><button class="primary" onclick="sendTrade()">🤝 Предложить обмен</button><div id="trades"></div></div></div></section>
<section id="profile" class="screen"><div class="title">Профиль</div>
<div class="card"><div class="av" style="width:70px;height:70px;font-size:28px" id="ava">🧑‍💼</div><h2 id="pname">Игрок</h2><div class="sub">Выбери персонажа</div>
<div id="avatars" style="display:grid;grid-template-columns:repeat(6,1fr);gap:7px;margin-top:12px"></div>
<button class="primary" style="margin-top:10px" onclick="saveAvatar()">💾 Сохранить персонажа</button></div>
<div class="card"><b>🏆 Рейтинг комнаты</b><div id="leaderboard" class="log" style="margin-top:8px"></div></div></section>
<nav class="nav"><button onclick="show('home')"><i>🏠</i><b>Главная</b></button><button onclick="roomCode?show(g?.status==='playing'||g?.status==='finished'?'game':'room'):show('join')"><i>🎲</i><b>Игра</b></button><button onclick="show('profile')"><i>👤</i><b>Профиль</b></button></nav><div id="toast" class="toast"></div></div>
<script>
const tg=window.Telegram?.WebApp;if(tg){tg.ready();tg.expand()}let me=null,g=null,roomCode=null,poll=null;const $=id=>document.getElementById(id);
function show(id){document.querySelectorAll('.screen').forEach(x=>x.classList.remove('on'));$(id).classList.add('on');if(id==='profile'){let p=g?.players?.find(x=>x.user_id==g.me);if(p){selectedAvatar=p.avatar||'🧑‍💼';$('ava').textContent=selectedAvatar}loadLeaderboard()}}function toast(s){let x=$('toast');x.textContent=s;x.classList.add('show');setTimeout(()=>x.classList.remove('show'),2600)}function esc(s){return String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))}
async function api(u,o={}){o.headers=Object.assign({'Content-Type':'application/json'},o.headers||{});if(tg?.initData)o.headers['X-Telegram-Init-Data']=tg.initData;let r=await fetch(u,o),d=await r.json();if(!r.ok){let e=Error(d.error||'Ошибка');Object.assign(e,d);throw e}return d}
const AV=['🧑‍💼','🧑‍🚀','🧑‍🎨','🧑‍🔬','🧑‍💻','🧑‍🍳','🦊','🐯','🐼','🤖','👽','🦸'];let selectedAvatar='🧑‍💼';
function renderAvatarPicker(){ $('avatars').innerHTML=AV.map(a=>`<button onclick="selectedAvatar='${a}';$('ava').textContent='${a}'" style="font-size:24px;padding:8px;border-radius:12px;border:1px solid #2b3a54;background:#0b1422">${a}</button>`).join('') }
async function saveAvatar(){if(!roomCode){toast('Сначала войди в комнату');return}try{g=await api('/api/rooms/profile',{method:'POST',body:JSON.stringify({code:roomCode,avatar:selectedAvatar})});renderGame();toast('Персонаж сохранён')}catch(e){toast(e.message)}}
async function loadLeaderboard(){if(!roomCode)return;try{let d=await api('/api/rooms/'+roomCode+'/leaderboard');$('leaderboard').innerHTML=d.players.map((p,i)=>`<div style="display:flex;gap:8px;align-items:center;padding:7px 0;border-bottom:1px solid #1a2537"><b>#${i+1}</b><span style="font-size:18px">${esc(p.avatar||'🧑‍💼')}</span><span style="flex:1">${esc(p.name)}<br><small>${Number(p.xp).toLocaleString('ru-RU')} XP</small></span><b>${Number(p.net_worth).toLocaleString('ru-RU')} 🪙</b></div>`).join('')}catch(e){}}

async function mortgageCell(cell){
 try{g=await api('/api/rooms/mortgage',{method:'POST',body:JSON.stringify({code:roomCode,cell})});renderGame();toast('Улица заложена за 50% стоимости')}catch(e){toast(e.message)}
}
async function unmortgageCell(cell){
 try{g=await api('/api/rooms/unmortgage',{method:'POST',body:JSON.stringify({code:roomCode,cell})});renderGame();toast('Улица выкуплена')}catch(e){toast(e.message)}
}
async function jailAction(action){
 try{g=await api('/api/rooms/jail',{method:'POST',body:JSON.stringify({code:roomCode,action})});renderGame()}catch(e){toast(e.message)}
}
async function createAuction(cell){
 try{let r=await api('/api/rooms/auction',{method:'POST',body:JSON.stringify({code:roomCode,cell})});toast('Аукцион запущен');loadAuctions()}catch(e){toast(e.message)}
}
async function bidAuction(id){
 let v=prompt('Ваша ставка 🪙');if(!v)return;
 try{await api('/api/rooms/auction/bid',{method:'POST',body:JSON.stringify({code:roomCode,auction_id:id,bid:Number(v)} )});toast('Ставка принята');loadAuctions()}catch(e){toast(e.message)}
}
async function finishAuction(id){
 try{g=await api('/api/rooms/auction/finish',{method:'POST',body:JSON.stringify({code:roomCode,auction_id:id})});renderGame()}catch(e){toast(e.message)}
}
async function loadAuctions(){
 if(!roomCode)return;
 try{let d=await api('/api/rooms/'+roomCode+'/auctions');$('auctionBox').innerHTML=d.auctions.map(a=>{let c=B[a.cell_id];let left=Math.max(0,a.ends_at-Math.floor(Date.now()/1000));return `<div style="margin-top:6px">🔨 ${esc(c.name)} • ${Number(a.bid).toLocaleString('ru-RU')} 🪙 • ${left}с <button onclick="bidAuction(${a.id})">Ставка</button> ${left===0?`<button onclick="finishAuction(${a.id})">Завершить</button>`:''}</div>`}).join('')||'Аукционов нет'}catch(e){}
}
async function init(){try{me=await api('/api/me');$('pname').textContent=me.name;renderAvatarPicker();if(me.is_admin)$('adminEntry').style.display='block'}catch(e){if(e.subscription_required){renderSubscription(e);show('subscribe')}else toast(e.message)}}
function renderSubscription(d){$('subList').innerHTML=(d.channels||[]).map(c=>`<div class="pl"><div class="av">📢</div><div style="flex:1"><b>${esc(c.title)}</b><div class="sub">${c.subscribed?'✅ Подписка есть':'❌ Нужно подписаться'}</div></div>${c.invite_url?`<button class="primary" style="width:auto;padding:10px 12px" onclick="window.open('${esc(c.invite_url)}','_blank')">Открыть</button>`:''}</div>`).join('')}
async function checkSubscription(){try{let d=await api('/api/subscription/check',{method:'POST',body:'{}'});if(d.ok){toast('✅ Подписка подтверждена');show('home');init()}else{renderSubscription(d);toast('Подпишись на все каналы')}}catch(e){toast(e.message)}}
async function loadAdmin(){try{let s=await api('/api/admin/stats');$('adminStats').innerHTML=`Игроков: <b>${s.players}</b><br>Открытых комнат: <b>${s.waiting_rooms}</b><br>Игр идёт: <b>${s.playing_games}</b>`;let d=await api('/api/admin/channels');$('adminChannels').innerHTML=d.channels.length?d.channels.map(c=>`<div class="pl"><div style="flex:1"><b>${esc(c.title)}</b><div class="sub">${esc(c.username?'@'+c.username:c.chat_id)} • ${c.active?'включён':'выключен'}</div></div><button class="secondary" style="width:auto;padding:9px" onclick="toggleChannel(${c.id})">${c.active?'⏸':'▶️'}</button><button class="secondary" style="width:auto;padding:9px" onclick="deleteChannel(${c.id})">🗑</button></div>`).join(''):'<div class="sub">Каналов пока нет</div>'}catch(e){toast(e.message)}}
async function addChannel(){try{await api('/api/admin/channels',{method:'POST',body:JSON.stringify({chat_id:$('chId').value,title:$('chTitle').value,invite_url:$('chInvite').value})});$('chId').value='';$('chTitle').value='';$('chInvite').value='';loadAdmin();toast('Канал добавлен')}catch(e){toast(e.message)}}
async function toggleChannel(id){try{await api('/api/admin/channels/'+id+'/toggle',{method:'POST',body:'{}'});loadAdmin()}catch(e){toast(e.message)}}
async function deleteChannel(id){try{await api('/api/admin/channels/'+id,{method:'DELETE'});loadAdmin()}catch(e){toast(e.message)}}
async function loadRooms(){try{let d=await api('/api/rooms/list');let el=$('roomList');if(!d.rooms.length){el.innerHTML='<div class=\"sub\">Пока нет открытых комнат. Создай первую 🎲</div>';return}el.innerHTML=d.rooms.map(r=>`<div class=\"pl\" style=\"align-items:center\"><div class=\"av\">🏙️</div><div style=\"flex:1\"><b>${esc(r.host_name||'Игрок')}</b><div class=\"sub\">Код: <b>${esc(r.code)}</b> • ${r.players}/6 игроков</div></div><button class=\"primary\" style=\"width:auto;padding:10px 13px\" onclick=\"joinOpenRoom('${esc(r.code)}')\">Войти</button></div>`).join('')}catch(e){$('roomList').innerHTML='<div class=\"sub\">Не удалось загрузить комнаты</div>'}}
async function joinOpenRoom(code){try{g=await api('/api/rooms/join',{method:'POST',body:JSON.stringify({code})});roomCode=g.code;g.status==='playing'?renderGame():renderRoom();show(g.status==='playing'?'game':'room');startPoll()}catch(e){toast(e.message)}}
async function createRoom(){try{g=await api('/api/rooms',{method:'POST',body:'{}'});roomCode=g.code;renderRoom();show('room');startPoll()}catch(e){toast(e.message)}}async function joinRoom(){try{g=await api('/api/rooms/join',{method:'POST',body:JSON.stringify({code:$('joinCode').value})});roomCode=g.code;g.status==='playing'?renderGame():renderRoom();show(g.status==='playing'?'game':'room');startPoll()}catch(e){toast(e.message)}}async function startGame(){try{g=await api('/api/rooms/start',{method:'POST',body:JSON.stringify({code:roomCode})});renderGame();show('game')}catch(e){toast(e.message)}}
function startPoll(){clearInterval(poll);poll=setInterval(async()=>{try{g=await api('/api/rooms/'+roomCode);if(g.status==='playing'||g.status==='finished'){renderGame();if(!$('game').classList.contains('on'))show('game')}else renderRoom()}catch(e){}},1500)}
function renderRoom(){$('roomCode').textContent=g.code;$('players').innerHTML=g.players.map(p=>`<div class="pl"><div class="av">${esc(p.name[0]||'P')}</div><div><b>${esc(p.name)}</b><div class="sub">${p.user_id==g.host_id?'Создатель':''}</div></div></div>`).join('');$('startBtn').style.display=me&&me.user_id==g.host_id?'block':'none'}
function renderGame(){let p=g.players.find(x=>x.user_id==g.me),a=g.players[g.turn];if(!p)return;$('money').textContent=Number(p.money).toLocaleString('ru-RU')+' 🪙';$('turn').textContent=a?esc(a.name):'—';let c=g.board[p.pos];$('pos').textContent=c.name;$('info').textContent=c.price?`Цена ${c.price.toLocaleString('ru-RU')} 🪙 • ${c.type==='property'?'Улучшения повышают аренду':''}`:'';let ownerP=g.players.find(q=>(q.props||[]).map(Number).includes(c.id));let mep=g.players.find(q=>q.user_id==g.me);let mort=mep?.mortgages?.[String(c.id)];let lv=ownerP?Number((ownerP.houses||{})[String(c.id)]||0):0;let rentTxt=c.type==='property'?`Аренда уровня ${lv}: ${[60,120,360,900,1600,2500][Math.min(lv,5)]} 🪙`:(c.type==='station'?'Станция: аренда зависит от числа станций':'');$('propertyDetail').textContent=ownerP?`Владелец: ${ownerP.avatar||'🧑‍💼'} ${ownerP.name} • ${rentTxt}`:rentTxt;let last=g.state?.last_roll;$('board').innerHTML=g.board.map(c=>{let op=g.players.find(q=>(q.props||[]).map(Number).includes(c.id));let hs=op?Number((op.houses||{})[String(c.id)]||0):0;let toks=g.players.filter(q=>q.pos===c.id&&!q.bankrupt).map(q=>`<span class="tok" title="${esc(q.name)}">${esc(q.avatar||'🧑‍💼')}</span>`).join('');return `<div class="cell ${c.id===p.pos?'me':''} ${last?.to===c.id?'active float':''}">${c.group?`<div class="bar" style="background:${g.colors[c.group]}"></div>`:''}<b>${esc(c.name)}</b><small>${c.price?c.price.toLocaleString('ru-RU')+' 🪙':''}</small>${hs?`<div class="level">${hs>=5?'🏨': '🏠'.repeat(Math.min(hs,4))} LVL ${hs}</div>`:''}${toks}</div>`}).join('');$('log').innerHTML=(g.state?.log||[]).slice().reverse().map(x=>`<div>${esc(x)}</div>`).join('');renderChat();renderTrades();renderDice();$('rollBtn').disabled=a?.user_id!==g.me||g.status!=='playing';$('winnerBox').innerHTML=g.status==='finished'?`<div class="winner">🏆 Победитель: ${esc(g.state?.winner||'не определён')} ${g.host_id==g.me?`<button class="primary" onclick="rematch()">🔁 Реванш</button>`:''}</div>`:'';renderAchievements(p);loadLeaderboard()}
function renderDice(){let r=g.state?.last_roll;if(!r)return;let ic=['','⚀','⚁','⚂','⚃','⚄','⚅'];$('dice').textContent=ic[r.d1]+' '+ic[r.d2];$('diceText').textContent=`${r.d1}+${r.d2} = ${r.d1+r.d2} шагов${r.doubles?' • 🎉 Дубль — ещё ход!':''}`;if(r.player==g.me){$('dice').classList.remove('rolling');void $('dice').offsetWidth;$('dice').classList.add('rolling')}}
function renderAchievements(p){let b=p?.badges||[];let names={first_roll:'🎲 Первый ход',double:'⚡ Дубль',builder:'🏗️ Строитель',collector:'🏠 Коллекционер',rich:'💎 Капиталист',auction:'🔨 Аукционист',jailbreak:'🚔 Освобождение'};$('achievements').innerHTML=b.map(x=>`<span class="pill">${names[x]||x}</span>`).join('')||'Пока нет — сыграй первый ход!'}
async function rematch(){try{g=await api('/api/rooms/rematch',{method:'POST',body:JSON.stringify({code:roomCode})});renderGame();toast('🔁 Реванш начался')}catch(e){toast(e.message)}}
function tab(t){['log','chat','trade'].forEach(x=>{$('panel'+x[0].toUpperCase()+x.slice(1)).style.display=x===t?'block':'none';$('tab'+x[0].toUpperCase()+x.slice(1)).classList.toggle('active',x===t)})}
function renderChat(){$('chatbox').innerHTML=(g.messages||[]).slice().reverse().map(m=>`<div class="chatmsg"><b>${esc(m.name)}:</b> ${esc(m.message)}</div>`).join('')}
async function sendChat(){let v=$('chatInput').value.trim();if(!v)return;try{g=await api('/api/rooms/chat',{method:'POST',body:JSON.stringify({code:roomCode,message:v})});$('chatInput').value='';renderChat();tab('chat')}catch(e){toast(e.message)}}
function propsFor(uid){let p=g.players.find(x=>x.user_id==uid);return (p?.props||[]).map(Number)}
function fillTrade(){let to=$('tradeTo');to.innerHTML=g.players.filter(p=>p.user_id!=g.me&&!p.bankrupt).map(p=>`<option value="${p.user_id}">${esc(p.name)}</option>`).join('');$('offerProp').innerHTML='<option value="">Не отдавать улицу</option>'+propsFor(g.me).map(i=>`<option value="${i}">${esc(g.board[i].name)}</option>`).join('');let id=Number(to.value||0);$('wantProp').innerHTML='<option value="">Получить улицу</option>'+propsFor(id).map(i=>`<option value="${i}">${esc(g.board[i].name)}</option>`).join('')}
function renderTrades(){fillTrade();$('trades').innerHTML=(g.trades||[]).map(t=>{let from=g.players.find(p=>p.user_id==t.from_user)?.name||'Игрок';let to=g.players.find(p=>p.user_id==t.to_user)?.name||'Игрок';let off=(t.offer_props||[]).map(i=>g.board[Number(i)]?.name).join(', ');let want=(t.want_props||[]).map(i=>g.board[Number(i)]?.name).join(', ');if(t.to_user==g.me)return `<div class="card"><b>🤝 ${esc(from)} → вам</b><div class="sub">Дает: ${t.offer_money} 🪙 ${esc(off)}<br>Хочет: ${t.want_money} 🪙 ${esc(want)}</div><button class="primary" onclick="acceptTrade(${t.id})">Принять</button><button class="secondary" onclick="rejectTrade(${t.id})">Отклонить</button></div>`;return `<div class="sub" style="padding:8px">🤝 ${esc(from)} → ${esc(to)}: ожидает ответа</div>`}).join('')}
$('tradeTo').addEventListener('change',()=>{let id=Number($('tradeTo').value||0);$('wantProp').innerHTML='<option value="">Получить улицу</option>'+propsFor(id).map(i=>`<option value="${i}">${esc(g.board[i].name)}</option>`).join('')});
async function sendTrade(){try{let to=Number($('tradeTo').value),op=$('offerProp').value?[$('offerProp').value]:[],wp=$('wantProp').value?[$('wantProp').value]:[];g=await api('/api/rooms/trade',{method:'POST',body:JSON.stringify({code:roomCode,to_user:to,offer_money:Number($('offerMoney').value||0),want_money:Number($('wantMoney').value||0),offer_props:op,want_props:wp})});renderGame();toast('Предложение отправлено 🤝')}catch(e){toast(e.message)}}
async function acceptTrade(id){try{g=await api('/api/rooms/trade/'+id+'/accept',{method:'POST',body:'{}'});renderGame();toast('Обмен завершён 🤝')}catch(e){toast(e.message)}}async function rejectTrade(id){try{g=await api('/api/rooms/trade/'+id+'/reject',{method:'POST',body:JSON.stringify({code:roomCode})});renderGame()}catch(e){toast(e.message)}}
async function doRoll(){try{$('rollBtn').disabled=true;g=await api('/api/rooms/roll',{method:'POST',body:JSON.stringify({code:roomCode})});renderGame()}catch(e){toast(e.message)}finally{if(g?.status==='playing')$('rollBtn').disabled=false}}
async function buyHere(){try{let p=g.players.find(x=>x.user_id==g.me),c=g.board[p.pos];g=await api('/api/rooms/buy',{method:'POST',body:JSON.stringify({code:roomCode,property_id:c.id})});renderGame();toast('🏠 Участок куплен')}catch(e){toast(e.message)}}async function buildHere(){try{let p=g.players.find(x=>x.user_id==g.me),c=g.board[p.pos];g=await api('/api/rooms/build',{method:'POST',body:JSON.stringify({code:roomCode,property_id:c.id})});renderGame();toast('🏗️ Здание улучшено')}catch(e){toast(e.message)}}init();loadRooms();setInterval(()=>{if(!$('home').classList.contains('on'))return;loadRooms()},4000);
</script></body></html>'''

if __name__=='__main__': app.run(host='0.0.0.0',port=PORT)
