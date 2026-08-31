<div align="center">

# 📁 FTransfer

### Phone → PC file drop, with zero friction.

A tiny, self-hosted **FastAPI** app that turns your computer into an AirDrop-style
landing pad. Open it on your phone, tap, upload — files land straight on your PC.
**No size limit. No accounts. No cloud. No nonsense.**

Installable as a **PWA**, so it lives on your home screen like a real app.

<br>

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![PWA](https://img.shields.io/badge/PWA-installable-5A0FC8?logo=pwa&logoColor=white)
![Self-hosted](https://img.shields.io/badge/self--hosted-LAN-22c55e)
![License](https://img.shields.io/badge/license-MIT-blue)

</div>

---

## Why

You took 40 photos on your phone and want them on your PC. The cable is missing,
the cloud wants a login, and email caps at 25 MB. FTransfer is the boring, instant
answer: both devices on the same Wi-Fi, one page, drag-and-drop. That's the whole product.

## ✨ Features

- 📦 **No size limit** — files stream to disk in 1 MiB chunks, so a 4 GB video
  never touches RAM.
- 🗂️ **Multi-file uploads** — pick or drag a whole batch at once, with a live
  per-batch progress bar.
- 📅 **Auto-organized** — everything is filed under `uploads/YYYY-MM-DD/` so your
  drops sort themselves by day.
- 📱 **Mobile-first UI** — big tap targets, dark theme, safe-area aware. Feels
  native on a phone.
- 🏠 **Installable PWA** — "Add to Home Screen" and it opens fullscreen with its
  own icon, on iOS and Android.
- 🔎 **Uploaded tab** — browse everything you've ever sent, newest first, and tap
  any file to open or download it back.
- 🔒 **Yours only** — runs on your LAN, saves to your disk. Nothing leaves the house.
- 🧼 **Safe by default** — filenames are sanitized, collisions auto-rename
  (`clip (1).mp4`), and downloads are path-traversal guarded.

## 🚀 Quick start

```bat
:: Windows — first run creates the venv and installs deps automatically
run.bat
```

Then, from any device **on the same Wi-Fi**, open the URL the script prints:

```
From your phone:  http://192.168.1.34:8987
On this PC:        http://localhost:8987
```

That's it. Drop files on the phone, find them on the PC under `uploads/`.

> **Not on Windows?** Just run it directly:
> ```bash
> pip install -r requirements.txt
> uvicorn app:app --host 0.0.0.0 --port 8987
> ```

## 📲 Install it on your phone

**iPhone (Safari):** open the page → Share → **Add to Home Screen**.
**Android (Chrome):** open the page → menu → **Install app**.

It'll get the FTransfer icon and launch fullscreen, no browser chrome.

## 🗃️ Where files go

```
FTransfer/
└── uploads/
    └── 2026-08-31/
        ├── vacation.mp4
        ├── receipt.pdf
        └── screenshot.png
```

The `uploads/` folder is created automatically on first launch and is **git-ignored** —
your files never end up in the repo.

## 🧩 How it works

A single FastAPI app serves the mobile web UI and three small endpoints:

| Route | Purpose |
|-------|---------|
| `POST /upload` | Streams each part straight to `uploads/{date}/` |
| `GET /api/files` | Lists every stored file, newest first |
| `GET /download/{day}/{name}` | Serves a file back (traversal-guarded) |

Plus `manifest.webmanifest`, `sw.js`, and icons to make it an installable PWA.
The frontend is one dependency-free HTML page — no build step, no framework.

## ⚙️ Configuration

| What | Where | Default |
|------|-------|---------|
| Port | `run.bat` / uvicorn `--port` | `8987` |
| Save location | `UPLOAD_ROOT` in `app.py` | `./uploads` |
| Bind address | uvicorn `--host` | `0.0.0.0` (whole LAN) |

## 🛠️ Tech

FastAPI · Starlette · Uvicorn · vanilla HTML/CSS/JS · Service Worker + Web App Manifest.

## ⚠️ Note

FTransfer has **no authentication** by design — it's built for a trusted home/office
LAN. Don't expose it directly to the public internet.

## 📄 License

MIT — do whatever you want with it.
