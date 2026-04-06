# ═══════════════════════════════════════════════════════
#  UNZIPPER BOT — CLEAN REWRITE v6
#  Admin: @F88UF
#  Auto-installs all deps. Run: python main.py
# ═══════════════════════════════════════════════════════

import subprocess, sys
for pkg in ["telethon","aiohttp","aiofiles","yt-dlp","requests"]:
    try: __import__(pkg.replace("-","_"))
    except ImportError:
        subprocess.check_call([sys.executable,"-m","pip","install","--quiet",pkg])

import os, asyncio, zipfile, tarfile, shutil, time, re, json, threading, logging
from pathlib import Path
from base64 import b64decode
from http.server import BaseHTTPRequestHandler, HTTPServer

import aiohttp, aiofiles, yt_dlp
from telethon import TelegramClient, events, Button
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.tl.types import ChannelParticipantAdmin, ChannelParticipantCreator

logging.basicConfig(level=logging.WARNING)

# ── Credentials ─────────────────────────────────────────
_AI = int(b64decode("Mjk2NDM0NzQ=").decode())
_AH = b64decode("NDkxNjMzZjAzNGMxYjUwYjFiYzBmMWU0ZDJiNDI2ZTM=").decode()
_BT = b64decode("ODcyMzk2NTI5MzpBQUdfd0hOZTkzNERNVHVTRlpZTFhNNDVXajN3dEdMTEdDUQ==").decode()

# ── Settings ─────────────────────────────────────────────
BOT_TAG       = "@F88UF_FILEUNZIPBOT"
ADMIN         = "F88UF"
CH_LINK       = "https://t.me/F88UF9844"
WORK          = Path("/tmp/uzbot"); WORK.mkdir(exist_ok=True)
ACCEPT_FILE   = Path("/tmp/uzbot_users.json")
PORT          = 8080
BOT_DEL_SEC   = 300   # 5 min — delete status msgs in bot chat only

VIDEO = {".mp4",".mkv",".avi",".mov",".wmv",".flv",".webm",".m4v",".mpg",".mpeg",".3gp",".ts",".vob",".divx"}
IMAGE = {".jpg",".jpeg",".png",".gif",".bmp",".webp",".tiff"}
AUDIO = {".mp3",".flac",".aac",".ogg",".wav",".m4a",".opus",".wma"}
ZIPS  = {".zip",".7z",".rar",".tar",".gz",".tgz",".bz2",".xz"}

POLICY = (
    "📋 *Terms of Use*\n\n"
    "1️⃣ This bot is a utility tool only.\n"
    "2️⃣ You are 100% responsible for your files.\n"
    "3️⃣ No illegal / 18+ / pirated content.\n"
    "4️⃣ Admin has zero liability for misuse.\n\n"
    "Tap ✅ Accept to continue."
)

# ── State ─────────────────────────────────────────────────
client   = TelegramClient("uzbot_s", _AI, _AH).start(bot_token=_BT)
ACCEPTED : set  = set()
CHANNELS : dict = {}   # chat_id → channel
JOBS     : dict = {}   # flag_key → {"stop": bool}
PENDING  : dict = {}   # job_id  → pending send info

def load_users():
    global ACCEPTED
    try: ACCEPTED = set(json.loads(ACCEPT_FILE.read_text()))
    except: pass

def save_users():
    try: ACCEPT_FILE.write_text(json.dumps(list(ACCEPTED)))
    except: pass

load_users()

# ── Keep-alive ────────────────────────────────────────────
class _H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"alive")
    def log_message(self,*a): pass

threading.Thread(
    target=lambda: HTTPServer(("0.0.0.0", PORT), _H).serve_forever(),
    daemon=True
).start()

# ── Helpers ───────────────────────────────────────────────
def hsize(n):
    for u in ("B","KB","MB","GB","TB"):
        if abs(n)<1024: return f"{n:.1f}{u}"
        n/=1024
    return f"{n:.1f}PB"

def bar(d,t,w=16):
    p = min(d/t,1.0) if t else 0
    f = int(w*p)
    return f"[{'█'*f}{'░'*(w-f)}] {p*100:.0f}%"

def fext(name): return Path(str(name)).suffix.lower()
def is_zip(n):  return fext(n) in ZIPS or str(n).lower().endswith((".tar.gz",".tar.bz2"))
def is_vid(n):  return fext(n) in VIDEO
def is_img(n):  return fext(n) in IMAGE
def is_aud(n):  return fext(n) in AUDIO

def new_jid(uid): return f"{uid}_{int(time.time()*1000)}"

async def timed_delete(msg, sec):
    await asyncio.sleep(sec)
    try: await msg.delete()
    except: pass

async def rm(*paths):
    for p in paths:
        try:
            if os.path.isfile(p): os.remove(p)
            elif os.path.isdir(p): shutil.rmtree(p)
        except: pass

# ── Button sets ───────────────────────────────────────────
def stop_btn(fk):
    return [[Button.inline("⏹ Stop", data=f"STOP_{fk}")]]

def output_btns(jid, ch=""):
    ch_label = f"📢 Send to {ch}" if ch else "📢 Send to Channel"
    return [
        [Button.inline("📲 Send here (bot)",  data=f"OUT_here_{jid}")],
        [Button.inline(ch_label,               data=f"OUT_ch_{jid}")],
        [Button.inline("❌ Cancel",            data=f"OUT_no_{jid}")],
    ]

def menu_btns():
    return [[Button.inline("🏠 Menu", data="MENU"), Button.inline("📢 Channel", url=CH_LINK)]]

# ── Policy gate ───────────────────────────────────────────
async def need_policy(event):
    uid = event.sender_id
    if uid in ACCEPTED: return False
    # Never show policy to bots
    try:
        s = await event.get_sender()
        if not s or getattr(s, "bot", False): return True  # silently block
    except: return True
    await event.reply(POLICY, parse_mode="markdown",
        buttons=[[Button.inline("✅ Accept", data=f"PA:{uid}")]])
    return True

@client.on(events.CallbackQuery(pattern=rb"PA:"))
async def cb_policy(ev):
    uid = ev.sender_id  # always the person who clicked
    ACCEPTED.add(uid); save_users()
    await ev.answer("✅ Accepted!")
    try:
        await ev.edit("✅ *Accepted!* Send /start to begin.",
            parse_mode="markdown",
            buttons=[[Button.inline("🏠 Start", data="MENU")]])
    except: pass

# ── Channel admin check ───────────────────────────────────
async def is_admin(ch):
    try:
        me = await client.get_me()
        p  = await client(GetParticipantRequest(ch, me.id))
        return isinstance(p.participant,(ChannelParticipantAdmin,ChannelParticipantCreator))
    except: return False

# ── Extraction ────────────────────────────────────────────
async def do_extract(zpath, outdir, flag, update_cb):
    ext  = fext(zpath)
    name = str(zpath).lower()
    out  = []

    async def upd(t):
        try: await update_cb(t)
        except: pass

    if ext == ".zip":
        try:
            with zipfile.ZipFile(zpath,"r") as zf:
                mbs   = zf.infolist()
                total = sum(m.file_size for m in mbs) or 1
                done  = t0 = 0
                for m in mbs:
                    if flag["stop"]: return None
                    zf.extract(m, outdir)
                    done += m.file_size
                    p = outdir/m.filename
                    if p.is_file(): out.append(p)
                    if time.time()-t0>1.5:
                        await upd(f"⚡ *Extracting ZIP*\n{bar(done,total)}\n{hsize(done)}/{hsize(total)}\n📄 `{Path(m.filename).name[:40]}`")
                        t0=time.time()
        except zipfile.BadZipFile:
            await upd("❌ Bad ZIP file"); return []

    elif ext in (".tar",".gz",".tgz",".bz2",".xz") or name.endswith((".tar.gz",".tar.bz2")):
        try:
            with tarfile.open(zpath,"r:*") as tf:
                mbs   = tf.getmembers()
                total = sum(m.size for m in mbs) or 1
                done  = t0 = 0
                for m in mbs:
                    if flag["stop"]: return None
                    tf.extract(m,outdir,set_attrs=False)
                    done+=m.size
                    p=outdir/m.name
                    if p.is_file(): out.append(p)
                    if time.time()-t0>1.5:
                        await upd(f"⚡ *Extracting TAR*\n{bar(done,total)}\n{hsize(done)}/{hsize(total)}")
                        t0=time.time()
        except Exception as e:
            await upd(f"❌ TAR error: {e}"); return []

    elif ext in (".7z",".rar"):
        await upd(f"⚡ *Extracting {ext.upper()}…*\n⏳ Please wait…")
        proc = await asyncio.create_subprocess_exec(
            "7z","x",str(zpath),f"-o{outdir}","-y",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE)
        t0=time.time()
        while proc.returncode is None:
            if flag["stop"]: proc.kill(); return None
            await asyncio.sleep(0.8)
            if time.time()-t0>2:
                await upd(f"⚡ *Extracting {ext.upper()}…*\n⏳ Running…")
                t0=time.time()
        await proc.wait()
        if proc.returncode!=0:
            err=(await proc.stderr.read()).decode(errors="ignore")[:200]
            await upd(f"❌ 7z error:\n`{err}`"); return []
        for r,_,fs in os.walk(outdir):
            for f in fs: out.append(Path(r)/f)
    else:
        await upd(f"❌ Unsupported: `{ext}`"); return []

    return out

# ── Link downloader ───────────────────────────────────────
async def do_download(url, outdir, flag, update_cb):
    out=[]
    async def upd(t):
        try: await update_cb(t)
        except: pass

    await upd(f"🔗 *Analyzing link…*\n`{url[:60]}`")

    loop=asyncio.get_event_loop()
    tmpl=str(outdir/"%(title).60s.%(ext)s")

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
        except Exception as e:
            return e

    res = await loop.run_in_executor(None, ydl_run)

    if isinstance(res, Exception):
        # Fallback: direct HTTP download
        await upd(f"⬇️ *Direct download…*\n`{url[:60]}`")
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(url, timeout=aiohttp.ClientTimeout(total=600)) as r:
                    if r.status != 200:
                        await upd(f"❌ HTTP {r.status}"); return []
                    total = int(r.headers.get("Content-Length",0))
                    cd    = r.headers.get("Content-Disposition","")
                    m     = re.search(r'filename=["\']?([^"\';\s]+)',cd)
                    fname = m.group(1) if m else (Path(url.split("?")[0]).name or "file")
                    if not Path(fname).suffix:
                        ct=r.content_type or ""
                        for ct2,ex in {
                            "video/mp4":".mp4","video/webm":".webm",
                            "image/jpeg":".jpg","image/png":".png",
                            "application/zip":".zip","application/pdf":".pdf"
                        }.items():
                            if ct2 in ct: fname+=ex; break
                    dl=outdir/fname; done=t0=0
                    async with aiofiles.open(dl,"wb") as f:
                        async for chunk in r.content.iter_chunked(65536):
                            if flag["stop"]: return None
                            await f.write(chunk); done+=len(chunk)
                            if time.time()-t0>1.5:
                                pb=bar(done,total) if total else "⏳"
                                await upd(f"⬇️ *Downloading*\n`{fname[:40]}`\n{pb}\n{hsize(done)}"+(f"/{hsize(total)}" if total else ""))
                                t0=time.time()
                    out.append(dl)
        except Exception as e:
            await upd(f"❌ Download failed: `{e}`"); return []
    else:
        for fp in outdir.iterdir():
            if fp.is_file(): out.append(fp)

    return out

# ── Send files one by one ─────────────────────────────────
async def send_all(target, files, flag, fkey, status_msg, src="", to_bot=True):
    total=len(files); sent=0; failed=[]
    SBTN=stop_btn(fkey)

    for i,fp in enumerate(files,1):
        if flag["stop"]: break
        if not fp.exists(): continue

        sz=fp.stat().st_size
        name=fp.name
        ext=fext(name)
        cap=f"📄 `{name}`\n📦 {hsize(sz)} • {i}/{total}\n\n🤖 {BOT_TAG}"

        # Update progress
        try:
            await status_msg.edit(
                f"📤 *Sending {i}/{total}*\n"
                f"{bar(i-1,total)}\n"
                f"📄 `{name[:45]}`\n{hsize(sz)}",
                parse_mode="markdown",
                buttons=SBTN)
        except: pass

        try:
            if ext in VIDEO:
                await client.send_file(target,str(fp),caption=cap,
                    parse_mode="markdown",supports_streaming=True)
            elif ext in IMAGE:
                await client.send_file(target,str(fp),caption=cap,
                    parse_mode="markdown")
            elif ext in AUDIO:
                await client.send_file(target,str(fp),caption=cap,
                    parse_mode="markdown")
            else:
                await client.send_file(target,str(fp),caption=cap,
                    parse_mode="markdown",force_document=True)
            sent+=1
        except Exception as e:
            failed.append(name)
            try:
                await status_msg.edit(
                    f"⚠️ Failed: `{name}`\n`{str(e)[:80]}`\nSkipping…",
                    parse_mode="markdown",buttons=SBTN)
                await asyncio.sleep(1)
            except: pass

        await asyncio.sleep(0.4)  # flood protection

    return sent, failed

# ── Archive pipeline ─────────────────────────────────────
async def pipe_zip(event, zpath, fname):
    cid  = event.chat_id
    flag = {"stop":False}
    fkey = str(id(flag))
    JOBS[fkey]=flag

    jid    = new_jid(cid)
    outdir = WORK/jid; outdir.mkdir(exist_ok=True)

    smsg = await event.reply(
        f"⚡ *Extracting* `{fname}`…",
        parse_mode="markdown",
        buttons=stop_btn(fkey))

    async def upd(t):
        try: await smsg.edit(t,parse_mode="markdown",buttons=stop_btn(fkey))
        except: pass

    files = await do_extract(zpath, outdir, flag, upd)

    if files is None:
        JOBS.pop(fkey,None)
        try: await smsg.edit("🚫 *Cancelled.*",parse_mode="markdown",buttons=menu_btns())
        except: pass
        await rm(str(zpath),str(outdir))
        asyncio.create_task(timed_delete(smsg,30))
        return

    if not files:
        JOBS.pop(fkey,None)
        try: await smsg.edit("❌ *Nothing extracted.*",parse_mode="markdown",buttons=menu_btns())
        except: pass
        await rm(str(zpath),str(outdir))
        asyncio.create_task(timed_delete(smsg,60))
        return

    tsz   = sum(f.stat().st_size for f in files if f.exists())
    vids  = sum(1 for f in files if is_vid(f.name))
    imgs  = sum(1 for f in files if is_img(f.name))
    docs  = len(files)-vids-imgs
    ch    = CHANNELS.get(cid,"")

    PENDING[jid] = dict(files=files,cid=cid,fkey=fkey,
                        outdir=str(outdir),zpath=str(zpath),
                        smsg=smsg,fname=fname,src="")

    await smsg.edit(
        f"✅ *Extracted!* `{fname}`\n\n"
        f"📦 {len(files)} files • {hsize(tsz)}\n"
        f"🎬 Videos: {vids}  🖼 Images: {imgs}  📄 Docs: {docs}\n\n"
        f"*Where to send?*",
        parse_mode="markdown",
        buttons=output_btns(jid, ch))

# ── Link pipeline ────────────────────────────────────────
async def pipe_link(event, url):
    cid  = event.chat_id
    flag = {"stop":False}
    fkey = str(id(flag))
    JOBS[fkey]=flag

    jid    = new_jid(cid)
    outdir = WORK/jid; outdir.mkdir(exist_ok=True)

    smsg = await event.reply(
        f"🔗 *Link received*\n`{url[:60]}`\n\n⏳ Downloading…",
        parse_mode="markdown",
        buttons=stop_btn(fkey))

    async def upd(t):
        try: await smsg.edit(t,parse_mode="markdown",buttons=stop_btn(fkey))
        except: pass

    files = await do_download(url, outdir, flag, upd)

    if files is None:
        JOBS.pop(fkey,None)
        try: await smsg.edit("🚫 *Cancelled.*",parse_mode="markdown",buttons=menu_btns())
        except: pass
        await rm(str(outdir))
        asyncio.create_task(timed_delete(smsg,30))
        return

    if not files:
        JOBS.pop(fkey,None)
        try: await smsg.edit("❌ *Could not download.*\nCheck the link is public.",
            parse_mode="markdown",buttons=menu_btns())
        except: pass
        await rm(str(outdir))
        asyncio.create_task(timed_delete(smsg,60))
        return

    # Auto-extract any archives in download
    all_files=[]
    for f in files:
        if is_zip(f.name):
            xdir=outdir/f"x_{f.stem}"; xdir.mkdir(exist_ok=True)
            xf={"stop":False}
            async def xupd(t):
                try: await smsg.edit(t,parse_mode="markdown",buttons=stop_btn(fkey))
                except: pass
            extracted=await do_extract(f,xdir,xf,xupd)
            if extracted: all_files.extend(extracted)
        else:
            all_files.append(f)

    tsz  = sum(f.stat().st_size for f in all_files if f.exists())
    vids = sum(1 for f in all_files if is_vid(f.name))
    imgs = sum(1 for f in all_files if is_img(f.name))
    ch   = CHANNELS.get(cid,"")

    PENDING[jid]=dict(files=all_files,cid=cid,fkey=fkey,
                      outdir=str(outdir),zpath=None,
                      smsg=smsg,fname="",src=url)

    await smsg.edit(
        f"✅ *Downloaded!*\n\n"
        f"🔗 `{url[:50]}`\n\n"
        f"📦 {len(all_files)} files • {hsize(tsz)}\n"
        f"🎬 Videos: {vids}  🖼 Images: {imgs}\n\n"
        f"*Where to send?*",
        parse_mode="markdown",
        buttons=output_btns(jid, ch))

# ── Output choice callback ────────────────────────────────
@client.on(events.CallbackQuery(pattern=rb"OUT_"))
async def cb_output(ev):
    raw  = ev.data.decode()  # e.g. "OUT_here_1234_5678"
    # split on first two underscores only
    tmp  = raw[4:]  # remove "OUT_"
    idx  = tmp.index("_")
    mode = tmp[:idx]        # here / ch / no
    jid  = tmp[idx+1:]      # rest is job id

    pend = PENDING.pop(jid, None)
    if not pend:
        await ev.answer("⚠️ Expired.", alert=False); return

    await ev.answer()
    files  = pend["files"]
    cid    = pend["cid"]
    fkey   = pend["fkey"]
    flag   = JOBS.get(fkey, {"stop":False})
    smsg   = pend["smsg"]
    src    = pend["src"]
    outdir = pend["outdir"]
    zpath  = pend.get("zpath")
    fname  = pend.get("fname","")

    # Cancel
    if mode == "no":
        flag["stop"]=True; JOBS.pop(fkey,None)
        await rm(*(x for x in [zpath,outdir] if x))
        try: await smsg.edit("🚫 *Cancelled. Files not sent.*",
            parse_mode="markdown",buttons=menu_btns())
        except: pass
        asyncio.create_task(timed_delete(smsg,60))
        return

    # Channel — check if set
    if mode == "ch":
        ch = CHANNELS.get(cid,"")
        if not ch:
            PENDING[jid]=pend  # put back
            try:
                await smsg.edit(
                    "📢 *No channel set!*\n\n"
                    "Steps:\n"
                    "1️⃣ Make this bot admin in your channel\n"
                    "2️⃣ Send: `/setchannel @yourchannel`\n"
                    "   or:  `/setchannel -1001234567890`\n\n"
                    "_Then tap Send to Channel again._",
                    parse_mode="markdown",
                    buttons=output_btns(jid,""))
            except: pass
            await ev.answer("Use /setchannel first!", alert=True)
            return
        target       = ch
        target_label = f"📢 {ch}"
        to_bot       = False
    else:
        target       = cid
        target_label = "📲 this chat"
        to_bot       = True

    tsz=sum(f.stat().st_size for f in files if f.exists())
    try:
        await smsg.edit(
            f"📤 *Sending to {target_label}*\n"
            f"📦 {len(files)} files • {hsize(tsz)}\n\n"
            f"_Starting…_",
            parse_mode="markdown",
            buttons=stop_btn(fkey))
    except: pass

    sent, failed = await send_all(target, files, flag, fkey, smsg, src, to_bot)

    result = (
        f"🎉 *Done!*\n"
        f"✅ Sent `{sent}/{len(files)}` → {target_label}\n"
    )
    if fname:  result += f"📦 `{fname}`\n"
    if failed: result += f"⚠️ Failed: {len(failed)}\n"
    result += f"\n🤖 {BOT_TAG}"

    JOBS.pop(fkey,None)
    await rm(*(x for x in [zpath,outdir] if x))

    try: await smsg.edit(result,parse_mode="markdown",buttons=menu_btns())
    except: pass

    if to_bot:
        asyncio.create_task(timed_delete(smsg, BOT_DEL_SEC))

# ── Stop button ───────────────────────────────────────────
@client.on(events.CallbackQuery(pattern=rb"STOP_"))
async def cb_stop(ev):
    fkey = ev.data.decode()[5:]  # remove "STOP_" 
    flag = JOBS.get(fkey)
    if not flag:
        await ev.answer("Already finished.",alert=False); return
    flag["stop"]=True
    await ev.answer("⏹ Stopped!",alert=False)
    try: await ev.edit("🚫 *Stopping…*",parse_mode="markdown")
    except: pass

# ── Main menu ─────────────────────────────────────────────
def _menu_text(cid):
    ch=CHANNELS.get(cid,"Not set")
    return (
        f"👋 *Unzipper Bot*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 Send any archive to extract\n"
        f"🔗 Paste any URL to download\n"
        f"📢 Output channel: `{ch}`\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"*Formats:* ZIP 7Z RAR TAR GZ BZ2 XZ\n"
        f"*Sites:* YouTube TikTok Instagram +1000"
    )

def _menu_btns():
    return [
        [Button.inline("📦 How to Extract",  data="INFO:zip"),
         Button.inline("🔗 How to Download", data="INFO:link")],
        [Button.inline("📢 Set Channel",      data="INFO:ch"),
         Button.inline("📊 Status",           data="INFO:status")],
        [Button.inline("📢 Join Channel",     url=CH_LINK)],
    ]

@client.on(events.NewMessage(pattern="/start"))
async def cmd_start(ev):
    if await need_policy(ev): return
    await ev.reply(_menu_text(ev.chat_id),parse_mode="markdown",buttons=_menu_btns())

@client.on(events.CallbackQuery(data=b"MENU"))
async def cb_menu(ev):
    await ev.answer()
    try: await ev.edit(_menu_text(ev.chat_id),parse_mode="markdown",buttons=_menu_btns())
    except: pass

@client.on(events.CallbackQuery(pattern=rb"INFO:"))
async def cb_info(ev):
    await ev.answer()
    key=ev.data.decode().split(":",1)[1]
    msgs={
        "zip":  "📦 Send any `.zip` `.7z` `.rar` `.tar` `.gz` `.bz2` `.xz` file\nBot extracts and asks where to send!",
        "link": "🔗 Paste any URL:\nYouTube, TikTok, Instagram, Twitter, Terabox, direct links etc.\nBot downloads and asks where to send!",
        "ch":   "📢 *Set output channel:*\n`/setchannel @yourchannel`\nor\n`/setchannel -1001234567890`\n\nMake bot admin in channel first!",
        "status": f"⚡ Active jobs: `{len(JOBS)}`\n👥 Users: `{len(ACCEPTED)}`",
    }
    await ev.reply(msgs.get(key,"?"),parse_mode="markdown",
        buttons=[[Button.inline("🏠 Back",data="MENU")]])

@client.on(events.NewMessage(pattern=r"/setchannel\s*(.*)"))
async def cmd_setch(ev):
    if await need_policy(ev): return
    ch=(ev.pattern_match.group(1) or "").strip()
    cid=ev.chat_id
    if not ch:
        await ev.reply(
            "📢 *Set your channel:*\n\n"
            "`/setchannel @yourchannel`\n"
            "`/setchannel -1001234567890`\n\n"
            "Get channel ID from @userinfobot",
            parse_mode="markdown")
        return
    ch_r=int(ch) if ch.lstrip("-").isdigit() else ch
    w=await ev.reply(f"🔍 Checking `{ch}`…",parse_mode="markdown")
    if not await is_admin(ch_r):
        await w.edit(
            f"❌ *Bot is not admin in `{ch}`*\n\n"
            f"1. Open channel → Administrators\n"
            f"2. Add this bot as admin\n"
            f"3. Give Post Messages permission\n"
            f"4. Run `/setchannel {ch}` again",
            parse_mode="markdown")
        return
    CHANNELS[cid]=ch_r
    await w.edit(f"✅ *Channel set!*\n`{ch}`\n\nOutput will go there.",
        parse_mode="markdown",buttons=[[Button.inline("🏠 Menu",data="MENU")]])

@client.on(events.NewMessage(pattern="/clearchannel"))
async def cmd_clrch(ev):
    CHANNELS.pop(ev.chat_id,None)
    await ev.reply("✅ Channel cleared. Files will come here.",
        buttons=[[Button.inline("🏠 Menu",data="MENU")]])

@client.on(events.NewMessage(pattern="/status"))
async def cmd_status(ev):
    await ev.reply(
        f"📊 *Status*\n\nActive jobs: `{len(JOBS)}`\nUsers: `{len(ACCEPTED)}`\nPort: `{PORT}`",
        parse_mode="markdown",buttons=[[Button.inline("🏠 Menu",data="MENU")]])

# ── Forward cleaner ───────────────────────────────────────
FWD_STORE={}

@client.on(events.CallbackQuery(pattern=rb"FWD:"))
async def cb_fwd(ev):
    parts=ev.data.decode().split(":",2)
    mode=parts[1]; key=":".join(parts[:3])
    stored=FWD_STORE.pop(key,None)
    if not stored: await ev.answer("Expired.",alert=False); return
    cid=ev.chat_id
    ch=CHANNELS.get(cid,"")
    if mode=="ch" and not ch:
        await ev.answer("Set channel first with /setchannel",alert=True)
        FWD_STORE[key]=stored; return
    target=ch if mode=="ch" else cid
    orig=stored["ev"]
    msg=orig.message
    cap=re.sub(r"@\w+","",msg.message or "")
    cap=re.sub(r"https?://t\.me/\S+","",cap).strip()
    await ev.answer()
    try:
        if msg.media:
            await client.send_file(target,msg.media,caption=cap or None,parse_mode="markdown")
        elif msg.message:
            await client.send_message(target,cap)
        c=await orig.reply("✅ Reposted clean!")
        try: await msg.delete()
        except: pass
        asyncio.create_task(timed_delete(c,20))
    except Exception as e:
        await orig.reply(f"❌ Failed: {e}")

# ── Main handler ──────────────────────────────────────────
@client.on(events.NewMessage(incoming=True, func=lambda e: not e.via_bot_id))
async def on_msg(ev):
    msg=ev.message
    # Skip if sender is a bot
    try:
        sender=await ev.get_sender()
        if not sender or getattr(sender,"bot",False): return
    except: return
    # Ignore commands
    if msg.text and msg.text.startswith("/"): return
    # Policy check
    if await need_policy(ev): return

    cid=ev.chat_id

    # Forwarded message
    if msg.forward:
        ts=int(time.time()*1000)
        hk=f"FWD:here:{cid}_{ts}"
        ck=f"FWD:ch:{cid}_{ts}"
        FWD_STORE[hk]={"ev":ev}
        FWD_STORE[ck]={"ev":ev}
        ch=CHANNELS.get(cid,"")
        btns=[[Button.inline("📲 Repost here (clean)",data=hk)]]
        if ch: btns.append([Button.inline(f"📢 Send to {ch} (clean)",data=ck)])
        btns.append([Button.inline("🗑 Ignore",data="IGNORE")])
        p=await ev.reply("🔄 *Forwarded!* Repost without source?",
            parse_mode="markdown",buttons=btns)
        asyncio.create_task(timed_delete(p,90))
        return

    # Archive file
    if msg.document:
        fname=next((a.file_name for a in (msg.document.attributes or [])
                    if hasattr(a,"file_name")),f"file_{int(time.time())}")
        if is_zip(fname):
            dm=await ev.reply(f"📥 *Downloading* `{fname}`…\n_{hsize(msg.document.size or 0)}_",
                parse_mode="markdown")
            try:
                dp=WORK/f"{cid}_{int(time.time()*1000)}{Path(fname).suffix}"
                await ev.download_media(file=str(dp))
            except Exception as e:
                await dm.edit(f"❌ Download failed: `{e}`",parse_mode="markdown"); return
            await dm.delete()
            asyncio.create_task(pipe_zip(ev,dp,fname))
        else:
            await ev.reply(
                f"⚠️ `{fname}` is not an archive.\n\n"
                f"Send: `.zip` `.7z` `.rar` `.tar` `.gz`\nOr paste a URL.",
                parse_mode="markdown",
                buttons=[[Button.inline("🏠 Menu",data="MENU")]])
        return

    # URL
    if msg.text:
        urls=re.findall(r'https?://[^\s<>"\']+',msg.text)
        if urls:
            asyncio.create_task(pipe_link(ev,urls[0])); return
        await ev.reply(
            "🤔 Send an archive file or paste a URL.",
            buttons=[[Button.inline("🏠 Menu",data="MENU")]])

@client.on(events.CallbackQuery(data=b"IGNORE"))
async def cb_ignore(ev):
    await ev.answer("Ignored.",alert=False)
    try: await ev.delete()
    except: pass

# ── Run ───────────────────────────────────────────────────
async def main():
    me=await client.get_me()
    print(f"""
╔══════════════════════════════════╗
║  ⚡ UNZIPPER BOT v6 — ONLINE    ║
╠══════════════════════════════════╣
║  Bot   : @{me.username:<22}║
║  Admin : @{ADMIN:<22}║
║  Port  : {PORT:<23}║
╚══════════════════════════════════╝
UptimeRobot URL: http://YOUR_REPLIT_URL:{PORT}/
""")
    await client.run_until_disconnected()

if __name__=="__main__":
    client.loop.run_until_complete(main())
