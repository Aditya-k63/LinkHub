import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import uuid
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from starlette.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logger import logger
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.auth import AuthMiddleware
from app.api import auth, links, analytics, admin

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-ready URL shortening service with analytics",
)

@app.on_event("startup")
async def startup():
    try:
        from app.db.session import engine
        from app.db.models import Base
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created")
    except Exception as e:
        logger.error(f"Database startup error: {e}")

app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(links.router)
app.include_router(analytics.router)
app.include_router(admin.router)

logger.info(f"Routers loaded: {len(app.routes)} routes")


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return HTMLResponse("""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>LinkHub</title>
<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,sans-serif;background:#0f172a;color:#f8fafc;min-height:100vh}.navbar{background:#1e293b;padding:1rem 2rem;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #334155}.logo{font-size:1.5rem;font-weight:bold;color:#f8fafc;text-decoration:none}.nav-links a{color:#94a3b8;text-decoration:none;margin-left:1.5rem}.nav-links a:hover{color:#6366f1}.hero{padding:4rem 2rem;text-align:center;max-width:800px;margin:0 auto}h1{font-size:3rem;margin-bottom:1rem;background:linear-gradient(135deg,#6366f1,#a855f7);-webkit-background-clip:text;-webkit-text-fill-color:transparent}.subtitle{color:#94a3b8;font-size:1.2rem;margin-bottom:2rem}.auth-box{max-width:400px;margin:0 auto 2rem;padding:2rem;background:#1e293b;border-radius:12px}.auth-box h2{margin-bottom:1.5rem;text-align:center}.auth-box input{width:100%;padding:.75rem 1rem;margin-bottom:1rem;border:2px solid #334155;border-radius:8px;background:#0f172a;color:#f8fafc;font-size:1rem}.auth-box input:focus{outline:none;border-color:#6366f1}.auth-box button{width:100%;padding:.75rem;background:#6366f1;color:#fff;border:none;border-radius:8px;font-size:1rem;font-weight:600;cursor:pointer}.auth-box button:hover{background:#4f46e5}.auth-box p{text-align:center;margin-top:1rem;color:#94a3b8}.auth-box a{color:#6366f1;cursor:pointer;text-decoration:underline}.shorten-box{display:flex;gap:.5rem;max-width:600px;margin:0 auto 2rem;flex-wrap:wrap;justify-content:center}.shorten-box input{flex:1;min-width:200px;padding:1rem;border:2px solid #334155;border-radius:8px;background:#1e293b;color:#f8fafc;font-size:1rem}.shorten-box input:focus{outline:none;border-color:#6366f1}.shorten-box button{padding:1rem 2rem;background:#6366f1;color:#fff;border:none;border-radius:8px;font-size:1rem;font-weight:600;cursor:pointer}.result{display:none;max-width:600px;margin:0 auto 2rem;padding:1.5rem;background:#1e293b;border-radius:12px;border:1px solid #22c55e}.result.show{display:block}.result-box{display:flex;gap:.5rem;margin:1rem 0}.result-box code{flex:1;padding:.75rem;background:#0f172a;border-radius:6px;word-break:break-all}.result-box button{padding:.75rem 1.5rem;background:#22c55e;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:600}#qr-code{max-width:200px;margin-top:1rem}.features{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem;margin-top:3rem}.feature{padding:1.5rem;background:#1e293b;border-radius:12px}.feature h3{margin-bottom:.5rem;color:#6366f1}.feature p{color:#94a3b8;font-size:.9rem}.hidden{display:none}.error{color:#ef4444;margin-top:.5rem;font-size:.9rem}</style></head>
<body>
<nav class="navbar"><a href="/" class="logo">LinkHub</a><div class="nav-links"><a href="/docs">API Docs</a><a href="/dashboard">Dashboard</a><a href="#" id="auth-link" onclick="showAuth()">Login</a></div></nav>
<main class="hero"><h1>Shorten. Track. Optimize.</h1><p class="subtitle">Production-ready URL shortening with analytics, caching, and rate limiting.</p>
<div id="auth-section" class="auth-box"><h2 id="auth-title">Login</h2><div id="register-fields" class="hidden"><input type="text" id="username" placeholder="Username"></div><input type="email" id="email" placeholder="Email"><input type="password" id="password" placeholder="Password"><div id="auth-error" class="error hidden"></div><button onclick="handleAuth()" id="auth-btn">Login</button><p>Don't have an account? <a onclick="toggleAuth()">Register</a></p></div>
<div id="shorten-section" class="hidden"><div class="shorten-box"><input type="url" id="url-input" placeholder="Paste your long URL here..." required><input type="text" id="alias-input" placeholder="Custom alias (optional)"><button onclick="shortenUrl()">Shorten</button></div><div id="result" class="result"><p>Your shortened URL:</p><div class="result-box"><code id="short-url"></code><button onclick="copyUrl()">Copy</button></div><img id="qr-code" alt="QR Code"></div></div>
<div class="features"><div class="feature"><h3>Fast Redirects</h3><p>Redis-powered caching for sub-5ms lookups</p></div><div class="feature"><h3>Analytics</h3><p>Track clicks, devices, browsers, and geography</p></div><div class="feature"><h3>Secure</h3><p>JWT auth, rate limiting, and password-protected links</p></div><div class="feature"><h3>Docker Ready</h3><p>One command deployment with Docker Compose</p></div></div></main>
<script>
const API=window.location.origin;let isRegister=false;function getToken(){return localStorage.getItem('token')}function showAuth(){document.getElementById('auth-section').classList.remove('hidden');document.getElementById('shorten-section').classList.add('hidden')}function toggleAuth(){isRegister=!isRegister;document.getElementById('auth-title').textContent=isRegister?'Register':'Login';document.getElementById('auth-btn').textContent=isRegister?'Register':'Login';document.getElementById('register-fields').classList.toggle('hidden',!isRegister);document.getElementById('auth-error').classList.add('hidden')}
async function handleAuth(){const email=document.getElementById('email').value;const password=document.getElementById('password').value;const username=document.getElementById('username').value;const endpoint=isRegister?'/api/auth/register':'/api/auth/login';const body=isRegister?{email,password,username}:{email,password};try{const res=await fetch(API+endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await res.json();if(!res.ok)throw new Error(data.detail||'Auth failed');localStorage.setItem('token',data.access_token);document.getElementById('auth-link').textContent='Logout';document.getElementById('auth-link').onclick=()=>{localStorage.removeItem('token');location.reload()};document.getElementById('auth-section').classList.add('hidden');document.getElementById('shorten-section').classList.remove('hidden')}catch(e){document.getElementById('auth-error').textContent=e.message;document.getElementById('auth-error').classList.remove('hidden')}}
async function shortenUrl(){const url=document.getElementById('url-input').value;const alias=document.getElementById('alias-input').value;const body={url};if(alias)body.custom_alias=alias;try{const res=await fetch(API+'/api/links',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+getToken()},body:JSON.stringify(body)});const data=await res.json();if(!res.ok)throw new Error(data.detail||'Failed');document.getElementById('short-url').textContent=data.short_url;document.getElementById('qr-code').src=data.qr_code;document.getElementById('result').classList.add('show')}catch(e){alert(e.message)}}
function copyUrl(){navigator.clipboard.writeText(document.getElementById('short-url').textContent);alert('Copied!')}
if(getToken()){document.getElementById('auth-link').textContent='Logout';document.getElementById('auth-link').onclick=()=>{localStorage.removeItem('token');location.reload()};document.getElementById('auth-section').classList.add('hidden');document.getElementById('shorten-section').classList.remove('hidden')}
</script></body></html>""")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return HTMLResponse("""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Dashboard - LinkHub</title>
<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,sans-serif;background:#0f172a;color:#f8fafc;min-height:100vh}.navbar{background:#1e293b;padding:1rem 2rem;display:flex;justify-content:space-between;border-bottom:1px solid #334155}.navbar a{color:#94a3b8;text-decoration:none;margin-left:1rem}.navbar a:hover{color:#6366f1}.container{max-width:1000px;margin:2rem auto;padding:0 1rem}h1{margin-bottom:2rem}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;margin-bottom:2rem}.stat{background:#1e293b;padding:1.5rem;border-radius:12px;text-align:center}.stat h3{color:#94a3b8;font-size:.9rem;margin-bottom:.5rem}.stat p{font-size:2rem;font-weight:bold;color:#6366f1}.links-list{background:#1e293b;border-radius:12px;padding:1rem}.link-item{display:flex;justify-content:space-between;align-items:center;padding:1rem;border-bottom:1px solid #334155}.link-item:last-child{border-bottom:none}.link-info a{color:#6366f1;font-weight:600;text-decoration:none}.link-info p{color:#94a3b8;font-size:.85rem;margin-top:.25rem;word-break:break-all}.link-stats{text-align:right}.link-stats .clicks{font-size:1.25rem;font-weight:bold;color:#22c55e}.link-stats .label{font-size:.75rem;color:#94a3b8}.empty{text-align:center;padding:3rem;color:#94a3b8}</style></head>
<body>
<nav class="navbar"><a href="/" style="font-size:1.5rem;font-weight:bold;color:#f8fafc;text-decoration:none">LinkHub</a><div><a href="/docs">API Docs</a><a href="#" onclick="logout()">Logout</a></div></nav>
<div class="container"><h1>Your Links</h1><div class="stats"><div class="stat"><h3>Total Links</h3><p id="total-links">0</p></div><div class="stat"><h3>Total Clicks</h3><p id="total-clicks">0</p></div><div class="stat"><h3>Active Links</h3><p id="active-links">0</p></div></div><div class="links-list" id="links-list"><div class="empty">Loading...</div></div></div>
<script>
const API=window.location.origin;const token=localStorage.getItem('token');if(!token)window.location.href='/';async function load(){try{const res=await fetch(API+'/api/links',{headers:{'Authorization':'Bearer '+token}});if(!res.ok)throw new Error('Failed');const data=await res.json();document.getElementById('total-links').textContent=data.total;const list=document.getElementById('links-list');if(!data.links.length){list.innerHTML='<div class="empty">No links yet. <a href="/">Create one</a></div>';return}let tc=0;list.innerHTML=data.links.map(l=>{tc+=l.click_count;return '<div class="link-item"><div class="link-info"><a href="'+l.short_url+'" target="_blank">'+l.short_url+'</a><p>'+l.original_url+'</p></div><div class="link-stats"><div class="clicks">'+l.click_count+'</div><div class="label">clicks</div></div></div>'}).join('');document.getElementById('total-clicks').textContent=tc;document.getElementById('active-links').textContent=data.total}catch(e){document.getElementById('links-list').innerHTML='<div class="empty">Failed to load</div>'}}function logout(){localStorage.removeItem('token');window.location.href='/'}load()
</script></body></html>""")


@app.get("/health")
def health_check():
    return {"status": "healthy", "version": settings.APP_VERSION}
