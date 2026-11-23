#!/usr/bin/env python3
"""Agnosto local development server. Standard library only; not production deployment."""
import os, json, sqlite3, secrets, hashlib, hmac, time, mimetypes
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote
from http.cookies import SimpleCookie

ROOT=Path(__file__).resolve().parent
DB=Path(os.environ.get('AGNOSTO_DB',str(ROOT/'agnosto.sqlite3')))
SESSIONS={}
MAX_BODY=65536

def db():
 c=sqlite3.connect(DB,timeout=10);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c

def init():
 with db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS admins(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, salt TEXT NOT NULL, digest TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS artists(id INTEGER PRIMARY KEY, name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL, discipline TEXT NOT NULL, bio TEXT NOT NULL DEFAULT '', published INTEGER NOT NULL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS works(id INTEGER PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL, type TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '', artist_id INTEGER REFERENCES artists(id) ON DELETE SET NULL, published INTEGER NOT NULL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS applications(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL, discipline TEXT NOT NULL, relationship TEXT NOT NULL, portfolio TEXT NOT NULL, bio TEXT NOT NULL, rights INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'New', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS inquiries(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL, kind TEXT NOT NULL, message TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'New', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, action TEXT NOT NULL, details TEXT NOT NULL DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP);''')
  if not c.execute('SELECT 1 FROM admins').fetchone():
   user=os.environ.get('AGNOSTO_ADMIN_USER','admin');pw=os.environ.get('AGNOSTO_ADMIN_PASSWORD')
   if not pw or len(pw)<14: raise SystemExit('Set AGNOSTO_ADMIN_PASSWORD to a unique password of at least 14 characters before starting.')
   salt=secrets.token_hex(16);digest=hashlib.pbkdf2_hmac('sha256',pw.encode(),bytes.fromhex(salt),350000).hex()
   c.execute('INSERT INTO admins(username,salt,digest) VALUES(?,?,?)',(user,salt,digest))

def clean(v,maxlen=5000):
 if not isinstance(v,str):return ''
 return v.strip()[:maxlen]

def valid_email(v):return '@' in v and '.' in v.split('@')[-1] and len(v)<=254

class Handler(BaseHTTPRequestHandler):
 def send(self,code,data,headers=None):
  b=json.dumps(data,ensure_ascii=False).encode();self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"default-src 'self'; frame-ancestors 'none'")
  for k,v in (headers or {}).items():self.send_header(k,v)
  self.end_headers();self.wfile.write(b)
 def file(self,path):
  p=ROOT/path
  if not p.is_file():return self.send(404,{'error':'Not found'})
  b=p.read_bytes();self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(str(p))[0] or 'text/plain');self.send_header('Content-Length',str(len(b)));self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(b)
 def session(self):
  cookie=SimpleCookie()
  try:cookie.load(self.headers.get('Cookie',''))
  except Exception:return None
  token=cookie.get('agnosto_session');s=SESSIONS.get(token.value) if token else None
  if s and s['expires']>time.time():return s
  return None
 def csrf(self):
  origin=self.headers.get('Origin');host=self.headers.get('Host','')
  return not origin or origin in ('http://'+host,'https://'+host)
 def body(self):
  try:
   n=int(self.headers.get('Content-Length','0'))
   if n<1 or n>MAX_BODY:return None
   data=json.loads(self.rfile.read(n));return data if isinstance(data,dict) else None
  except (ValueError,UnicodeDecodeError):return None
 def do_GET(self):
  path=urlparse(self.path).path
  if path=='/':return self.file('index.html')
  if path=='/admin':return self.file('admin.html')
  if path=='/api/session':return self.send(200,{'authenticated':bool(self.session())})
  if path=='/api/public':
   with db() as c:
    a=[dict(x) for x in c.execute('SELECT id,name,slug,discipline,bio FROM artists WHERE published=1 ORDER BY id DESC')]
    w=[dict(x) for x in c.execute('SELECT w.id,w.title,w.category,w.type,w.description,a.name artist FROM works w LEFT JOIN artists a ON a.id=w.artist_id WHERE w.published=1 ORDER BY w.id DESC')]
   return self.send(200,{'artists':a,'works':w})
  if path.startswith('/api/admin/'):
   if not self.session():return self.send(401,{'error':'Sign in required'})
   table=path.split('/')[-1]
   if table not in ('artists','works','applications','inquiries','audit'):return self.send(404,{'error':'Not found'})
   with db() as c:
    rows=[dict(x) for x in c.execute('SELECT * FROM '+table+' ORDER BY id DESC LIMIT 500')]
   return self.send(200,{'items':rows})
  return self.send(404,{'error':'Not found'})
 def do_POST(self):
  if not self.csrf():return self.send(403,{'error':'Invalid origin'})
  path=urlparse(self.path).path;data=self.body()
  if data is None:return self.send(400,{'error':'Invalid request'})
  if path=='/api/login':
   user=clean(data.get('username'),100);pw=data.get('password','')
   with db() as c:row=c.execute('SELECT * FROM admins WHERE username=?',(user,)).fetchone()
   if not row or not isinstance(pw,str) or not hmac.compare_digest(hashlib.pbkdf2_hmac('sha256',pw.encode(),bytes.fromhex(row['salt']),350000).hex(),row['digest']):
    time.sleep(.5);return self.send(401,{'error':'Invalid credentials'})
   token=secrets.token_urlsafe(32);SESSIONS[token]={'user':user,'expires':time.time()+8*3600}
   return self.send(200,{'ok':True},{'Set-Cookie':f'agnosto_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'})
  if path=='/api/logout':
   cookie=SimpleCookie();cookie.load(self.headers.get('Cookie',''));t=cookie.get('agnosto_session')
   if t:SESSIONS.pop(t.value,None)
   return self.send(200,{'ok':True},{'Set-Cookie':'agnosto_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'})
  if path=='/api/applications':
   vals=[clean(data.get(k),n) for k,n in [('name',100),('email',254),('discipline',100),('relationship',100),('portfolio',2000),('bio',4000)]]
   if not all(vals) or not valid_email(vals[1]) or data.get('rights') is not True:return self.send(400,{'error':'Complete all required fields and rights confirmation'})
   with db() as c:c.execute('INSERT INTO applications(name,email,discipline,relationship,portfolio,bio,rights) VALUES(?,?,?,?,?,?,1)',vals)
   return self.send(201,{'ok':True,'message':'Application received by the local development server. Email notifications are not configured.'})
  if path=='/api/inquiries':
   vals=[clean(data.get(k),n) for k,n in [('name',100),('email',254),('kind',100),('message',4000)]]
   if not all(vals) or not valid_email(vals[1]):return self.send(400,{'error':'Complete all required fields'})
   with db() as c:c.execute('INSERT INTO inquiries(name,email,kind,message) VALUES(?,?,?,?)',vals)
   return self.send(201,{'ok':True,'message':'Inquiry saved locally. Email delivery is not configured.'})
  if not self.session():return self.send(401,{'error':'Sign in required'})
  if path=='/api/admin/artists':
   vals=[clean(data.get(k),n) for k,n in [('name',100),('slug',100),('discipline',100),('bio',4000)]]
   if not all(vals[:3]) or not all(x.islower() or x.isdigit() or x=='-' for x in vals[1]) or vals[1].startswith('-'):return self.send(400,{'error':'Name, lowercase URL slug, and discipline required'})
   try:
    with db() as c:
     c.execute('INSERT INTO artists(name,slug,discipline,bio,published) VALUES(?,?,?,?,?)',(*vals,int(data.get('published') is True)))
     c.execute('INSERT INTO audit(action,details) VALUES(?,?)',('artist.created',vals[1]))
   except sqlite3.IntegrityError:return self.send(409,{'error':'Artist URL already exists'})
   return self.send(201,{'ok':True})
  if path=='/api/admin/works':
   vals=[clean(data.get(k),n) for k,n in [('title',150),('category',30),('type',80),('description',4000)]]
   if not vals[0] or vals[1] not in ('Music','Film','Photography','Art'):return self.send(400,{'error':'Title and valid category required'})
   aid=data.get('artist_id') or None
   try:
    with db() as c:
     c.execute('INSERT INTO works(title,category,type,description,artist_id,published) VALUES(?,?,?,?,?,?)',(*vals,aid,int(data.get('published') is True)))
     c.execute('INSERT INTO audit(action,details) VALUES(?,?)',('work.created',vals[0]))
   except (sqlite3.IntegrityError,ValueError):return self.send(400,{'error':'Invalid artist reference'})
   return self.send(201,{'ok':True})
  if path=='/api/admin/status':
   table=clean(data.get('table'),30);ident=data.get('id');status=clean(data.get('status'),40)
   if table not in ('applications','inquiries') or status not in ('New','Under Review','More Information Needed','Approved','Declined','Onboarding','Completed','Closed') or not isinstance(ident,int):return self.send(400,{'error':'Invalid status update'})
   with db() as c:
    c.execute(f'UPDATE {table} SET status=? WHERE id=?',(status,ident));c.execute('INSERT INTO audit(action,details) VALUES(?,?)',(table+'.status',str(ident)+' '+status))
   return self.send(200,{'ok':True})
  if path=='/api/admin/publish':
   table=clean(data.get('table'),30);ident=data.get('id');published=data.get('published')
   if table not in ('artists','works') or not isinstance(ident,int) or not isinstance(published,bool):return self.send(400,{'error':'Invalid publication update'})
   with db() as c:
    c.execute(f'UPDATE {table} SET published=? WHERE id=?',(int(published),ident));c.execute('INSERT INTO audit(action,details) VALUES(?,?)',(table+'.published',str(ident)+' '+str(published)))
   return self.send(200,{'ok':True})
  return self.send(404,{'error':'Not found'})

if __name__=='__main__':
 init();port=int(os.environ.get('AGNOSTO_PORT','8765'))
 print(f'Agnosto local development server: http://127.0.0.1:{port} (admin: /admin)',flush=True)
 ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
