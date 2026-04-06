# ═══════════════════════════════════════════════════════
#  UNZIPPER BOT v7 — FINAL WORKING
#  No sudo needed. Pure Python extraction.
#  Run: python main.py
# ═══════════════════════════════════════════════════════

import subprocess, sys

# Auto-install all deps
for pkg in ["telethon","aiohttp","aiofiles","yt-dlp","requests","patool","pyunpack"]:
    try:
        __import__(pkg.replace("-","_"))
    except ImportError:
        print(f"Installing {pkg}...")
        subprocess.check_call([sys.executable,"-m","pip","install","--quiet",pkg])

# Also try to install unrar binary via pip
try:
    import unrar
except:
    subprocess.check_call([sys.executable,"-m","pip","install","--quiet","unrar"])

import os, asyncio, zipfile, tarfile, shutil, time, re, json, threading, logging
from pathlib import Path
from base64 import b64decode
from http.server import BaseHTTPRequestHandler, HTTPServer

import aiohttp, aiofiles, yt_dlp
from telethon import TelegramClient, events, Button
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.tl.types import ChannelParticipantAdmin, ChannelParticipantCreator

logging.basicConfig(level=logging.WARNING)

# ── Credentials ──────────────────────────────────────────
_AI = int(b64decode("Mjk2NDM0NzQ=").decode())
_AH = b64decode("NDkxNjMzZjAzNGMxYjUwYjFiYzBmMWU0ZDJiNDI2ZTM=").decode()
_BT = b64decode("ODcyMzk2NTI5MzpBQUdfd0hOZTkzNERNVHVTRlpZTFhNNDVXajN3dEdMTEdDUQ==").decode()

# ── Config ────────────────────────────────────────────────
BOT_TAG     = "@F88UF_FILEUNZIPBOT"
ADMIN       = "F88UF"
CH_LINK     = "https://t.me/F88UF9844"
WORK        = Path("/tmp/uzbot"); WORK.mkdir(exist_ok=True)
USERS_F     = Path("/tmp/uzbot_u.json")
PORT        = 8080
DEL_SEC     = 300

VIDEO = {".mp4",".mkv",".avi",".mov",".wmv",".flv",".webm",".m4v",".mpg",".mpeg",".3gp",".ts",".vob",".divx",".rmvb"}
IMAGE = {".jpg",".jpeg",".png",".gif",".bmp",".webp",".tiff"}
AUDIO = {".mp3",".flac",".aac",".ogg",".wav",".m4a",".opus",".wma"}
ZIPS  = {".zip",".7z",".rar",".tar",".gz",".tgz",".bz2",".xz"}

POLICY = (
    "📋 *Terms of Use*\n\n"
    "1️⃣ Utility tool only.\n"
    "2️⃣ You are 100% responsible for your files.\n"
    "3️⃣ No illegal / 18+ / pirated content.\n"
    "4️⃣ Admin has zero liability.\n\n"
    "Tap ✅ Accept to continue."
)

# ── State ─────────────────────────────────────────────────
client   = TelegramClient("uzbot_s", _AI, _AH).start(bot_token=_BT)
ACCEPTED : set  = set()
CHANNELS : dict = {}
JOBS     : dict = {}
PENDING  : dict = {}

def load_u():
    global ACCEPTED
    try: ACCEPTED = set(json.loads(USERS_F.read_text()))
    except: pass

def save_u():
    try: USERS_F.write_text(json.dumps(list(ACCEPTED)))
    except: pass

load_u()

# ── Keep-alive server ─────────────────────────────────────
class _H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"alive")
    def log_message(self, *a): pass

threading.Thread(
    target=lambda: HTTPServer(("0.0.0.0", PORT), _H).serve_forever(),
    daemon=True
).start()

# ── Helpers ───────────────────────────────────────────────
def hsize(n):
    for u in ("B","KB","MB","GB","TB"):
        if abs(n) < 1024: return f"{n:.1f}{u}"
        n /= 1024
    return f"{n:.1f}PB"

def pbar(d, t, w=16):
    p = min(d/t, 1.0) if t else 0
    f = int(w*p)
    return f"[{'█'*f}{'░'*(w-f)}] {p*100:.0f}%"

def ext(name): return Path(str(name)).suffix.lower()
def is_zip(n): return ext(n) in ZIPS or str(n).lower().endswith((".tar.gz",".tar.bz2"))
def is_vid(n): return ext(n) in VIDEO
def is_img(n): return ext(n) in IMAGE
def is_aud(n): return ext(n) in AUDIO

def jid(uid): return f"{uid}_{int(time.time()*1000)}"

async def del_later(msg, sec):
    await asyncio.sleep(sec)
    try: await msg.delete()
    except: pass

async def rm(*paths):
    for p in paths:
        try:
            if os.path.isfile(p): os.remove(p)
            elif os.path.isdir(p): shutil.rmtree(p)
        except: pass

# ── Buttons ───────────────────────────────────────────────
def sbtn(fk):
    return [[Button.inline("⏹ Stop", data=f"ST_{fk}")]]

def obtn(jd, ch=""):
    lbl = f"📢 Send to {ch}" if ch else "📢 Send to Channel"
    return [
        [Button.inline("📲 Send here",  data=f"OT_here_{jd}")],
        [Button.inline(lbl,             data=f"OT_ch_{jd}")],
        [Button.inline("❌ Cancel",     data=f"OT_no_{jd}")],
    ]

def mbtn():
    return [[Button.inline("🏠 Menu", data="MENU"), Button.inline("📢 Channel", url=CH_LINK)]]

# ── Policy ────────────────────────────────────────────────
async def check_pol(event) -> bool:
    """Returns True if user is allowed to proceed."""
    try:
        sender = await event.get_sender()
        # Block bots silently
        if not sender or getattr(sender, "bot", False):
            return False
    except:
        return False

    uid = event.sender_id
    if uid in ACCEPTED:
        return True

    await event.reply(
        POLICY, parse_mode="markdown",
        buttons=[[Button.inline("✅ Accept & Start", data=f"POL_{uid}")]]
    )
    return False

@client.on(events.CallbackQuery(pattern=rb"POL_"))
async def cb_pol(ev):
    # The person who clicked — accept them
    uid = ev.sender_id
    ACCEPTED.add(uid)
    save_u()
    await ev.answer("✅ Accepted!")
    try:
        await ev.edit(
            "✅ *Accepted!*\n\nNow send /start or send a file!",
            parse_mode="markdown",
            buttons=[[Button.inline("🏠 Start", data="MENU")]]
        )
    except: pass

# ── Channel check ─────────────────────────────────────────
async def is_admin_in(ch):
    try:
        me = await client.get_me()
        p  = await client(GetParticipantRequest(ch, me.id))
        return isinstance(p.participant, (ChannelParticipantAdmin, ChannelParticipantCreator))
    except: return False

# ── EXTRACTION — pure Python, no system tools needed ─────
async def do_extract(zpath: Path, outdir: Path, flag: dict, upd_cb) -> list:
    e = ext(zpath.name)
    name = zpath.name.lower()
    out = []

    async def upd(t):
        try: await upd_cb(t)
        except: pass

    # ── ZIP ──────────────────────────────────────────────
    if e == ".zip":
        try:
            with zipfile.ZipFile(zpath, "r") as zf:
                mbs   = zf.infolist()
                total = sum(m.file_size for m in mbs) or 1
                done  = t0 = 0
                for m in mbs:
                    if flag["stop"]: return []
                    zf.extract(m, outdir)
                    done += m.file_size
                    p = outdir / m.filename
                    if p.is_file(): out.append(p)
                    if time.time()-t0 > 1.5:
                        await upd(
                            f"⚡ *Extracting ZIP*\n"
                            f"{pbar(done,total)}\n"
                            f"{hsize(done)} / {hsize(total)}\n"
                            f"📄 `{Path(m.filename).name[:40]}`"
                        )
                        t0 = time.time()
        except zipfile.BadZipFile:
            await upd("❌ Bad ZIP file."); return []
        except Exception as ex:
            await upd(f"❌ ZIP error: {ex}"); return []

    # ── TAR/GZ/BZ2/XZ ────────────────────────────────────
    elif e in (".tar",".gz",".tgz",".bz2",".xz") or name.endswith((".tar.gz",".tar.bz2")):
        try:
            with tarfile.open(zpath, "r:*") as tf:
                mbs   = tf.getmembers()
                total = sum(m.size for m in mbs) or 1
                done  = t0 = 0
                for m in mbs:
                    if flag["stop"]: return []
                    tf.extract(m, outdir, set_attrs=False)
                    done += m.size
                    p = outdir / m.name
                    if p.is_file(): out.append(p)
                    if time.time()-t0 > 1.5:
                        await upd(
                            f"⚡ *Extracting TAR*\n"
                            f"{pbar(done,total)}\n"
                            f"{hsize(done)} / {hsize(total)}"
                        )
                        t0 = time.time()
        except Exception as ex:
            await upd(f"❌ TAR error: {ex}"); return []

    # ── RAR — pure python via unrar lib ──────────────────
    elif e == ".rar":
        try:
            import rarfile
            rarfile.UNRAR_TOOL = "unrar"
        except:
            subprocess.check_call([sys.executable,"-m","pip","install","--quiet","rarfile"])
            import rarfile

        try:
            with rarfile.RarFile(str(zpath)) as rf:
                mbs   = rf.infolist()
                total = sum(m.file_size for m in mbs) or 1
                done  = t0 = 0
                for m in mbs:
                    if flag["stop"]: return []
                    rf.extract(m, outdir)
                    done += m.file_size
                    p = outdir / m.filename
                    if p.is_file(): out.append(p)
                    if time.time()-t0 > 1.5:
                        await upd(
                            f"⚡ *Extracting RAR*\n"
                            f"{pbar(done,total)}\n"
                            f"{hsize(done)} / {hsize(total)}\n"
                            f"📄 `{Path(m.filename).name[:40]}`"
                        )
                        t0 = time.time()
        except Exception as ex:
            # Fallback: try 7z if available
            r = subprocess.run(["which","7z"], capture_output=True)
            if r.returncode == 0:
                proc = await asyncio.create_subprocess_exec(
                    "7z","x",str(zpath),f"-o{outdir}","-y",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE)
                await proc.wait()
                if proc.returncode == 0:
                    for root,_,fs in os.walk(outdir):
                        for f in fs: out.append(Path(root)/f)
                else:
                    await upd(f"❌ RAR extract failed: {ex}"); return []
            else:
                await upd(
                    f"❌ *RAR extraction failed*\n\n"
                    f"`{str(ex)[:100]}`\n\n"
                    f"_Try converting RAR to ZIP and send again._"
                ); return []

    # ── 7Z ────────────────────────────────────────────────
    elif e == ".7z":
        # Try py7zr (pure python)
        try:
            import py7zr
        except:
            subprocess.check_call([sys.executable,"-m","pip","install","--quiet","py7zr"])
            import py7zr

        try:
            await upd("⚡ *Extracting 7Z…*\n⏳ Please wait…")
            loop = asyncio.get_event_loop()
            def _do7z():
                with py7zr.SevenZipFile(str(zpath), mode='r') as z:
                    z.extractall(path=str(outdir))
            await loop.run_in_executor(None, _do7z)
            for root,_,fs in os.walk(outdir):
                for f in fs: out.append(Path(root)/f)
        except Exception as ex:
            await upd(f"❌ 7Z error: {ex}"); return []

    else:
        await upd(f"❌ Format not supported: `{e}`"); return []

    return out

# ── LINK DOWNLOAD ─────────────────────────────────────────
async def do_download(url: str, outdir: Path, flag: dict, upd_cb) -> list:
    out = []

    async def upd(t):
        try: await upd_cb(t)
        except: pass

    await upd(f"🔗 *Analyzing…*\n`{url[:60]}`")

    loop = asyncio.get_event_loop()
    tmpl = str(outdir / "%(title).60s.%(ext)s")

    def ydl_run():
        try:
            with yt_dlp.YoutubeDL({
                "outtmpl": tmpl, "quiet": True, "no_warnings": True,
                "merge_output_format": "mp4",
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "noplaylist": True, "socket_timeout": 30,
                "retries": 3, "geo_bypass": True,
                "http_headers": {"User-Agent":
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            }) as ydl:
                return ydl.extract_info(url, download=True)
        except Exception as ex:
            return ex

    res = await loop.run_in_executor(None, ydl_run)

    if isinstance(res, Exception):
        # Direct HTTP fallback
        await upd(f"⬇️ *Direct download…*\n`{url[:60]}`")
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(url, timeout=aiohttp.ClientTimeout(total=600)) as r:
                    if r.status != 200:
                        await upd(f"❌ HTTP {r.status}"); return []
                    total = int(r.headers.get("Content-Length", 0))
                    cd    = r.headers.get("Content-Disposition", "")
                    m     = re.search(r'filename=["\']?([^"\';\s]+)', cd)
                    fname = m.group(1) if m else (Path(url.split("?")[0]).name or "file")
                    if not Path(fname).suffix:
                        ct = r.content_type or ""
                        for ct2, ex2 in {"video/mp4":".mp4","image/jpeg":".jpg",
                                        "application/zip":".zip","application/pdf":".pdf"}.items():
                            if ct2 in ct: fname += ex2; break
                    dl = outdir / fname; done = t0 = 0
                    async with aiofiles.open(dl, "wb") as f:
                        async for chunk in r.content.iter_chunked(65536):
                            if flag["stop"]: return []
                            await f.write(chunk); done += len(chunk)
                            if time.time()-t0 > 1.5:
                                pb = pbar(done,total) if total else "⏳"
                                await upd(
                                    f"⬇️ *Downloading*\n`{fname[:40]}`\n"
                                    f"{pb}\n{hsize(done)}"+(f"/{hsize(total)}" if total else "")
                                )
                                t0 = time.time()
                    out.append(dl)
        except Exception as ex:
            await upd(f"❌ Download failed: `{ex}`"); return []
    else:
        for fp in outdir.iterdir():
            if fp.is_file(): out.append(fp)

    return out

# ── SEND FILES ────────────────────────────────────────────
async def send_all(target, files: list, flag: dict, fkey: str, smsg, src=""):
    total = len(files); sent = 0; failed = []
    SBTN  = sbtn(fkey)

    for i, fp in enumerate(files, 1):
        if flag["stop"]: break
        if not fp.exists(): continue

        sz   = fp.stat().st_size
        name = fp.name
        e2   = ext(name)
        cap  = f"📄 `{name}`\n📦 {hsize(sz)} • {i}/{total}\n🤖 {BOT_TAG}"

        try:
            await smsg.edit(
                f"📤 *Sending {i}/{total}*\n"
                f"{pbar(i-1, total)}\n"
                f"📄 `{name[:45]}`  {hsize(sz)}",
                parse_mode="markdown", buttons=SBTN
            )
        except: pass

        try:
            if e2 in VIDEO:
                await client.send_file(target, str(fp), caption=cap,
                    parse_mode="markdown", supports_streaming=True)
            elif e2 in IMAGE:
                await client.send_file(target, str(fp), caption=cap,
                    parse_mode="markdown")
            elif e2 in AUDIO:
                await client.send_file(target, str(fp), caption=cap,
                    parse_mode="markdown")
            else:
                await client.send_file(target, str(fp), caption=cap,
                    parse_mode="markdown", force_document=True)
            sent += 1
        except Exception as ex:
            failed.append(name)
            try:
                await smsg.edit(f"⚠️ Failed `{name}`\n`{str(ex)[:80]}`\nSkipping…",
                    parse_mode="markdown", buttons=SBTN)
                await asyncio.sleep(1)
            except: pass

        await asyncio.sleep(0.4)

    return sent, failed

# ── ARCHIVE PIPELINE ──────────────────────────────────────
async def pipe_zip(event, zpath: Path, fname: str):
    cid  = event.chat_id
    flag = {"stop": False}
    fkey = str(id(flag))
    JOBS[fkey] = flag

    jd     = jid(cid)
    outdir = WORK / jd; outdir.mkdir(exist_ok=True)

    smsg = await event.reply(
        f"⚡ *Starting extraction…*\n📄 `{fname}`",
        parse_mode="markdown", buttons=sbtn(fkey)
    )

    async def upd(t):
        try: await smsg.edit(t, parse_mode="markdown", buttons=sbtn(fkey))
        except: pass

    files = await do_extract(zpath, outdir, flag, upd)

    JOBS.pop(fkey, None)

    if flag["stop"] or not files:
        msg = "🚫 *Cancelled.*" if flag["stop"] else "❌ *Nothing extracted.*\nBad archive or unsupported format."
        try: await smsg.edit(msg, parse_mode="markdown", buttons=mbtn())
        except: pass
        await rm(str(zpath), str(outdir))
        asyncio.create_task(del_later(smsg, 60))
        return

    tsz  = sum(f.stat().st_size for f in files if f.exists())
    vids = sum(1 for f in files if is_vid(f.name))
    imgs = sum(1 for f in files if is_img(f.name))
    ch   = CHANNELS.get(cid, "")

    PENDING[jd] = dict(
        files=files, cid=cid, fkey=fkey,
        outdir=str(outdir), zpath=str(zpath),
        smsg=smsg, fname=fname, src=""
    )

    await smsg.edit(
        f"✅ *Extracted!*\n"
        f"📄 `{fname}`\n\n"
        f"📦 {len(files)} files • {hsize(tsz)}\n"
        f"🎬 Videos: {vids}  🖼 Images: {imgs}  "
        f"📄 Docs: {len(files)-vids-imgs}\n\n"
        f"*Where to send?*",
        parse_mode="markdown",
        buttons=obtn(jd, ch)
    )

# ── LINK PIPELINE ─────────────────────────────────────────
async def pipe_link(event, url: str):
    cid  = event.chat_id
    flag = {"stop": False}
    fkey = str(id(flag))
    JOBS[fkey] = flag

    jd     = jid(cid)
    outdir = WORK / jd; outdir.mkdir(exist_ok=True)

    smsg = await event.reply(
        f"🔗 *Link received*\n`{url[:60]}`\n⏳ Downloading…",
        parse_mode="markdown", buttons=sbtn(fkey)
    )

    async def upd(t):
        try: await smsg.edit(t, parse_mode="markdown", buttons=sbtn(fkey))
        except: pass

    files = await do_download(url, outdir, flag, upd)
    JOBS.pop(fkey, None)

    if flag["stop"] or not files:
        msg = "🚫 *Cancelled.*" if flag["stop"] else "❌ *Download failed.*\nCheck link is public."
        try: await smsg.edit(msg, parse_mode="markdown", buttons=mbtn())
        except: pass
        await rm(str(outdir))
        asyncio.create_task(del_later(smsg, 60))
        return

    # Auto-extract archives inside downloaded files
    all_files = []
    for f in files:
        if is_zip(f.name):
            xdir = outdir / f"x_{f.stem}"; xdir.mkdir(exist_ok=True)
            xflag = {"stop": False}
            async def xupd(t):
                try: await smsg.edit(t, parse_mode="markdown", buttons=sbtn(fkey))
                except: pass
            xf = await do_extract(f, xdir, xflag, xupd)
            if xf: all_files.extend(xf)
        else:
            all_files.append(f)

    tsz  = sum(f.stat().st_size for f in all_files if f.exists())
    vids = sum(1 for f in all_files if is_vid(f.name))
    imgs = sum(1 for f in all_files if is_img(f.name))
    ch   = CHANNELS.get(cid, "")

    PENDING[jd] = dict(
        files=all_files, cid=cid, fkey=fkey,
        outdir=str(outdir), zpath=None,
        smsg=smsg, fname="", src=url
    )

    await smsg.edit(
        f"✅ *Downloaded!*\n"
        f"🔗 `{url[:50]}`\n\n"
        f"📦 {len(all_files)} files • {hsize(tsz)}\n"
        f"🎬 Videos: {vids}  🖼 Images: {imgs}\n\n"
        f"*Where to send?*",
        parse_mode="markdown",
        buttons=obtn(jd, ch)
    )

# ── OUTPUT CHOICE ─────────────────────────────────────────
@client.on(events.CallbackQuery(pattern=rb"OT_"))
async def cb_out(ev):
    raw  = ev.data.decode()          # OT_here_JOBID or OT_ch_JOBID or OT_no_JOBID
    tmp  = raw[3:]                   # here_JOBID
    idx  = tmp.index("_")
    mode = tmp[:idx]                 # here / ch / no
    jd   = tmp[idx+1:]               # JOBID

    pend = PENDING.pop(jd, None)
    if not pend:
        await ev.answer("⚠️ Expired.", alert=False); return

    await ev.answer()

    files  = pend["files"]
    cid    = pend["cid"]
    fkey   = pend["fkey"]
    flag   = JOBS.get(fkey, {"stop": False})
    smsg   = pend["smsg"]
    src    = pend["src"]
    outdir = pend["outdir"]
    zpath  = pend.get("zpath")
    fname  = pend.get("fname", "")

    if mode == "no":
        flag["stop"] = True
        JOBS.pop(fkey, None)
        await rm(*(x for x in [zpath, outdir] if x))
        try: await smsg.edit("🚫 *Cancelled.*", parse_mode="markdown", buttons=mbtn())
        except: pass
        asyncio.create_task(del_later(smsg, 60))
        return

    if mode == "ch":
        ch = CHANNELS.get(cid, "")
        if not ch:
            PENDING[jd] = pend  # restore
            try:
                await smsg.edit(
                    "📢 *No channel set!*\n\n"
                    "1️⃣ Make this bot admin in your channel\n"
                    "2️⃣ Send: `/setchannel @yourchannel`\n"
                    "   or:  `/setchannel -1001234567890`\n\n"
                    "_Then tap Send to Channel again._",
                    parse_mode="markdown",
                    buttons=obtn(jd, "")
                )
            except: pass
            await ev.answer("Use /setchannel first!", alert=True)
            return
        target = ch
        tlabel = f"📢 {ch}"
        to_bot = False
    else:
        target = cid
        tlabel = "📲 this chat"
        to_bot = True

    tsz = sum(f.stat().st_size for f in files if f.exists())
    try:
        await smsg.edit(
            f"📤 *Sending to {tlabel}*\n"
            f"📦 {len(files)} files • {hsize(tsz)}\n_Starting…_",
            parse_mode="markdown", buttons=sbtn(fkey)
        )
    except: pass

    sent, failed = await send_all(target, files, flag, fkey, smsg, src)

    result = f"🎉 *Done!*\n✅ Sent `{sent}/{len(files)}` → {tlabel}\n"
    if fname:  result += f"📦 `{fname}`\n"
    if failed: result += f"⚠️ Failed: {len(failed)}\n"
    result += f"\n🤖 {BOT_TAG}"

    JOBS.pop(fkey, None)
    await rm(*(x for x in [zpath, outdir] if x))

    try: await smsg.edit(result, parse_mode="markdown", buttons=mbtn())
    except: pass

    if to_bot:
        asyncio.create_task(del_later(smsg, DEL_SEC))

# ── STOP ──────────────────────────────────────────────────
@client.on(events.CallbackQuery(pattern=rb"ST_"))
async def cb_stop(ev):
    fkey = ev.data.decode()[3:]
    flag = JOBS.get(fkey)
    if not flag:
        await ev.answer("Already done.", alert=False); return
    flag["stop"] = True
    await ev.answer("⏹ Stopped!", alert=False)
    try: await ev.edit("🚫 *Stopping…*", parse_mode="markdown")
    except: pass

# ── MENU ──────────────────────────────────────────────────
def menu_text(cid):
    ch = CHANNELS.get(cid, "Not set")
    return (
        f"👋 *File Unzip Bot*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 Send any archive → extract & send\n"
        f"🔗 Paste URL → download & send\n"
        f"📢 Output channel: `{ch}`\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Formats: ZIP RAR 7Z TAR GZ BZ2 XZ\n"
        f"Sites: YouTube TikTok Instagram +1000"
    )

def menu_kb(cid):
    return [
        [Button.inline("📦 Unzip Info",  data="I_zip"),
         Button.inline("🔗 URL Info",   data="I_url")],
        [Button.inline("📢 Set Channel", data="I_ch"),
         Button.inline("📊 Status",     data="I_st")],
        [Button.inline("📢 Join Channel", url=CH_LINK)],
    ]

@client.on(events.NewMessage(pattern="/start"))
async def cmd_start(ev):
    if not await check_pol(ev): return
    await ev.reply(menu_text(ev.chat_id), parse_mode="markdown", buttons=menu_kb(ev.chat_id))

@client.on(events.CallbackQuery(data=b"MENU"))
async def cb_menu(ev):
    await ev.answer()
    try: await ev.edit(menu_text(ev.chat_id), parse_mode="markdown", buttons=menu_kb(ev.chat_id))
    except: pass

@client.on(events.CallbackQuery(pattern=rb"I_"))
async def cb_info(ev):
    await ev.answer()
    k = ev.data.decode()[2:]
    msgs = {
        "zip": "📦 *Extract Archive*\n\nSend `.zip` `.rar` `.7z` `.tar` `.gz` `.bz2` `.xz`\n\nBot extracts all files and asks where to send!",
        "url": f"🔗 *Download Link*\n\nPaste any URL:\nYouTube, TikTok, Instagram, Twitter, Terabox, direct links\n\nBot downloads and asks where to send!",
        "ch":  "📢 *Set Output Channel*\n\n`/setchannel @yourchannel`\nor\n`/setchannel -1001234567890`\n\n⚠️ Make bot admin in channel first!\nGet ID from @userinfobot",
        "st":  f"📊 *Status*\n\nActive jobs: `{len(JOBS)}`\nAccepted users: `{len(ACCEPTED)}`",
    }
    await ev.reply(msgs.get(k, "?"), parse_mode="markdown",
        buttons=[[Button.inline("🏠 Back", data="MENU")]])

# ── SET CHANNEL ───────────────────────────────────────────
@client.on(events.NewMessage(pattern=r"/setchannel\s*(.*)"))
async def cmd_setch(ev):
    if not await check_pol(ev): return
    ch  = (ev.pattern_match.group(1) or "").strip()
    cid = ev.chat_id

    if not ch:
        await ev.reply(
            "📢 *How to set channel:*\n\n"
            "`/setchannel @yourchannel`\n"
            "or\n"
            "`/setchannel -1001234567890`\n\n"
            "Get channel ID → add @userinfobot to channel",
            parse_mode="markdown"
        ); return

    ch_r = int(ch) if ch.lstrip("-").isdigit() else ch
    w = await ev.reply(f"🔍 Checking `{ch}`…", parse_mode="markdown")

    if not await is_admin_in(ch_r):
        await w.edit(
            f"❌ *Bot not admin in `{ch}`*\n\n"
            f"1. Open channel → Administrators\n"
            f"2. Add this bot as admin\n"
            f"3. Give *Post Messages* permission ✅\n"
            f"4. Run `/setchannel {ch}` again",
            parse_mode="markdown"
        ); return

    CHANNELS[cid] = ch_r
    await w.edit(
        f"✅ *Channel set!* `{ch}`\n\nAll output will go there.\n`/clearchannel` to disable.",
        parse_mode="markdown", buttons=[[Button.inline("🏠 Menu", data="MENU")]]
    )

@client.on(events.NewMessage(pattern="/clearchannel"))
async def cmd_clrch(ev):
    CHANNELS.pop(ev.chat_id, None)
    await ev.reply("✅ Channel cleared. Files come here now.",
        buttons=[[Button.inline("🏠 Menu", data="MENU")]])

@client.on(events.NewMessage(pattern="/status"))
async def cmd_status(ev):
    await ev.reply(
        f"📊 Active jobs: `{len(JOBS)}`\nUsers: `{len(ACCEPTED)}`",
        parse_mode="markdown", buttons=[[Button.inline("🏠 Menu", data="MENU")]])

# ── FORWARD CLEANER ───────────────────────────────────────
FWD = {}

@client.on(events.CallbackQuery(pattern=rb"FW_"))
async def cb_fwd(ev):
    raw  = ev.data.decode()   # FW_here_KEY or FW_ch_KEY
    tmp  = raw[3:]
    idx  = tmp.index("_")
    mode = tmp[:idx]
    key  = tmp[idx+1:]

    stored = FWD.pop(key, None)
    if not stored: await ev.answer("Expired.", alert=False); return

    cid = ev.chat_id
    ch  = CHANNELS.get(cid, "")
    if mode == "ch" and not ch:
        await ev.answer("Set channel first! /setchannel", alert=True)
        FWD[key] = stored; return

    target = ch if mode == "ch" else cid
    orig   = stored["ev"]
    msg    = orig.message
    cap    = re.sub(r"@\w+", "", msg.message or "")
    cap    = re.sub(r"https?://t\.me/\S+", "", cap).strip()

    await ev.answer()
    try:
        if msg.media:
            await client.send_file(target, msg.media, caption=cap or None, parse_mode="markdown")
        elif cap:
            await client.send_message(target, cap)
        c = await orig.reply("✅ Reposted clean! Source removed.")
        try: await msg.delete()
        except: pass
        asyncio.create_task(del_later(c, 20))
    except Exception as ex:
        await orig.reply(f"❌ Failed: {ex}")

# ── IGNORE BUTTON ─────────────────────────────────────────
@client.on(events.CallbackQuery(data=b"IGN"))
async def cb_ign(ev):
    await ev.answer("Ignored.", alert=False)
    try: await ev.delete()
    except: pass

# ── MAIN HANDLER — only incoming user messages ────────────
@client.on(events.NewMessage(incoming=True))
async def on_msg(ev):
    msg = ev.message

    # CRITICAL: Ignore bot's own messages and other bots
    try:
        sender = await ev.get_sender()
        if not sender or getattr(sender, "bot", False):
            return
    except:
        return

    # Ignore commands (handled above)
    if msg.text and msg.text.startswith("/"):
        return

    # Policy check
    if not await check_pol(ev):
        return

    cid = ev.chat_id

    # Forwarded message
    if msg.forward:
        ts  = str(int(time.time()*1000))
        hk  = f"h_{ts}"
        ck  = f"c_{ts}"
        FWD[hk] = {"ev": ev}
        FWD[ck] = {"ev": ev}
        ch  = CHANNELS.get(cid, "")
        btns = [[Button.inline("📲 Repost here (clean)", data=f"FW_here_{hk}")]]
        if ch: btns.append([Button.inline(f"📢 Send to {ch}", data=f"FW_ch_{ck}")])
        btns.append([Button.inline("🗑 Ignore", data="IGN")])
        p = await ev.reply("🔄 *Forward detected!*\nRepost without source?",
            parse_mode="markdown", buttons=btns)
        asyncio.create_task(del_later(p, 90))
        return

    # Archive file
    if msg.document:
        fname = next(
            (a.file_name for a in (msg.document.attributes or []) if hasattr(a, "file_name")),
            f"file_{int(time.time())}"
        )
        if is_zip(fname):
            dm = await ev.reply(
                f"📥 *Downloading* `{fname}`\n_{hsize(msg.document.size or 0)}_",
                parse_mode="markdown"
            )
            try:
                dp = WORK / f"{cid}_{int(time.time()*1000)}{Path(fname).suffix}"
                await ev.download_media(file=str(dp))
            except Exception as ex:
                await dm.edit(f"❌ Download failed: `{ex}`", parse_mode="markdown")
                return
            await dm.delete()
            asyncio.create_task(pipe_zip(ev, dp, fname))
        else:
            await ev.reply(
                f"⚠️ `{fname}` is not a supported archive.\n\n"
                f"Supported: `.zip` `.rar` `.7z` `.tar` `.gz` `.bz2` `.xz`\n"
                f"Or paste a URL to download.",
                parse_mode="markdown",
                buttons=[[Button.inline("🏠 Menu", data="MENU")]]
            )
        return

    # URL in text
    if msg.text:
        urls = re.findall(r'https?://[^\s<>"\']+', msg.text)
        if urls:
            asyncio.create_task(pipe_link(ev, urls[0]))
            return
        await ev.reply(
            "🤔 Send an archive file or paste a URL.",
            buttons=[[Button.inline("🏠 Menu", data="MENU")]]
        )

# ── START ─────────────────────────────────────────────────
async def main():
    me = await client.get_me()
    print(f"""
╔══════════════════════════════════╗
║  ⚡ UNZIPPER BOT v7 — ONLINE    ║
╠══════════════════════════════════╣
║  Bot  : @{me.username:<23}║
║  Admin: @{ADMIN:<23}║
╚══════════════════════════════════╝
UptimeRobot → http://YOUR_REPLIT:{PORT}/
""")
    await client.run_until_disconnected()

if __name__ == "__main__":
    client.loop.run_until_complete(main())
