# ═══════════════════════════════════════════════════════════════════════
#  🚀 ULTRA ADVANCED UNZIPPER + LINK DOWNLOADER BOT  v2.0
#  Admin: @F88UF  |  Channel: @F88UF9844
#  ─────────────────────────────────────────────────────────────────────
#  Features:
#    ✅ Unzip: ZIP, 7Z, RAR, TAR, GZ, BZ2, XZ
#    ✅ Link download: YouTube, TikTok, Instagram, Twitter/X, 1000+ sites
#    ✅ Direct links: .mp4, .zip, .rar, .jpg, .pdf, etc.
#    ✅ Output chooser: send to bot OR channel (button)
#    ✅ Cancel / Stop / Back buttons
#    ✅ Live progress bar
#    ✅ Video → streamable, Image → photo, Audio → audio, Docs → document
#    ✅ Policy accept gate
#    ✅ 24/7 keep-alive (UptimeRobot)
#    ✅ 1000+ concurrent users
#    ✅ Forward cleaner (strip source)
#    ✅ Auto-extract archives found inside links
#  ─────────────────────────────────────────────────────────────────────
#  Run:  python main.py
# ═══════════════════════════════════════════════════════════════════════

import subprocess, sys, os, threading

# ── Auto-install ─────────────────────────────────────────────────────────
_REQUIRED = ["telethon", "cryptography", "aiohttp", "aiofiles", "yt-dlp", "requests"]
for _pkg in _REQUIRED:
    try:
        __import__(_pkg.replace("-", "_"))
    except ImportError:
        print(f"📦 Installing {_pkg}...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet", _pkg],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

import asyncio, zipfile, shutil, tarfile, time, re, logging, json
from pathlib import Path
from base64 import b64decode
from urllib.parse import urlparse
from http.server import BaseHTTPRequestHandler, HTTPServer

import aiohttp
import aiofiles
import yt_dlp
from telethon import TelegramClient, events, Button
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.tl.types import ChannelParticipantAdmin, ChannelParticipantCreator

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.WARNING)

# ═══════════════════════════════════════════════════════════════════════
#  CREDENTIALS
#  To encode a new value:
#    python3 -c "import base64; print(base64.b64encode(b'YOUR_VALUE').decode())"
# ═══════════════════════════════════════════════════════════════════════
_AI = int(b64decode("Mjk2NDM0NzQ=").decode())
_AH = b64decode("NDkxNjMzZjAzNGMxYjUwYjFiYzBmMWU0ZDJiNDI2ZTM=").decode()
_BT = b64decode("ODcyMzk2NTI5MzpBQUdfd0hOZTkzNERNVHVTRlpZTFhNNDVXajN3dEdMTEdDUQ==").decode()

# ═══════════════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════════════
ADMIN_USERNAME   = "F88UF"
CHANNEL_HANDLE   = "@F88UF9844"
CHANNEL_LINK     = "https://t.me/F88UF9844"
BOT_TAG          = "@F88UF_FILEUNZIPBOT"
AUTO_DEL_SEC     = 300           # 5 min auto-delete in bot chat only
MAX_EXTRACT_JOBS = 20            # parallel extraction slots
MAX_LINK_JOBS    = 10            # parallel link-download slots
KEEP_ALIVE_PORT  = 8080          # UptimeRobot pings this port
WORK_DIR         = Path("/tmp/uzbot")
SESSIONS_FILE    = Path("/tmp/uzbot_accepted.json")
WORK_DIR.mkdir(parents=True, exist_ok=True)

ARCHIVE_EXTS = {".zip", ".7z", ".rar", ".tar", ".gz", ".tgz", ".bz2", ".xz"}
VIDEO_EXTS   = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
                ".m4v", ".mpg", ".mpeg", ".3gp", ".ts", ".m2ts", ".vob", ".divx"}
IMAGE_EXTS   = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"}
AUDIO_EXTS   = {".mp3", ".flac", ".aac", ".ogg", ".wav", ".m4a", ".opus", ".wma"}

SUPPORTED_SITES = (
    "YouTube • TikTok • Instagram • Twitter/X • Facebook\n"
    "Vimeo • Twitch • Dailymotion • Reddit • SoundCloud\n"
    "Pinterest • Bandcamp + 1000s more via yt-dlp\n"
    "Direct links: .mp4 .zip .rar .pdf .jpg .mp3 etc."
)

POLICY_TEXT = (
    "📋 *Terms of Use — Please Read*\n\n"
    "By tapping Accept, you agree:\n\n"
    "1️⃣ This bot is a *utility tool* only.\n"
    "2️⃣ You are *100% responsible* for files you process.\n"
    "3️⃣ Do NOT use for illegal, pirated, or 18+ content.\n"
    "4️⃣ Admin bears *zero liability* for any misuse.\n"
    "5️⃣ Abuse → permanent ban, no appeal.\n\n"
    "⚠️ _All legal responsibility rests with the user._"
)

# ═══════════════════════════════════════════════════════════════════════
#  STATE
# ═══════════════════════════════════════════════════════════════════════
client = TelegramClient("uzbot_session", _AI, _AH).start(bot_token=_BT)

_flag_map: dict[str, dict]    = {}   # active job flags
_dest_channels: dict[int, str] = {}  # per-chat channel
_fwd_store: dict[str, object] = {}   # forwarded events pending action
# pending output-choice: job_id → {files, chat_id, flag_key, source_url, out_dir, zip_path}
_pending_output: dict[str, dict] = {}

_sem_extract = asyncio.Semaphore(MAX_EXTRACT_JOBS)
_sem_link    = asyncio.Semaphore(MAX_LINK_JOBS)

# ── Policy persistence ───────────────────────────────────────────────────
def _load_accepted() -> set:
    try:
        if SESSIONS_FILE.exists():
            return set(json.loads(SESSIONS_FILE.read_text()))
    except Exception:
        pass
    return set()

def _save_accepted(s: set):
    try:
        SESSIONS_FILE.write_text(json.dumps(list(s)))
    except Exception:
        pass

_policy_accepted: set = _load_accepted()

# ═══════════════════════════════════════════════════════════════════════
#  KEEP-ALIVE SERVER (for UptimeRobot 24/7)
# ═══════════════════════════════════════════════════════════════════════
class _PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot alive!")
    def log_message(self, *_):
        pass

def _start_keep_alive():
    srv = HTTPServer(("0.0.0.0", KEEP_ALIVE_PORT), _PingHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"🌐 Keep-alive server on port {KEEP_ALIVE_PORT}")

# ═══════════════════════════════════════════════════════════════════════
#  UTILS
# ═══════════════════════════════════════════════════════════════════════
def human(n: float) -> str:
    for u in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024: return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"

def pbar(done: int, total: int, w: int = 16) -> str:
    p = min(done / total, 1.0) if total else 0
    f = int(w * p)
    return f"[{'█'*f}{'░'*(w-f)}] {p*100:.0f}%"

def _ext(name: str) -> str:
    return Path(str(name)).suffix.lower()

def is_archive(name: str) -> bool:
    n = name.lower()
    return n.endswith(".tar.gz") or n.endswith(".tar.bz2") or _ext(n) in ARCHIVE_EXTS

def is_video(name: str) -> bool:  return _ext(name) in VIDEO_EXTS
def is_image(name: str) -> bool:  return _ext(name) in IMAGE_EXTS
def is_audio(name: str) -> bool:  return _ext(name) in AUDIO_EXTS

def extract_urls(text: str) -> list:
    return re.findall(r'https?://[^\s<>"\']+', text or "")

def strip_promo(text: str) -> str:
    if not text: return ""
    text = re.sub(r"@\w+", f"@{ADMIN_USERNAME}", text)
    text = re.sub(r"https?://t\.me/\S+", CHANNEL_LINK, text)
    return text.strip()

def file_cap(fname: str, sz: int, idx: int, total: int, src: str = "") -> str:
    s = f"🔗 `{src[:60]}`\n" if src else ""
    return f"📄 `{fname}`\n{s}📦 {human(sz)} • {idx}/{total}\n\n_via {BOT_TAG}_"

def bot_footer() -> str:
    return f"🤖 {BOT_TAG}"

async def auto_del(msg, delay: int = AUTO_DEL_SEC):
    await asyncio.sleep(delay)
    try: await msg.delete()
    except Exception: pass

async def cleanup(*paths):
    for p in paths:
        try:
            if os.path.isfile(p):   os.remove(p)
            elif os.path.isdir(p):  shutil.rmtree(p)
        except Exception: pass

# ── Shared button builders ────────────────────────────────────────────────
def cancel_row(flag_key: str) -> list:
    return [[Button.inline("❌ Cancel", data=f"stop:{flag_key}")]]

def output_choice_buttons(job_id: str, has_channel: bool, channel: str = "") -> list:
    rows = [[Button.inline("📲 Send here (in bot)", data=f"out:here:{job_id}")]]
    if has_channel:
        rows.append([Button.inline(f"📢 Send to {channel}", data=f"out:ch:{job_id}")])
    rows.append([Button.inline("❌ Cancel — Don't Send", data=f"out:cancel:{job_id}")])
    return rows

def done_buttons() -> list:
    return [
        [Button.inline("🏠 Main Menu", data="mainmenu"),
         Button.inline("📢 Channel", url=CHANNEL_LINK)],
    ]

# ═══════════════════════════════════════════════════════════════════════
#  POLICY GATE
# ═══════════════════════════════════════════════════════════════════════
async def check_policy(event) -> bool:
    uid = event.sender_id
    if uid in _policy_accepted:
        return True
    await event.reply(
        POLICY_TEXT,
        parse_mode="markdown",
        buttons=[[Button.inline("✅ I Accept & Start", data=f"policy:{uid}")]],
    )
    return False

@client.on(events.CallbackQuery(pattern=rb"policy:(\d+)"))
async def cb_policy(event):
    uid = event.sender_id   # always use the person who clicked
    _policy_accepted.add(uid)
    _save_accepted(_policy_accepted)
    await event.answer("✅ Accepted!", alert=False)
    try:
        await event.edit(
            "✅ *Policy Accepted!*\n\nSend /start to begin.",
            parse_mode="markdown",
            buttons=[[Button.inline("🏠 Start", data="mainmenu")]],
        )
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════════════
#  CHANNEL ADMIN CHECK
# ═══════════════════════════════════════════════════════════════════════
async def bot_is_admin(channel) -> bool:
    try:
        me   = await client.get_me()
        part = await client(GetParticipantRequest(channel, me.id))
        return isinstance(part.participant, (ChannelParticipantAdmin, ChannelParticipantCreator))
    except Exception:
        return False

# ═══════════════════════════════════════════════════════════════════════
#  EXTRACTION ENGINE
# ═══════════════════════════════════════════════════════════════════════
async def extract_archive(zip_path: Path, out_dir: Path, flag: dict, status_cb) -> list | None:
    ext  = zip_path.suffix.lower()
    name = zip_path.name.lower()
    out  : list[Path] = []

    async def upd(t: str):
        try: await status_cb(t)
        except Exception: pass

    # ZIP
    if ext == ".zip":
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                mbs = zf.infolist()
                total = sum(m.file_size for m in mbs) or 1
                done = t0 = 0
                for m in mbs:
                    if flag["stop"]: return None
                    zf.extract(m, out_dir)
                    done += m.file_size
                    p = out_dir / m.filename
                    if p.is_file(): out.append(p)
                    if time.time() - t0 > 1.8:
                        await upd(
                            f"⚡ *Extracting ZIP*\n`{pbar(done, total)}`\n"
                            f"{human(done)} / {human(total)}\n"
                            f"📄 `{Path(m.filename).name[:45]}`"
                        )
                        t0 = time.time()
        except zipfile.BadZipFile:
            await upd("❌ Corrupted ZIP file."); return []

    # TAR family
    elif ext in (".tar", ".gz", ".tgz", ".bz2", ".xz") or name.endswith((".tar.gz", ".tar.bz2")):
        try:
            with tarfile.open(zip_path, "r:*") as tf:
                mbs = tf.getmembers()
                total = sum(m.size for m in mbs) or 1
                done = t0 = 0
                for m in mbs:
                    if flag["stop"]: return None
                    tf.extract(m, out_dir, set_attrs=False)
                    done += m.size
                    p = out_dir / m.name
                    if p.is_file(): out.append(p)
                    if time.time() - t0 > 1.8:
                        await upd(
                            f"⚡ *Extracting TAR*\n`{pbar(done, total)}`\n"
                            f"{human(done)} / {human(total)}"
                        )
                        t0 = time.time()
        except Exception as e:
            await upd(f"❌ TAR error: `{e}`"); return []

    # 7Z / RAR
    elif ext in (".7z", ".rar"):
        if subprocess.run(["which", "7z"], capture_output=True).returncode != 0:
            await upd("⏳ Installing 7zip (first time only)…")
            subprocess.run(["apt-get", "install", "-y", "p7zip-full"], capture_output=True)
        await upd(f"⚡ *Extracting {ext.upper()}*…\n⏳ Please wait…")
        proc = await asyncio.create_subprocess_exec(
            "7z", "x", str(zip_path), f"-o{out_dir}", "-y",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
        )
        t0 = time.time()
        while proc.returncode is None:
            if flag["stop"]: proc.kill(); return None
            await asyncio.sleep(0.8)
            if time.time() - t0 > 2:
                await upd(f"⚡ *Extracting {ext.upper()}*…\n⏳ Running…")
                t0 = time.time()
        await proc.wait()
        if proc.returncode != 0:
            err = (await proc.stderr.read()).decode(errors="ignore")[:250]
            await upd(f"❌ 7z error:\n`{err}`"); return []
        for root, _, fs in os.walk(out_dir):
            for f in fs: out.append(Path(root) / f)
    else:
        await upd(f"❌ Unsupported format: `{ext}`"); return []

    return out

# ═══════════════════════════════════════════════════════════════════════
#  LINK DOWNLOADER
# ═══════════════════════════════════════════════════════════════════════
async def download_link(url: str, out_dir: Path, flag: dict, status_cb) -> list | None:
    out: list[Path] = []

    async def upd(t: str):
        try: await status_cb(t)
        except Exception: pass

    await upd(f"🔗 *Analyzing link…*\n`{url[:70]}`\n⏳ Please wait…")

    loop = asyncio.get_event_loop()
    ydl_out = str(out_dir / "%(title).80s.%(ext)s")

    def _ydl():
        try:
            with yt_dlp.YoutubeDL({
                "outtmpl"             : ydl_out,
                "quiet"               : True,
                "no_warnings"         : True,
                "merge_output_format" : "mp4",
                "format"              : "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "noplaylist"          : True,
                "socket_timeout"      : 30,
                "retries"             : 5,
                "fragment_retries"    : 5,
                "ignoreerrors"        : False,
                "geo_bypass"          : True,
                "http_headers"        : {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                                  "Chrome/120.0.0.0 Safari/537.36"
                },
            }) as ydl:
                return ydl.extract_info(url, download=True)
        except Exception as e:
            return e

    result = await loop.run_in_executor(None, _ydl)

    if isinstance(result, Exception):
        # Fallback: direct HTTP download
        await upd(f"🌐 *Direct HTTP download…*\n`{url[:70]}`")
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(url, timeout=aiohttp.ClientTimeout(total=600)) as resp:
                    if resp.status != 200:
                        await upd(f"❌ HTTP {resp.status}: cannot reach link."); return []

                    total = int(resp.headers.get("Content-Length", 0))
                    cd = resp.headers.get("Content-Disposition", "")
                    m = re.search(r'filename="?([^";]+)"?', cd)
                    fname = m.group(1).strip() if m else (Path(urlparse(url).path).name or "file")
                    if not Path(fname).suffix:
                        ct = resp.content_type or ""
                        for ctype, ex in {
                            "video/mp4": ".mp4", "video/webm": ".webm",
                            "image/jpeg": ".jpg", "image/png": ".png",
                            "image/gif": ".gif", "application/zip": ".zip",
                            "application/x-rar": ".rar", "application/pdf": ".pdf",
                        }.items():
                            if ctype in ct: fname += ex; break

                    dl_path = out_dir / fname
                    done = t0 = 0
                    async with aiofiles.open(dl_path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(65536):
                            if flag["stop"]: return None
                            await f.write(chunk)
                            done += len(chunk)
                            if time.time() - t0 > 1.8:
                                pb = pbar(done, total) if total else "⏳ Downloading"
                                await upd(
                                    f"📥 *Downloading*\n`{fname[:50]}`\n"
                                    f"`{pb}`\n{human(done)}"
                                    + (f" / {human(total)}" if total else "")
                                )
                                t0 = time.time()
                    out.append(dl_path)
        except Exception as e:
            await upd(f"❌ Download failed: `{e}`"); return []
    else:
        for fp in out_dir.iterdir():
            if fp.is_file(): out.append(fp)

    return out

# ═══════════════════════════════════════════════════════════════════════
#  SEND FILES
# ═══════════════════════════════════════════════════════════════════════
async def send_files(
    target, files: list, flag: dict, status_msg, flag_key: str, src: str = ""
) -> tuple[int, list]:
    total = len(files)
    sent  = 0
    skip  = []

    for i, fp in enumerate(files, 1):
        if flag["stop"]: break
        if not fp.exists(): continue
        sz   = fp.stat().st_size
        name = fp.name

        try:
            await status_msg.edit(
                f"📤 *Sending* `{name}`\n"
                f"`{pbar(i-1, total)}`\n"
                f"_{i-1}/{total} done_",
                parse_mode="markdown",
                buttons=[[Button.inline("⏹ Stop Sending", data=f"stop:{flag_key}")]],
            )
        except Exception:
            pass

        cap = file_cap(name, sz, i, total, src)
        try:
            if is_video(name):
                await client.send_file(
                    target, str(fp), caption=cap, parse_mode="markdown",
                    supports_streaming=True, attributes=[],
                )
            elif is_image(name):
                await client.send_file(target, str(fp), caption=cap, parse_mode="markdown")
            elif is_audio(name):
                await client.send_file(
                    target, str(fp), caption=cap, parse_mode="markdown", voice_note=False,
                )
            else:
                await client.send_file(
                    target, str(fp), caption=cap, parse_mode="markdown", force_document=True,
                )
            sent += 1
        except Exception as e:
            skip.append(f"`{name}`: {str(e)[:80]}")

    return sent, skip

# ═══════════════════════════════════════════════════════════════════════
#  OUTPUT CHOICE HANDLER (button: send here / send to channel)
# ═══════════════════════════════════════════════════════════════════════
@client.on(events.CallbackQuery(pattern=rb"out:(here|ch|cancel):(.+)"))
async def cb_output_choice(event):
    data    = event.data.decode()
    parts   = data.split(":", 2)
    mode    = parts[1]
    job_id  = parts[2]

    pending = _pending_output.pop(job_id, None)
    if not pending:
        await event.answer("⚠️ Job expired or already started.", alert=False)
        return

    await event.answer()

    files      = pending["files"]
    chat_id    = pending["chat_id"]
    flag_key   = pending["flag_key"]
    flag       = _flag_map.get(flag_key, {"stop": False})
    src        = pending.get("source_url", "")
    out_dir    = pending.get("out_dir")
    zip_path   = pending.get("zip_path")
    status_msg = pending["status_msg"]
    fname      = pending.get("fname", "")

    if mode == "cancel":
        flag["stop"] = True
        _flag_map.pop(flag_key, None)
        await cleanup(*(p for p in [zip_path, out_dir] if p))
        try:
            await status_msg.edit(
                "🚫 *Cancelled.* Files not sent.",
                parse_mode="markdown",
                buttons=done_buttons(),
            )
        except Exception:
            pass
        asyncio.create_task(auto_del(status_msg, 60))
        return

    ch = _dest_channels.get(chat_id)
    if mode == "ch" and not ch:
        await event.answer("❌ No channel set. Use /setchannel first.", alert=True)
        _pending_output[job_id] = pending  # put it back
        return

    target = ch if mode == "ch" else chat_id
    target_label = f"📢 {ch}" if mode == "ch" else "📲 bot"

    total_sz = sum(f.stat().st_size for f in files if f.exists())
    try:
        await status_msg.edit(
            f"📤 *Sending {len(files)} file(s) to {target_label}*\n"
            f"Total: `{human(total_sz)}`",
            parse_mode="markdown",
            buttons=[[Button.inline("⏹ Stop Sending", data=f"stop:{flag_key}")]],
        )
    except Exception:
        pass

    sent, skipped = await send_files(target, files, flag, status_msg, flag_key, src)

    lines = [f"🎉 *Done!*"]
    if fname: lines.append(f"📦 `{fname}`")
    lines.append(f"✅ Sent `{sent}/{len(files)}`  →  {target_label}")
    if skipped: lines.append(f"⚠️ Failed: `{len(skipped)}`")
    lines.append(f"\n{bot_footer()}")

    try:
        await status_msg.edit(
            "\n".join(lines),
            parse_mode="markdown",
            buttons=done_buttons(),
        )
    except Exception:
        pass

    _flag_map.pop(flag_key, None)
    await cleanup(*(p for p in [zip_path, out_dir] if p))
    # Only auto-delete in bot chat — not channel messages
    if mode != "ch":
        asyncio.create_task(auto_del(status_msg, AUTO_DEL_SEC))

# ═══════════════════════════════════════════════════════════════════════
#  PIPELINE — ARCHIVE FILE
# ═══════════════════════════════════════════════════════════════════════
async def pipeline_archive(event, zip_path: Path, fname: str):
    chat_id  = event.chat_id
    flag     = {"stop": False}
    flag_key = str(id(flag))
    _flag_map[flag_key] = flag

    jid     = f"{chat_id}_{int(time.time()*1000)}"
    out_dir = WORK_DIR / jid
    out_dir.mkdir(parents=True, exist_ok=True)

    status = await event.reply(
        f"⚡ *Extracting* `{fname}`…",
        parse_mode="markdown",
        buttons=cancel_row(flag_key),
    )

    async def cb(t):
        try: await status.edit(t, parse_mode="markdown", buttons=cancel_row(flag_key))
        except Exception: pass

    async with _sem_extract:
        files = await extract_archive(zip_path, out_dir, flag, cb)

    if files is None:
        await status.edit("🚫 *Cancelled.*", parse_mode="markdown", buttons=done_buttons())
        _flag_map.pop(flag_key, None)
        await cleanup(str(zip_path), str(out_dir))
        asyncio.create_task(auto_del(status, 30))
        return

    if not files:
        await status.edit(
            "❌ *Nothing extracted.* Bad archive?",
            parse_mode="markdown",
            buttons=done_buttons(),
        )
        _flag_map.pop(flag_key, None)
        await cleanup(str(zip_path), str(out_dir))
        asyncio.create_task(auto_del(status, 60))
        return

    total_sz  = sum(f.stat().st_size for f in files if f.exists())
    vid_count = sum(1 for f in files if is_video(f.name))
    img_count = sum(1 for f in files if is_image(f.name))
    arc_count = sum(1 for f in files if is_archive(f.name))

    ch    = _dest_channels.get(chat_id)
    job_id = jid
    _pending_output[job_id] = {
        "files": files, "chat_id": chat_id, "flag_key": flag_key,
        "source_url": "", "out_dir": str(out_dir), "zip_path": str(zip_path),
        "status_msg": status, "fname": fname,
    }

    summary = (
        f"✅ *Extracted!* `{fname}`\n\n"
        f"📦 `{len(files)}` file(s) — `{human(total_sz)}`\n"
        f"🎬 Videos: `{vid_count}` | 🖼 Images: `{img_count}`\n"
        f"📁 Docs/other: `{len(files) - vid_count - img_count}`"
    )
    if arc_count:
        summary += f"\n⚠️ Nested archives: `{arc_count}` (send separately)"
    summary += "\n\n*Where should I send the files?*"

    await status.edit(
        summary,
        parse_mode="markdown",
        buttons=output_choice_buttons(job_id, bool(ch), ch or ""),
    )

# ═══════════════════════════════════════════════════════════════════════
#  PIPELINE — LINK
# ═══════════════════════════════════════════════════════════════════════
async def pipeline_link(event, url: str):
    chat_id  = event.chat_id
    flag     = {"stop": False}
    flag_key = str(id(flag))
    _flag_map[flag_key] = flag

    jid     = f"{chat_id}_{int(time.time()*1000)}"
    out_dir = WORK_DIR / jid
    out_dir.mkdir(parents=True, exist_ok=True)

    status = await event.reply(
        f"🔗 *Link received!*\n`{url[:70]}`\n\n⏳ Analyzing…",
        parse_mode="markdown",
        buttons=cancel_row(flag_key),
    )

    async def cb(t):
        try: await status.edit(t, parse_mode="markdown", buttons=cancel_row(flag_key))
        except Exception: pass

    async with _sem_link:
        files = await download_link(url, out_dir, flag, cb)

    if files is None:
        await status.edit("🚫 *Cancelled.*", parse_mode="markdown", buttons=done_buttons())
        _flag_map.pop(flag_key, None)
        await cleanup(str(out_dir))
        asyncio.create_task(auto_del(status, 30))
        return

    if not files:
        await status.edit(
            "❌ *Could not download this link.*\n\n"
            "_Ensure the link is public and accessible._",
            parse_mode="markdown",
            buttons=done_buttons(),
        )
        _flag_map.pop(flag_key, None)
        await cleanup(str(out_dir))
        asyncio.create_task(auto_del(status, 60))
        return

    # Auto-extract any archives in the download
    archives     = [f for f in files if is_archive(f.name)]
    non_archives = [f for f in files if not is_archive(f.name)]
    all_files    = list(non_archives)

    for arch in archives:
        arch_out  = out_dir / f"x_{arch.stem}"
        arch_out.mkdir(exist_ok=True)
        arch_flag = {"stop": False}
        async def arch_cb(t): 
            try: await status.edit(t, parse_mode="markdown", buttons=cancel_row(flag_key))
            except Exception: pass
        extracted = await extract_archive(arch, arch_out, arch_flag, arch_cb)
        if extracted:
            all_files.extend(extracted)

    total_sz  = sum(f.stat().st_size for f in all_files if f.exists())
    vid_count = sum(1 for f in all_files if is_video(f.name))
    img_count = sum(1 for f in all_files if is_image(f.name))

    ch     = _dest_channels.get(chat_id)
    job_id = jid
    _pending_output[job_id] = {
        "files": all_files, "chat_id": chat_id, "flag_key": flag_key,
        "source_url": url, "out_dir": str(out_dir), "zip_path": None,
        "status_msg": status, "fname": "",
    }

    await status.edit(
        f"✅ *Downloaded!*\n\n"
        f"🔗 `{url[:60]}`\n\n"
        f"📦 `{len(all_files)}` file(s) — `{human(total_sz)}`\n"
        f"🎬 Videos: `{vid_count}` | 🖼 Images: `{img_count}`\n\n"
        f"*Where should I send the files?*",
        parse_mode="markdown",
        buttons=output_choice_buttons(job_id, bool(ch), ch or ""),
    )

# ═══════════════════════════════════════════════════════════════════════
#  FORWARD CLEANER
# ═══════════════════════════════════════════════════════════════════════
async def handle_forward(event, dest_channel=None):
    msg    = event.message
    target = dest_channel or event.chat_id
    cap    = strip_promo(msg.message or "")
    cap    = (cap + f"\n\n📢 {CHANNEL_LINK}") if cap else f"📢 {CHANNEL_LINK}"
    try:
        if msg.media:
            await client.send_file(target, msg.media, caption=cap, parse_mode="markdown")
        elif msg.message:
            await client.send_message(target, cap, parse_mode="markdown")
        confirm = await event.reply("✅ *Reposted clean!*\nSource removed.", parse_mode="markdown")
        try: await msg.delete()
        except Exception: pass
        asyncio.create_task(auto_del(confirm, 20))
    except Exception as e:
        await event.reply(f"❌ Failed: `{e}`", parse_mode="markdown")

# ═══════════════════════════════════════════════════════════════════════
#  COMMANDS
# ═══════════════════════════════════════════════════════════════════════

def _start_menu_buttons() -> list:
    return [
        [Button.inline("📦 Unzip Archive", data="info:unzip"),
         Button.inline("🔗 Link Download", data="info:link")],
        [Button.inline("📢 Set Channel", data="info:channel"),
         Button.inline("📊 Status", data="statusbtn")],
        [Button.inline("📋 Policy", data="info:policy"),
         Button.inline("💬 Help", data="help")],
        [Button.inline("📢 Join Our Channel", url=CHANNEL_LINK)],
    ]

async def _send_start(event_or_msg, is_edit=False):
    ch      = _dest_channels.get(getattr(event_or_msg, "chat_id", None))
    ch_line = f"\n📢 *Output channel:* `{ch}`" if ch else "\n📲 *Output:* bot (use /setchannel to change)"
    text = (
        f"👋 *Ultra Unzipper Bot*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Unzip: `.zip` `.7z` `.rar` `.tar` `.gz` `.bz2` `.xz`\n"
        f"🔗 Links: YouTube • TikTok • Instagram • 1000+ sites\n"
        f"📁 Direct links: `.mp4` `.zip` `.pdf` `.jpg` etc.\n"
        f"{ch_line}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Just *send a file* or *paste a URL* to start!"
    )
    if is_edit:
        try:
            await event_or_msg.edit(text, parse_mode="markdown", buttons=_start_menu_buttons())
        except Exception:
            pass
    else:
        await event_or_msg.reply(text, parse_mode="markdown", buttons=_start_menu_buttons())

@client.on(events.NewMessage(pattern="/start"))
async def cmd_start(event):
    uid = event.sender_id
    if uid not in _policy_accepted:
        await event.reply(
            POLICY_TEXT, parse_mode="markdown",
            buttons=[[Button.inline("✅ I Accept & Start", data=f"policy:{uid}")]],
        )
        return
    await _send_start(event)

@client.on(events.CallbackQuery(data=b"mainmenu"))
async def cb_mainmenu(event):
    await event.answer()
    await _send_start(event, is_edit=True)

@client.on(events.CallbackQuery(data=b"help"))
async def cb_help(event):
    await event.answer()
    await event.reply(
        "📖 *How to Use*\n\n"
        "*📦 Extract archive:*\nSend any `.zip` `.7z` `.rar` etc. file\n\n"
        "*🔗 Download link:*\nPaste any URL — video, image, archive\n\n"
        "*📢 Channel mode:*\n"
        "`/setchannel @yourchan` → files go to channel\n"
        "Bot must be admin in the channel!\n\n"
        "*🔄 Forward cleaner:*\nForward a message → bot reposts without source\n\n"
        "*❌ Cancel:* Press the button during any operation\n\n"
        f"Admin: @{ADMIN_USERNAME}",
        parse_mode="markdown",
        buttons=[[Button.inline("🏠 Back to Menu", data="mainmenu")]],
    )

@client.on(events.CallbackQuery(pattern=rb"info:(\w+)"))
async def cb_info(event):
    await event.answer()
    key = event.data.decode().split(":")[1]
    msgs = {
        "unzip": (
            "📦 *Archive Extraction*\n\n"
            "Supported: `.zip` `.7z` `.rar` `.tar` `.gz` `.tgz` `.bz2` `.xz`\n\n"
            "Just send the file → bot extracts and asks where to send!"
        ),
        "link": (
            "🔗 *Link Downloader*\n\n"
            f"{SUPPORTED_SITES}\n\n"
            "Paste any link → bot downloads → asks where to send!\n"
            "If link has a `.zip` inside — auto-extracts too."
        ),
        "channel": (
            "📢 *Channel Mode Setup*\n\n"
            "1. Make bot admin in your channel\n"
            "2. Send: `/setchannel @yourchannel`\n"
            "3. Now extracted files go there!\n\n"
            "Use `/clearchannel` to switch back to bot."
        ),
        "policy": POLICY_TEXT,
    }
    await event.reply(
        msgs.get(key, "❓ Unknown."),
        parse_mode="markdown",
        buttons=[[Button.inline("🏠 Back to Menu", data="mainmenu")]],
    )

@client.on(events.CallbackQuery(data=b"statusbtn"))
async def cb_status_btn(event):
    await event.answer(
        f"⚡ Active jobs: {len(_flag_map)} / {MAX_EXTRACT_JOBS+MAX_LINK_JOBS}",
        alert=False,
    )

@client.on(events.CallbackQuery(pattern=b"stop:"))
async def cb_cancel(event):
    flag_key = event.data.decode().split(":", 1)[1]
    flag     = _flag_map.get(flag_key)
    if not flag:
        await event.answer("⚠️ Already finished.", alert=False)
        return
    flag["stop"] = True
    await event.answer("🚫 Stop signal sent!", alert=False)
    try:
        await event.edit(
            "🚫 *Stopping…* please wait.",
            parse_mode="markdown",
        )
    except Exception:
        pass

@client.on(events.NewMessage(pattern="/help"))
async def cmd_help_txt(event):
    if not await check_policy(event): return
    await event.reply(
        "📖 Send any archive file or paste a URL to begin.\n"
        "Use the /start menu for all options.",
        parse_mode="markdown",
        buttons=[[Button.inline("🏠 Main Menu", data="mainmenu")]],
    )

@client.on(events.NewMessage(pattern=r"/setchannel\s+(@\S+|[-\d]+)"))
async def cmd_setchannel(event):
    if not await check_policy(event): return
    ch      = event.pattern_match.group(1)
    chat_id = event.chat_id
    w = await event.reply(f"🔍 Checking admin status in `{ch}`…", parse_mode="markdown")
    if not await bot_is_admin(ch):
        await w.edit(
            f"❌ *Bot not admin in `{ch}`*\n\n"
            f"Steps:\n1. Open channel → Administrators\n"
            f"2. Add this bot as admin (Post Messages perm)\n"
            f"3. Run `/setchannel {ch}` again",
            parse_mode="markdown",
            buttons=[[Button.inline("🏠 Menu", data="mainmenu")]],
        )
        return
    _dest_channels[chat_id] = ch
    await w.edit(
        f"✅ *Channel set: `{ch}`*\n\nAll files will be sent there.\n`/clearchannel` to disable.",
        parse_mode="markdown",
        buttons=[[Button.inline("🏠 Menu", data="mainmenu")]],
    )

@client.on(events.NewMessage(pattern="/clearchannel"))
async def cmd_clearchannel(event):
    _dest_channels.pop(event.chat_id, None)
    await event.reply(
        "✅ Channel cleared. Files will come here.",
        parse_mode="markdown",
        buttons=[[Button.inline("🏠 Menu", data="mainmenu")]],
    )

@client.on(events.NewMessage(pattern="/status"))
async def cmd_status(event):
    await event.reply(
        f"📊 *Bot Status*\n\n"
        f"⚡ Active jobs: `{len(_flag_map)}`\n"
        f"🔧 Max extract: `{MAX_EXTRACT_JOBS}` | Max links: `{MAX_LINK_JOBS}`\n"
        f"👥 Policy accepted: `{len(_policy_accepted)}`\n"
        f"🌐 Keep-alive port: `{KEEP_ALIVE_PORT}`",
        parse_mode="markdown",
        buttons=[[Button.inline("🏠 Menu", data="mainmenu")]],
    )

@client.on(events.NewMessage(pattern="/admin"))
async def cmd_admin(event):
    try:
        sender = await event.get_sender()
        if getattr(sender, "username", "") != ADMIN_USERNAME:
            await event.reply("❌ Admin only."); return
    except Exception:
        return
    await event.reply(
        f"🛠️ *Admin Panel*\n\n"
        f"Active jobs: `{len(_flag_map)}`\n"
        f"Channels set: `{len(_dest_channels)}`\n"
        f"Policy users: `{len(_policy_accepted)}`\n"
        f"Pending sends: `{len(_pending_output)}`\n"
        f"Work dir: `{WORK_DIR}`",
        parse_mode="markdown",
    )

# ── Forward callback buttons ─────────────────────────────────────────────
@client.on(events.CallbackQuery(pattern=rb"fwd:(here|ch):(\d+_\d+)"))
async def cb_fwd(event):
    data   = event.data.decode()
    parts  = data.split(":", 2)
    mode   = parts[1]
    key    = data

    stored = _fwd_store.pop(key, None)
    if not stored:
        await event.answer("⚠️ Expired.", alert=False); return

    chat_id = event.chat_id
    ch      = _dest_channels.get(chat_id)

    if mode == "ch" and not ch:
        await event.answer("No channel set! Use /setchannel first.", alert=True)
        _fwd_store[key] = stored  # put back
        return

    await event.answer()
    await handle_forward(stored["event"], dest_channel=(ch if mode == "ch" else None))

# ═══════════════════════════════════════════════════════════════════════
#  MAIN MESSAGE HANDLER
# ═══════════════════════════════════════════════════════════════════════
@client.on(events.NewMessage)
async def main_handler(event):
    msg     = event.message
    chat_id = event.chat_id

    # Ignore messages from bots (including self) — prevents policy loop
    sender = await event.get_sender()
    if sender is None or getattr(sender, "bot", False):
        return

    if msg.text and msg.text.startswith("/"):
        return  # handled by commands above

    if not await check_policy(event):
        return

    # ── Forwarded message ─────────────────────────────────────────────
    if msg.forward:
        ts  = int(time.time() * 1000)
        fh_key = f"fwd:here:{chat_id}_{ts}"
        fc_key = f"fwd:ch:{chat_id}_{ts}"
        _fwd_store[fh_key] = {"event": event}
        _fwd_store[fc_key] = {"event": event}

        ch      = _dest_channels.get(chat_id)
        buttons = [[Button.inline("📲 Repost here (clean)", data=fh_key)]]
        if ch:
            buttons.append([Button.inline(f"📢 Send to {ch} (clean)", data=fc_key)])
        buttons.append([Button.inline("🗑 Ignore / Delete", data="ignore_fwd")])

        prompt = await event.reply(
            "🔄 *Forwarded message detected!*\n\n"
            "I'll repost *without* the original source.\n"
            "Where should I send it?",
            parse_mode="markdown",
            buttons=buttons,
        )
        asyncio.create_task(auto_del(prompt, 90))
        return

    # ── Archive file ──────────────────────────────────────────────────
    if msg.document:
        fname = next(
            (a.file_name for a in (msg.document.attributes or []) if hasattr(a, "file_name")),
            f"file_{int(time.time())}"
        )

        if is_archive(fname):
            dl_msg = await event.reply(
                f"📥 *Downloading* `{fname}`…\n_{human(msg.document.size or 0)}_",
                parse_mode="markdown",
            )
            try:
                dl_path = WORK_DIR / f"{chat_id}_{int(time.time()*1000)}{Path(fname).suffix}"
                await event.download_media(file=str(dl_path))
            except Exception as e:
                await dl_msg.edit(f"❌ Download failed: `{e}`", parse_mode="markdown"); return
            await dl_msg.delete()
            asyncio.create_task(pipeline_archive(event, dl_path, fname))

        elif is_video(fname) or is_image(fname) or is_audio(fname):
            # Non-archive media doc — offer to forward cleanly
            await event.reply(
                f"📁 `{fname}` received.\n\n"
                f"This is not an archive. To extract, send `.zip` `.rar` `.7z` etc.\n"
                f"To download from a URL, paste a link.",
                parse_mode="markdown",
                buttons=[[Button.inline("🏠 Menu", data="mainmenu")]],
            )
        else:
            await event.reply(
                f"⚠️ `{fname}` is not a supported archive.\n\n"
                f"Supported: `.zip` `.7z` `.rar` `.tar` `.gz` `.bz2` `.xz`\n"
                f"Or paste a URL to download.",
                parse_mode="markdown",
                buttons=[[Button.inline("🏠 Menu", data="mainmenu")]],
            )
        return

    # ── URL in text ───────────────────────────────────────────────────
    if msg.text:
        urls = extract_urls(msg.text)
        if urls:
            asyncio.create_task(pipeline_link(event, urls[0]))
            return

        # Unknown text
        await event.reply(
            "🤔 *Send me:*\n\n"
            "📦 An *archive file* to extract\n"
            "🔗 A *URL/link* to download\n\n"
            "Use /start for the full menu.",
            parse_mode="markdown",
            buttons=[[Button.inline("🏠 Menu", data="mainmenu")]],
        )

@client.on(events.CallbackQuery(data=b"ignore_fwd"))
async def cb_ignore_fwd(event):
    await event.answer("Ignored.", alert=False)
    try: await event.delete()
    except Exception: pass

# ═══════════════════════════════════════════════════════════════════════
#  RUN
# ═══════════════════════════════════════════════════════════════════════
async def main():
    _start_keep_alive()
    me = await client.get_me()
    print(f"""
╔═══════════════════════════════════════════╗
║  🚀 ULTRA UNZIPPER BOT v2.0 — ONLINE     ║
╠═══════════════════════════════════════════╣
║  Bot    : @{me.username:<29}║
║  Admin  : @{ADMIN_USERNAME:<29}║
║  Channel: {CHANNEL_HANDLE:<30}║
║  Port   : {KEEP_ALIVE_PORT:<30}║
║  Extract: {MAX_EXTRACT_JOBS} parallel  | Links: {MAX_LINK_JOBS} parallel  ║
╚═══════════════════════════════════════════╝
🌐 UptimeRobot URL → your Replit URL (port {KEEP_ALIVE_PORT})
""")
    await client.run_until_disconnected()

if __name__ == "__main__":
    client.loop.run_until_complete(main())
