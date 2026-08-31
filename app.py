"""FTransfer — simple, mobile-friendly file drop (installable PWA).

Uploads (one or many, no size limit) are streamed to disk under
./uploads/{YYYY-MM-DD}/{filename}.{ext} relative to this file.
No auth. Meant to run on the LAN so a phone can push files to the PC.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

# The multipart parser yields starlette's UploadFile; fastapi.UploadFile is a
# SUBCLASS of it, so isinstance() against fastapi.UploadFile is False for parsed
# files. Always check against the starlette base class.
from starlette.datastructures import UploadFile

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
UPLOAD_ROOT = (BASE_DIR / "uploads").resolve()
CHUNK_SIZE = 1024 * 1024  # 1 MiB — stream large files without loading into RAM

UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="FTransfer")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _safe_name(name: str) -> str:
    """Strip path components and characters Windows rejects; never empty."""
    name = name.replace("\\", "/").split("/")[-1]
    name = _UNSAFE.sub("_", name).strip().strip(".")
    return name or "file"


def _dest_path(filename: str) -> Path:
    """Today's folder + a non-colliding path for `filename`."""
    day_dir = UPLOAD_ROOT / date.today().isoformat()
    day_dir.mkdir(parents=True, exist_ok=True)
    safe = _safe_name(filename)
    dest = day_dir / safe
    if not dest.exists():
        return dest
    stem, suffix = Path(safe).stem, Path(safe).suffix
    i = 1
    while True:
        candidate = day_dir / f"{stem} ({i}){suffix}"
        if not candidate.exists():
            return candidate
        i += 1


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return INDEX_HTML


@app.post("/upload")
async def upload(request: Request):
    # No max_part_size cap -> allow arbitrarily large files (spooled to disk).
    form = await request.form(max_part_size=1024 * 1024 * 1024 * 1024)
    saved: list[dict] = []
    for value in form.getlist("files"):
        if not isinstance(value, UploadFile) or not value.filename:
            continue
        dest = _dest_path(value.filename)
        size = 0
        with dest.open("wb") as out:
            while chunk := await value.read(CHUNK_SIZE):
                out.write(chunk)
                size += len(chunk)
        await value.close()
        saved.append({"name": dest.name, "size": size})

    if not saved:
        return JSONResponse({"ok": False, "error": "No files received"}, status_code=400)
    return {"ok": True, "day": date.today().isoformat(), "saved": saved}


@app.get("/api/files")
async def list_files():
    """Every uploaded file across all day-folders, newest first."""
    out: list[dict] = []
    if UPLOAD_ROOT.exists():
        for f in UPLOAD_ROOT.glob("*/*"):
            if not f.is_file():
                continue
            st = f.stat()
            day = f.parent.name
            out.append(
                {
                    "name": f.name,
                    "day": day,
                    "size": st.st_size,
                    "mtime": st.st_mtime,
                    "when": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    "url": f"/download/{day}/{f.name}",
                }
            )
    out.sort(key=lambda r: r["mtime"], reverse=True)
    return {"files": out}


@app.get("/download/{day}/{name}")
async def download(day: str, name: str):
    target = (UPLOAD_ROOT / day / name).resolve()
    # Guard against path traversal — must stay inside UPLOAD_ROOT.
    if UPLOAD_ROOT not in target.parents or not target.is_file():
        return JSONResponse({"error": "Not found"}, status_code=404)
    return FileResponse(target, filename=name)


@app.get("/manifest.webmanifest")
async def manifest():
    return JSONResponse(
        {
            "name": "FTransfer",
            "short_name": "FTransfer",
            "description": "Send files from your phone to the PC.",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "background_color": "#0f1216",
            "theme_color": "#0f1216",
            "icons": [
                {"src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png"},
                {
                    "src": "/static/maskable-512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "maskable",
                },
            ],
        },
        media_type="application/manifest+json",
    )


@app.get("/sw.js")
async def service_worker():
    return Response(SERVICE_WORKER_JS, media_type="application/javascript")


SERVICE_WORKER_JS = """
const CACHE = 'ftransfer-v1';
const SHELL = ['/', '/manifest.webmanifest', '/static/icon-192.png', '/static/icon-512.png'];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;                 // never cache uploads
  if (url.pathname.startsWith('/upload') || url.pathname.startsWith('/api') || url.pathname.startsWith('/download')) return;
  e.respondWith(
    fetch(e.request).then(r => {
      const copy = r.clone();
      caches.open(CACHE).then(c => c.put(e.request, copy)).catch(() => {});
      return r;
    }).catch(() => caches.match(e.request).then(m => m || caches.match('/')))
  );
});
"""


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0f1216">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="FTransfer">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="apple-touch-icon" href="/static/apple-touch-icon.png">
<link rel="icon" href="/static/icon-192.png">
<title>FTransfer</title>
<style>
  :root { --bg:#0f1216; --card:#1a1f27; --edge:#2a323d; --fg:#e8edf3; --mut:#8b97a7;
          --accent:#3b82f6; --ok:#22c55e; --err:#ef4444;
          --nav:72px; --top:env(safe-area-inset-top); }
  * { box-sizing:border-box; -webkit-tap-highlight-color:transparent; }
  html,body { margin:0; height:100%; }
  body { background:var(--bg); color:var(--fg); font:16px/1.4 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }
  header { text-align:center; padding:calc(16px + var(--top)) 16px 10px; }
  header h1 { font-size:22px; margin:0; letter-spacing:.3px; }
  header .sub { color:var(--mut); font-size:13px; margin-top:2px; }
  main { max-width:560px; margin:0 auto; padding:8px 16px calc(var(--nav) + 24px + env(safe-area-inset-bottom));
         width:100%; }
  .view { display:none; }
  .view.active { display:block; }

  .drop { border:2px dashed var(--edge); border-radius:16px; background:var(--card);
          padding:34px 20px; text-align:center; transition:border-color .15s,background .15s; cursor:pointer; }
  .drop.hot { border-color:var(--accent); background:#1e2836; }
  .drop .icon { font-size:44px; line-height:1; }
  .drop p { margin:12px 0 0; color:var(--mut); font-size:14px; }
  .btn { display:block; width:100%; margin-top:14px; padding:14px 22px; border-radius:12px; border:0;
         background:var(--accent); color:#fff; font-size:16px; font-weight:600; cursor:pointer; }
  .btn:active { filter:brightness(.92); }
  .btn.secondary { background:var(--edge); }
  .btn:disabled { opacity:.5; }
  input[type=file] { display:none; }
  .list { margin-top:16px; display:flex; flex-direction:column; gap:10px; }
  .row { background:var(--card); border:1px solid var(--edge); border-radius:12px; padding:12px 14px; }
  .row .top { display:flex; justify-content:space-between; gap:10px; align-items:baseline; }
  .row .nm { font-size:14px; word-break:break-all; }
  .row .sz { color:var(--mut); font-size:12px; white-space:nowrap; }
  .bar { height:6px; border-radius:6px; background:var(--edge); margin-top:9px; overflow:hidden; }
  .bar > i { display:block; height:100%; width:0; background:var(--accent); transition:width .12s; }
  .row.done .bar > i { background:var(--ok); }
  .row.fail .bar > i { background:var(--err); width:100% !important; }
  .row .st { font-size:11px; color:var(--mut); margin-top:6px; }
  .row.done .st { color:var(--ok); }
  .row.fail .st { color:var(--err); }
  .toast { margin-top:14px; text-align:center; font-size:13px; color:var(--ok); min-height:18px; }

  a.frow { text-decoration:none; color:inherit; display:flex; align-items:center; gap:12px;
           background:var(--card); border:1px solid var(--edge); border-radius:12px; padding:12px 14px; }
  a.frow:active { background:#1e2836; }
  .frow .ic { font-size:22px; flex:0 0 auto; }
  .frow .meta { min-width:0; flex:1; }
  .frow .nm { font-size:14px; word-break:break-all; }
  .frow .when { color:var(--mut); font-size:12px; margin-top:2px; }
  .frow .sz { color:var(--mut); font-size:12px; white-space:nowrap; flex:0 0 auto; }
  .empty { text-align:center; color:var(--mut); font-size:14px; padding:40px 10px; }
  .refresh { color:var(--accent); background:none; border:0; font-size:13px; cursor:pointer; padding:0; }
  .uphead { display:flex; justify-content:space-between; align-items:center; margin-bottom:4px; }
  .uphead .cnt { color:var(--mut); font-size:13px; }

  nav { position:fixed; left:0; right:0; bottom:0; height:calc(var(--nav) + env(safe-area-inset-bottom));
        padding-bottom:env(safe-area-inset-bottom); background:#12161c; border-top:1px solid var(--edge);
        display:flex; z-index:10; }
  nav button { flex:1; background:none; border:0; color:var(--mut); font-size:11px; font-weight:600;
               display:flex; flex-direction:column; align-items:center; justify-content:center; gap:3px; cursor:pointer; }
  nav button .ni { font-size:22px; line-height:1; }
  nav button.on { color:var(--accent); }
</style>
</head>
<body>
  <header>
    <h1>FTransfer</h1>
    <div class="sub" id="sub">Drop files here — saved to today's folder on the PC.</div>
  </header>

  <main>
    <!-- UPLOAD -->
    <section class="view active" id="view-upload">
      <label class="drop" id="drop">
        <div class="icon">📁</div>
        <p>Tap to choose files, or drag &amp; drop</p>
        <input type="file" id="file" multiple>
      </label>
      <button class="btn" id="pick">Choose files</button>
      <button class="btn secondary" id="send" disabled>Upload</button>
      <div class="list" id="queue"></div>
      <div class="toast" id="toast"></div>
    </section>

    <!-- UPLOADED -->
    <section class="view" id="view-files">
      <div class="uphead">
        <span class="cnt" id="fcount">Loading…</span>
        <button class="refresh" id="refresh">Refresh</button>
      </div>
      <div class="list" id="filelist"></div>
    </section>
  </main>

  <nav>
    <button id="tab-upload" class="on"><span class="ni">⬆️</span>Upload</button>
    <button id="tab-files"><span class="ni">🗂️</span>Uploaded</button>
  </nav>

<script>
  const $ = id => document.getElementById(id);
  const fmt = b => { const u=['B','KB','MB','GB','TB']; let i=0; while(b>=1024&&i<u.length-1){b/=1024;i++;} return b.toFixed(b<10&&i>0?1:0)+' '+u[i]; };
  const iconFor = n => { const e=(n.split('.').pop()||'').toLowerCase();
    if(['jpg','jpeg','png','gif','webp','heic','bmp','svg'].includes(e)) return '🖼️';
    if(['mp4','mov','mkv','avi','webm','m4v'].includes(e)) return '🎬';
    if(['mp3','wav','flac','aac','m4a','ogg'].includes(e)) return '🎵';
    if(['zip','rar','7z','tar','gz'].includes(e)) return '🗜️';
    if(['pdf'].includes(e)) return '📕';
    if(['doc','docx','txt','md','rtf'].includes(e)) return '📄';
    return '📎'; };

  /* ---------- tabs ---------- */
  function show(which) {
    const up = which === 'upload';
    $('view-upload').classList.toggle('active', up);
    $('view-files').classList.toggle('active', !up);
    $('tab-upload').classList.toggle('on', up);
    $('tab-files').classList.toggle('on', !up);
    $('sub').textContent = up ? "Drop files here — saved to today's folder on the PC."
                              : "All files received, newest first.";
    if(!up) loadFiles();
  }
  $('tab-upload').onclick = () => show('upload');
  $('tab-files').onclick = () => show('files');

  /* ---------- uploaded list ---------- */
  async function loadFiles() {
    $('fcount').textContent = 'Loading…';
    try {
      const r = await fetch('/api/files', {cache:'no-store'});
      const d = await r.json();
      const list = $('filelist'); list.innerHTML = '';
      if(!d.files.length){ $('fcount').textContent=''; list.innerHTML='<div class="empty">No files yet.<br>Upload something from the Upload tab.</div>'; return; }
      $('fcount').textContent = d.files.length + ' file' + (d.files.length>1?'s':'');
      d.files.forEach(f => {
        const a = document.createElement('a');
        a.className='frow'; a.href=f.url; a.target='_blank'; a.rel='noopener';
        a.innerHTML = `<span class="ic"></span>
          <span class="meta"><div class="nm"></div><div class="when"></div></span>
          <span class="sz">${fmt(f.size)}</span>`;
        a.querySelector('.ic').textContent = iconFor(f.name);
        a.querySelector('.nm').textContent = f.name;
        a.querySelector('.when').textContent = f.when;
        list.appendChild(a);
      });
    } catch(_) { $('fcount').textContent='Could not load files'; }
  }
  $('refresh').onclick = loadFiles;

  /* ---------- upload ---------- */
  const fileInput=$('file'), drop=$('drop'), pick=$('pick'), send=$('send'), queue=$('queue'), toast=$('toast');
  let files = [];

  function render() {
    queue.innerHTML='';
    files.forEach((f,idx) => {
      const row=document.createElement('div'); row.className='row'; row.id='row'+idx;
      row.innerHTML=`<div class="top"><span class="nm"></span><span class="sz">${fmt(f.size)}</span></div>
        <div class="bar"><i></i></div><div class="st">Ready</div>`;
      row.querySelector('.nm').textContent=f.name;
      queue.appendChild(row);
    });
    send.disabled = files.length===0;
  }
  function addFiles(fl){ files=files.concat(Array.from(fl)); render(); toast.textContent=''; }

  pick.onclick=()=>fileInput.click();
  fileInput.onchange=()=>{ addFiles(fileInput.files); fileInput.value=''; };
  ['dragenter','dragover'].forEach(e=>drop.addEventListener(e,ev=>{ev.preventDefault();drop.classList.add('hot');}));
  ['dragleave','drop'].forEach(e=>drop.addEventListener(e,ev=>{ev.preventDefault();drop.classList.remove('hot');}));
  drop.addEventListener('drop',ev=>{ if(ev.dataTransfer.files.length) addFiles(ev.dataTransfer.files); });

  send.onclick=()=>{
    if(!files.length) return;
    send.disabled=pick.disabled=true;
    const fd=new FormData();
    files.forEach(f=>fd.append('files',f,f.name));
    files.forEach((_,i)=>{const r=$('row'+i);r.className='row';r.querySelector('.st').textContent='Uploading…';});

    const xhr=new XMLHttpRequest();
    xhr.open('POST','/upload');
    xhr.upload.onprogress=e=>{
      if(!e.lengthComputable) return;
      const pct=(e.loaded/e.total*100).toFixed(1);
      files.forEach((_,i)=>{$('row'+i).querySelector('.bar > i').style.width=pct+'%';});
    };
    xhr.onload=()=>{
      let ok=false,data={};
      try{ data=JSON.parse(xhr.responseText); ok=xhr.status===200&&data.ok; }catch(_){}
      files.forEach((_,i)=>{const r=$('row'+i);
        r.classList.add(ok?'done':'fail'); r.querySelector('.bar > i').style.width='100%';
        r.querySelector('.st').textContent=ok?'Saved ✓':'Failed';});
      if(ok){ toast.style.color='var(--ok)'; toast.textContent=`Saved ${data.saved.length} file(s) → ${data.day}`; files=[]; }
      else { toast.style.color='var(--err)'; toast.textContent=(data.error||'Upload failed'); }
      pick.disabled=false; send.disabled=files.length===0;
    };
    xhr.onerror=()=>{
      files.forEach((_,i)=>{const r=$('row'+i);r.classList.add('fail');r.querySelector('.st').textContent='Network error';});
      toast.style.color='var(--err)'; toast.textContent='Network error';
      pick.disabled=false; send.disabled=false;
    };
    xhr.send(fd);
  };

  if('serviceWorker' in navigator){ navigator.serviceWorker.register('/sw.js').catch(()=>{}); }
</script>
</body>
</html>"""
