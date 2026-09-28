import math, time, re, os
from datetime import datetime
from pytz import timezone
from config import Config, Txt 
from pyrogram.errors import FloodWait, MessageNotModified
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import shutil

_PROGRESS_LAST_EDIT = {}
_PROGRESS_STATE = {}
_SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
_CANCEL_MARKUP = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("🔄 ʀᴇꜰʀᴇsʜ", callback_data="refresh_progress"),
            InlineKeyboardButton("✖️ ᴄʟᴏsᴇ", callback_data="close"),
        ]
    ]
)


def _get_msg_key(message):
    return (
        getattr(getattr(message, "chat", None), "id", 0),
        getattr(message, "id", id(message)),
    )


def _compute_stable_speed(state: dict, current_clamped: int, now: float, start: float) -> float:
    """
    Compute a rock-solid, non-fluctuating transfer speed using a 4-second rolling
    sample window combined with a damped EMA and transfer average, anchoring the
    clock on the first actual transferred chunk so pre-transfer setup (such as
    video_cover/thumbnail upload or foreign-DC auth export) never drags speed down.
    """
    if current_clamped <= 0:
        return 0.0

    # Anchor transfer clock when the first chunk of the main file arrives if pre-transfer
    # setup (e.g. thumb/video_cover upload or DC auth handshake) took > 0.4s
    effective_start = state.get("first_byte_ts")
    if effective_start is None:
        if (now - start) > 0.4 and current_clamped <= 2 * 1024 * 1024:
            effective_start = now - 0.15
        else:
            effective_start = start
        state["first_byte_ts"] = effective_start
        state["samples"] = [(effective_start, 0)]
        state["last_speed_sample_ts"] = effective_start

    last_sample_ts = state.get("last_speed_sample_ts", effective_start)
    prev_ema = state.get("ema_speed", 0.0)
    if prev_ema > 0.0 and (now - last_sample_ts) < 0.25:
        return prev_ema

    state["last_speed_sample_ts"] = now
    samples = state.setdefault("samples", [(effective_start, 0)])
    samples.append((now, current_clamped))
    cutoff = now - 4.0
    while len(samples) > 2 and samples[1][0] <= cutoff:
        samples.pop(0)

    oldest_ts, oldest_bytes = samples[0]
    window_dt = max(now - oldest_ts, 0.001)
    window_bytes = max(0, current_clamped - oldest_bytes)
    window_speed = window_bytes / window_dt if window_bytes > 0 else 0.0

    avg_speed = current_clamped / max(now - effective_start, 0.001)
    base_speed = (0.75 * window_speed + 0.25 * avg_speed) if window_speed > 0 else avg_speed

    if prev_ema <= 0.0:
        ema_speed = base_speed
    else:
        ema_speed = (0.35 * base_speed) + (0.65 * prev_ema)
        # Clamp per-sample swing to ±22% of previous EMA so transient jitter never spikes UI
        low_bound = prev_ema * 0.78
        high_bound = prev_ema * 1.22
        ema_speed = max(low_bound, min(high_bound, ema_speed))

    state["ema_speed"] = ema_speed
    return max(ema_speed, avg_speed * 0.75, 1.0)



def build_progress_text(
    current: int,
    total: int,
    ud_type: str,
    start: float,
    frame_idx: int = 0,
    speed_override: float = 0.0,
) -> str:
    now = time.time()
    diff = max(now - start, 0.001)
    total_safe = max(int(total or 0), 1)
    current_clamped = max(0, min(int(current or 0), total_safe))
    percentage = current_clamped * 100.0 / total_safe

    avg_speed = current_clamped / diff if current_clamped > 0 else 0.0
    speed = speed_override if speed_override > 0 else avg_speed

    if current_clamped >= total_safe:
        eta_str = "0s"
    elif speed > 1.0:
        time_to_completion = round((total_safe - current_clamped) / speed) * 1000
        eta_str = TimeFormatter(milliseconds=time_to_completion) or "1s"
    else:
        eta_str = "ᴄᴀʟᴄᴜʟᴀᴛɪɴɢ..."

    filled = min(14, max(0, math.floor(percentage / (100.0 / 14.0))))
    bar = ("▰" * filled) + ("▱" * (14 - filled))
    spinner = "✔" if current_clamped >= total_safe else _SPINNER_FRAMES[frame_idx % len(_SPINNER_FRAMES)]
    progress = f"<blockquote><code>{spinner} [{bar}] {round(percentage, 1)}%</code></blockquote>"
    tmp = progress + Txt.PROGRESS_BAR.format(
        round(percentage, 2),
        humanbytes(current_clamped),
        humanbytes(total_safe),
        humanbytes(speed),
        eta_str,
    )
    return f"{ud_type}\n\n{tmp}"


async def init_progress_message(message, ud_type: str, total: int, edit_target=None):
    """
    Render the initial 0.0% progress bar card immediately at transfer start and
    seed `_PROGRESS_STATE` so chunk #1 doesn't trigger a back-to-back duplicate edit.
    """
    now = time.time()
    total_safe = max(int(total or 0), 1)
    text = build_progress_text(0, total_safe, ud_type, now, frame_idx=0, speed_override=0.0)
    target = edit_target or message
    edited_msg = target
    try:
        res = await target.edit(text=text, reply_markup=_CANCEL_MARKUP)
        if res is not None:
            edited_msg = res
    except FloodWait as e:
        wait_s = float(getattr(e, "value", getattr(e, "x", 3)) or 3)
        msg_key = _get_msg_key(edited_msg)
        ts = time.time()
        _PROGRESS_STATE[msg_key] = {
            "last_edit": ts,
            "synced_legacy_last": ts,
            "last_pct": 0.0,
            "last_bytes": 0,
            "latest_bytes": 0,
            "latest_total": total_safe,
            "ud_type": ud_type,
            "start": now,
            "samples": [(now, 0)],
            "last_sample_time": ts,
            "ema_speed": 0.0,
            "frame_idx": 1,
            "min_interval": 2.2,
            "cooldown_until": ts + wait_s + 0.5,
            "in_flight": False,
            "last_text": text,
        }
        _PROGRESS_LAST_EDIT[msg_key] = ts
        return edited_msg, now
    except Exception:
        pass

    edit_done = time.time()
    msg_key = _get_msg_key(edited_msg)
    _PROGRESS_STATE[msg_key] = {
        "last_edit": edit_done,
        "synced_legacy_last": edit_done,
        "last_pct": 0.0,
        "last_bytes": 0,
        "latest_bytes": 0,
        "latest_total": total_safe,
        "ud_type": ud_type,
        "start": now,
        "samples": [(now, 0)],
        "last_sample_time": edit_done,
        "ema_speed": 0.0,
        "frame_idx": 1,
        "min_interval": 1.6,
        "cooldown_until": 0.0,
        "in_flight": False,
        "last_text": text,
    }
    _PROGRESS_LAST_EDIT[msg_key] = edit_done
    return edited_msg, now


async def progress_for_pyrogram(current, total, ud_type, message, start):
    now = time.time()
    msg_key = _get_msg_key(message)
    total_safe = max(int(total or 0), 1)
    current_clamped = max(0, min(int(current or 0), total_safe))

    state = _PROGRESS_STATE.get(msg_key)
    legacy_last = _PROGRESS_LAST_EDIT.get(msg_key)
    if state is None:
        init_last = legacy_last if legacy_last is not None else 0.0
        state = {
            "last_edit": init_last,
            "synced_legacy_last": init_last,
            "last_pct": 0.0,
            "last_bytes": 0,
            "latest_bytes": current_clamped,
            "latest_total": total_safe,
            "ud_type": ud_type,
            "start": start,
            "samples": [(start, 0)],
            "last_sample_time": start,
            "ema_speed": 0.0,
            "frame_idx": 0,
            "min_interval": 1.6,
            "cooldown_until": 0.0,
            "in_flight": False,
            "last_text": "",
        }
        _PROGRESS_STATE[msg_key] = state
    elif legacy_last is not None and legacy_last != state.get("synced_legacy_last"):
        # Sync if caller/test mutated `_PROGRESS_LAST_EDIT` directly
        state["last_edit"] = legacy_last
        state["synced_legacy_last"] = legacy_last

    # Always keep live transfer snapshot up-to-date for manual Refresh button clicks
    state["latest_bytes"] = current_clamped
    state["latest_total"] = total_safe
    state["ud_type"] = ud_type
    state["start"] = start
    display_speed = _compute_stable_speed(state, current_clamped, now, start)

    # Never overlap concurrent Telegram EditMessage RPCs on the same message
    if state.get("in_flight", False):
        return

    # Respect any active FloodWait cooldown window without stalling media workers
    if now < state.get("cooldown_until", 0.0):
        return

    percentage = current_clamped * 100.0 / total_safe

    elapsed_since_edit = now - state.get("last_edit", 0.0)
    pct_jump = abs(percentage - state.get("last_pct", 0.0))
    min_interval = state.get("min_interval", 1.6)
    is_complete = current_clamped >= total_safe

    should_edit = (
        elapsed_since_edit >= min_interval
        or (pct_jump >= 8.0 and elapsed_since_edit >= 0.9)
        or (is_complete and state.get("last_pct", 0.0) < 100.0 and elapsed_since_edit >= 0.6)
    )
    if not should_edit:
        return

    frame_idx = state.get("frame_idx", 0)
    text = build_progress_text(
        current_clamped,
        total_safe,
        ud_type,
        start,
        frame_idx=frame_idx,
        speed_override=display_speed,
    )

    if text == state.get("last_text"):
        return

    state["in_flight"] = True
    state["last_edit"] = now
    state["synced_legacy_last"] = now
    state["last_pct"] = percentage
    state["last_bytes"] = current_clamped
    state["last_sample_time"] = now
    state["frame_idx"] = frame_idx + 1
    _PROGRESS_LAST_EDIT[msg_key] = now

    try:
        await message.edit(
            text=text,
            reply_markup=_CANCEL_MARKUP,
        )
        finish_now = time.time()
        state["last_edit"] = finish_now
        state["synced_legacy_last"] = finish_now
        state["last_text"] = text
        _PROGRESS_LAST_EDIT[msg_key] = finish_now
    except MessageNotModified:
        state["last_text"] = text
    except FloodWait as e:
        wait_s = float(getattr(e, "value", getattr(e, "x", 3)) or 3)
        cooldown_ts = time.time() + wait_s + 0.5
        state["cooldown_until"] = cooldown_ts
        state["last_edit"] = cooldown_ts
        state["synced_legacy_last"] = cooldown_ts
        state["min_interval"] = min(4.0, state.get("min_interval", 1.6) + 0.6)
        _PROGRESS_LAST_EDIT[msg_key] = cooldown_ts
    except Exception:
        pass
    finally:
        state["in_flight"] = False
        if is_complete:
            _PROGRESS_LAST_EDIT.pop(msg_key, None)


async def refresh_progress_message(query) -> None:
    """
    Handle on-demand `refresh_progress` button clicks on the progress bar card.
    Renders the latest smoothed transfer progress and answers the callback query.
    """
    msg = getattr(query, "message", None)
    if msg is None:
        return
    msg_key = _get_msg_key(msg)
    state = _PROGRESS_STATE.get(msg_key)
    now = time.time()

    if state is None:
        try:
            await query.answer("⚡ ᴛʀᴀɴsꜰᴇʀ ɪs ɪɴɪᴛɪᴀʟɪᴢɪɴɢ...", show_alert=False)
        except Exception:
            pass
        return

    current_clamped = state.get("latest_bytes", state.get("last_bytes", 0))
    total_safe = max(int(state.get("latest_total", 1) or 1), 1)
    ud_type = state.get("ud_type", "<blockquote>🚀 <b>ᴘʀᴏᴄᴇssɪɴɢ ᴍᴇᴅɪᴀ...</b> ⚡</blockquote>")
    start = state.get("start", now - 1.0)
    display_speed = _compute_stable_speed(state, current_clamped, now, start)
    pct = round(current_clamped * 100.0 / total_safe, 1)

    if not state.get("in_flight", False) and now >= state.get("cooldown_until", 0.0):
        frame_idx = state.get("frame_idx", 0)
        text = build_progress_text(
            current_clamped,
            total_safe,
            ud_type,
            start,
            frame_idx=frame_idx,
            speed_override=display_speed,
        )
        state["frame_idx"] = frame_idx + 1
        if text != state.get("last_text"):
            state["in_flight"] = True
            try:
                await msg.edit(text=text, reply_markup=_CANCEL_MARKUP)
                finish_now = time.time()
                state["last_edit"] = finish_now
                state["synced_legacy_last"] = finish_now
                state["last_text"] = text
                _PROGRESS_LAST_EDIT[msg_key] = finish_now
            except MessageNotModified:
                state["last_text"] = text
            except FloodWait as e:
                wait_s = float(getattr(e, "value", getattr(e, "x", 3)) or 3)
                state["cooldown_until"] = time.time() + wait_s + 0.5
            except Exception:
                pass
            finally:
                state["in_flight"] = False

    try:
        await query.answer(
            f"⚡ {pct}%  •  {humanbytes(display_speed)}/s",
            show_alert=False,
        )
    except Exception:
        pass



def humanbytes(size):    
    if not size or size <= 0:
        return "0 B"
    power = 2**10
    n = 0
    Dic_powerN = {0: ' ', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'B'


def TimeFormatter(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = ((str(days) + "d, ") if days else "") + \
        ((str(hours) + "h, ") if hours else "") + \
        ((str(minutes) + "m, ") if minutes else "") + \
        ((str(seconds) + "s, ") if seconds else "") + \
        ((str(milliseconds) + "ms, ") if milliseconds else "")
    return tmp[:-2] 

def convert(seconds):
    seconds = seconds % (24 * 3600)
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60      
    return "%d:%02d:%02d" % (hour, minutes, seconds)

async def send_log(b, u):
    if Config.LOG_CHANNEL is not None:
        curr = datetime.now(timezone("Asia/Kolkata"))
        date = curr.strftime('%d %B, %Y')
        time_str = curr.strftime('%I:%M:%S %p')
        await b.send_message(
            Config.LOG_CHANNEL,
            f"<blockquote>✨ <b>ɴᴇᴡ ᴜsᴇʀ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ</b></blockquote>\n\n"
            f"╭─▸ 👤 <b>ᴜsᴇʀ :</b> {u.mention}\n"
            f"├─▸ 🆔 <b>ᴜsᴇʀ ɪᴅ :</b> <code>{u.id}</code>\n"
            f"├─▸ 🏷️ <b>ꜰɪʀsᴛ ɴᴀᴍᴇ :</b> <code>{u.first_name or 'N/A'}</code>\n"
            f"├─▸ 🏷️ <b>ʟᴀsᴛ ɴᴀᴍᴇ :</b> <code>{u.last_name or 'N/A'}</code>\n"
            f"├─▸ 🌐 <b>ᴜsᴇʀɴᴀᴍᴇ :</b> @{u.username or 'None'}\n"
            f"├─▸ 🔗 <b>ᴘʀᴏꜰɪʟᴇ :</b> <a href='tg://openmessage?user_id={u.id}'>ᴄʟɪᴄᴋ ʜᴇʀᴇ</a>\n"
            f"├─▸ 📅 <b>ᴅᴀᴛᴇ :</b> <code>{date}</code>\n"
            f"╰─▸ ⏰ <b>ᴛɪᴍᴇ :</b> <code>{time_str}</code>"
        )
        



def add_prefix_suffix(input_string, prefix='', suffix=''):
    pattern = r'(?P<filename>.*?)(\.\w+)?$'
    match = re.search(pattern, input_string)
    if match:
        filename = match.group('filename')
        extension = match.group(2) or ''
        if prefix == None:
            if suffix == None:
                return f"{filename}{extension}"
            return f"{filename} {suffix}{extension}"
        elif suffix == None:
            if prefix == None:
               return f"{filename}{extension}"
            return f"{prefix}{filename}{extension}"
        else:
            return f"{prefix}{filename} {suffix}{extension}"


    else:
        return input_string



def makedir(name: str):
    """
    Create a directory with the specified name.
    If a directory with the same name already exists, it will be removed and a new one will be created.
    """

    if os.path.exists(name):
        shutil.rmtree(name)
    os.mkdir(name)

# 📁 helper/utils.py

def get_file_name(message):
    media = message.document or message.video or message.audio
    return media.file_name if media else "Unknown_File"


# Developer @CosmicBotz
# Telegram Channel @CosmicBotz
