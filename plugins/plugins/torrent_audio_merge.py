import asyncio
import ctypes
import functools
import gc
import inspect
import io
import logging
import math
import os
import re
import shutil
import socket
import sys
import time
from hashlib import md5, sha256
from pathlib import PurePath
from typing import Any, Callable, Dict, List, Optional, Tuple

from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from pyrogram import Client, StopTransmission, filters, raw, utils
from pyrogram.connection.transport.tcp import TCP
from pyrogram.enums import MessageMediaType
from pyrogram.errors import CDNFileHashMismatch, FloodPremiumWait, FloodWait, VolumeLocNotFound
from pyrogram.file_id import FileId, FileType, ThumbnailSource
from pyrogram.session.session import Session
from pyrogram.types import ForceReply, Message

from bot.core.cache import ram_workspace
from config import Config
from helper.database import Mythicbotz
from helper.ffmpeg import (
    add_metadata,
    extract_auto_thumbnail,
    get_cached_user_thumb,
    get_hd_cover_path,
    probe_video_dimensions_and_duration,
)
from helper.utils import (
    add_prefix_suffix,
    clear_transfer_cancellation,
    convert,
    humanbytes,
    init_progress_message,
    progress_for_pyrogram,
)

logger = logging.getLogger(__name__)

# =========================================================================
# SECTION 1: TURBO MTPROTO MULTI-SOCKET ACCELERATION ENGINE
# =========================================================================

CHUNK_SIZE_512KB: int = 512 * 1024
DOWNLOAD_CHUNK_1MB: int = 1024 * 1024
MIN_MEDIA_POOL_SIZE: int = 16
MAX_MEDIA_POOL_SIZE: int = 48
DEFAULT_MEDIA_POOL_SIZE: int = int(os.environ.get("MEDIA_POOL_SIZE", "24"))
_MTPROTO_PATCHED: bool = False

if sys.platform == "win32":
    try:
        ctypes.windll.winmm.timeBeginPeriod(1)
    except Exception:
        pass


def compute_dynamic_pool_size(file_size_bytes: int, is_upload: bool = False) -> Tuple[int, int]:
    """Calculate optimal media socket pool size and worker concurrency based on file size."""
    mb = file_size_bytes / (1024 * 1024)
    if is_upload:
        pool_size = 16 if mb <= 200 else 24
        workers = 32 if mb <= 200 else 48
        part_size = CHUNK_SIZE_512KB
    else:
        pool_size = 16
        workers = 32
        part_size = DOWNLOAD_CHUNK_1MB

    total_parts = max(1, math.ceil(file_size_bytes / part_size)) if file_size_bytes > 0 else pool_size
    actual_pool = min(pool_size, total_parts)
    actual_workers = min(workers, total_parts * 2 if is_upload else total_parts)
    return actual_pool, actual_workers


class FastCryptoEngine:
    """Hardware-accelerated AES-NI MTProto Crypto Engine using warpcrypto or pycryptodome."""

    def __init__(self) -> None:
        self.backend_name: str = "pure-python"
        self._warpcrypto: Any = None
        self._pycryptodome_aes: Any = None
        self._init_backend()

    def _init_backend(self) -> None:
        try:
            import warpcrypto  # type: ignore

            self._warpcrypto = warpcrypto
            self.backend_name = "warpcrypto (Rust AES-NI)"
            return
        except ImportError:
            pass

        try:
            from Crypto.Cipher import AES  # type: ignore

            self._pycryptodome_aes = AES
            self.backend_name = "pycryptodome (C AES-NI)"
        except ImportError:
            self.backend_name = "fallback"

    def ige256_encrypt(self, data: bytes, key: bytes, iv: bytes) -> bytes:
        if not data:
            return b""
        pad_len = (-len(data)) % 16
        if pad_len:
            data = data + os.urandom(pad_len)
        if self._warpcrypto is not None:
            return bytes(self._warpcrypto.ige256_encrypt(data, key, iv))
        from pyrogram.crypto import aes  # type: ignore

        return bytes(aes.ige256_encrypt(data, key, iv))

    def ige256_decrypt(self, data: bytes, key: bytes, iv: bytes) -> bytes:
        if not data:
            return b""
        if self._warpcrypto is not None:
            return bytes(self._warpcrypto.ige256_decrypt(data, key, iv))
        from pyrogram.crypto import aes  # type: ignore

        return bytes(aes.ige256_decrypt(data, key, iv))


def _patch_turbo_mtproto_engine(target_pool: int = DEFAULT_MEDIA_POOL_SIZE) -> None:
    global _MTPROTO_PATCHED
    if _MTPROTO_PATCHED:
        return

    try:
        from pyrogram.client import ReadAhead, write_at  # type: ignore
        from pyrogram.crypto import aes  # type: ignore
        import pyrogram.methods.advanced.save_file as save_file_mod  # type: ignore

        # Linux/Docker TCP keepalive optimization
        if not hasattr(TCP, "_turbo_patched_connect"):
            _orig_tcp_connect = TCP.connect

            async def _turbo_tcp_connect(self, address: tuple):
                await _orig_tcp_connect(self, address)
                try:
                    if self.writer is not None:
                        sock = self.writer.get_extra_info("socket")
                        if sock is not None:
                            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                            if hasattr(socket, "TCP_KEEPIDLE"):
                                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)
                            if hasattr(socket, "TCP_KEEPINTVL"):
                                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
                            if hasattr(socket, "TCP_KEEPCNT"):
                                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
                except OSError:
                    pass

            TCP.connect = _turbo_tcp_connect
            TCP._turbo_patched_connect = True

        Session.MAX_RETRIES = 2
        Session.WAIT_TIMEOUT = 8.0
        Session.MEDIA_WAIT_TIMEOUT = 12.0

        save_file_mod.POOL_SIZE = target_pool
        save_file_mod.PART_SIZE = CHUNK_SIZE_512KB

        # Parallel TCP Session Pool Creator
        if not hasattr(Client, "_turbo_get_media_session_pool_patched"):
            async def _turbo_get_media_session_pool(self: Any, dc_id: int, n: int) -> list:
                lock = self._media_sessions_locks.setdefault(dc_id, asyncio.Lock())
                async with lock:
                    pool = []
                    for session in self.media_session_pools.get(dc_id, []):
                        if getattr(session, "is_started", None) and session.is_started.is_set():
                            pool.append(session)
                        else:
                            utils.run_in_background(session.stop(), self.loop)

                    needed = n - len(pool)
                    if needed > 0:
                        media = await self.get_session(dc_id, is_media=True)
                        ports = [443, 80, 5222]
                        while needed > 0:
                            chunk = min(needed, 16)
                            gate = getattr(self, "_session_creation_gate", None)
                            if gate is None:
                                gate = asyncio.Semaphore(16)
                                self._session_creation_gate = gate
                            async with gate:
                                start_idx = len(pool)
                                pool.extend(
                                    await asyncio.gather(
                                        *(
                                            self._make_media_session(
                                                dc_id,
                                                media.auth_key,
                                                media.server_address,
                                                ports[(start_idx + i) % len(ports)],
                                            )
                                            for i in range(chunk)
                                        )
                                    )
                                )
                            needed -= chunk
                    self.media_session_pools[dc_id] = pool
                    return list(pool)

            Client._get_media_session_pool = _turbo_get_media_session_pool
            Client._turbo_get_media_session_pool_patched = True

        # High-Speed Lock-Free Save File Patch
        async def _stop_workers(queue: asyncio.Queue, workers: list) -> list:
            for _ in workers:
                try:
                    await asyncio.wait_for(queue.put(None), 4.0)
                except asyncio.TimeoutError:
                    break
            for t in workers:
                if not t.done():
                    t.cancel()
            return await asyncio.gather(*workers, return_exceptions=True)

        async def _turbo_save_file(
            self: Any,
            path: Any,
            file_id: Optional[int] = None,
            file_part: int = 0,
            progress: Optional[Callable] = None,
            progress_args: tuple = (),
        ):
            async with getattr(self, "save_file_semaphore", asyncio.Semaphore(128)):
                if path is None:
                    return None
                part_size = CHUNK_SIZE_512KB

                if isinstance(path, (str, PurePath)):
                    fp = open(path, "rb", buffering=16 * 1024 * 1024)
                elif isinstance(path, io.IOBase):
                    fp = path
                else:
                    raise ValueError("Invalid file pointer/path")

                file_name = getattr(fp, "name", "file.bin")
                fp.seek(0, os.SEEK_END)
                file_size = fp.tell()
                fp.seek(0)

                if file_size == 0:
                    if isinstance(path, (str, PurePath)):
                        fp.close()
                    raise ValueError("File size equals 0 B")

                file_total_parts = int(math.ceil(file_size / part_size))
                is_big = file_size > 10 * 1024 * 1024
                dyn_ul_pool, dyn_ul_workers = compute_dynamic_pool_size(file_size, is_upload=True)
                ul_pool_size = min(dyn_ul_pool, min(target_pool, file_total_parts)) if is_big else 1

                file_id = file_id or self.rnd_id()
                md5_sum = md5() if not is_big else None

                dc_id = await self.storage.dc_id()
                pool = await self._get_media_session_pool(dc_id, ul_pool_size)
                if not pool:
                    pool = [await self.get_session(dc_id, is_media=True)]

                n_sessions = len(pool)
                n_workers = min(dyn_ul_workers, min(n_sessions * 2, file_total_parts))
                queue = asyncio.Queue(n_workers * 2)

                read_ahead_budget = getattr(self, "read_ahead_slots", None)
                if not isinstance(read_ahead_budget, asyncio.Semaphore):
                    read_ahead_budget = asyncio.Semaphore(256)
                budget = ReadAhead(read_ahead_budget)
                _acked = [0]

                async def _send_part(worker_idx: int, data: Any) -> None:
                    sess_idx = worker_idx
                    for attempt in range(8):
                        live_sessions = [
                            s for s in pool if getattr(s, "is_started", None) and s.is_started.is_set()
                        ]
                        if not live_sessions:
                            await asyncio.sleep(0.2)
                            live_sessions = pool if pool else [self]
                        sess = live_sessions[(sess_idx + attempt) % len(live_sessions)]
                        try:
                            await sess.invoke(data, retries=2, timeout=8.0, sleep_threshold=5)
                            return
                        except StopTransmission:
                            raise
                        except (FloodWait, FloodPremiumWait) as fw:
                            await asyncio.sleep(min(getattr(fw, "value", 1) or 1, 10))
                        except asyncio.CancelledError:
                            return
                        except Exception:
                            if attempt >= 7:
                                raise
                            await asyncio.sleep(0.05 * (2 ** min(attempt, 3)))

                async def worker(worker_idx: int) -> None:
                    while True:
                        data = await queue.get()
                        if data is None:
                            return
                        try:
                            await _send_part(worker_idx, data)
                            _acked[0] += 1
                        finally:
                            budget.release()

                workers = [self.loop.create_task(worker(i)) for i in range(n_workers)]
                _last_report_time = 0.0

                async def _report(parts: int) -> None:
                    nonlocal _last_report_time
                    if not progress:
                        return
                    _now = time.monotonic()
                    if _now - _last_report_time < 0.1 and parts < file_total_parts:
                        return
                    _last_report_time = _now
                    func = functools.partial(
                        progress,
                        min(parts * part_size, file_size),
                        file_size,
                        *progress_args,
                    )
                    try:
                        if inspect.iscoroutinefunction(progress):
                            await func()
                        else:
                            await self.loop.run_in_executor(self.executor, func)
                    except Exception as e:
                        logger.debug("Upload progress callback error: %s", e)

                async def _producer() -> None:
                    nonlocal file_part
                    read_ahead_bytes = min(32 * part_size, 16 * 1024 * 1024)
                    fp.seek(part_size * file_part)
                    while file_part < file_total_parts:
                        batch = await self.loop.run_in_executor(
                            self.executor, fp.read, read_ahead_bytes
                        )
                        if not batch:
                            break
                        for start in range(0, len(batch), part_size):
                            chunk = batch[start : start + part_size]
                            if not is_big and md5_sum is not None:
                                md5_sum.update(chunk)
                            if is_big:
                                rpc = raw.functions.upload.SaveBigFilePart(
                                    file_id=file_id,
                                    file_part=file_part,
                                    file_total_parts=file_total_parts,
                                    bytes=chunk,
                                )
                            else:
                                rpc = raw.functions.upload.SaveFilePart(
                                    file_id=file_id,
                                    file_part=file_part,
                                    bytes=chunk,
                                )
                            file_part += 1
                            await budget.acquire()
                            await queue.put(rpc)

                producer_task = self.loop.create_task(_producer())
                try:
                    while _acked[0] < file_total_parts:
                        for t in workers:
                            if t.done() and not t.cancelled() and t.exception():
                                producer_task.cancel()
                                raise t.exception()
                        await _report(_acked[0])
                        await asyncio.sleep(0.05)
                finally:
                    if not producer_task.done():
                        producer_task.cancel()
                    await _stop_workers(queue, workers)
                    budget.release_all()
                    if isinstance(path, (str, PurePath)):
                        fp.close()

                await _report(file_total_parts)

                if is_big:
                    return raw.types.InputFileBig(
                        id=file_id, parts=file_total_parts, name=file_name
                    )
                return raw.types.InputFile(
                    id=file_id,
                    parts=file_total_parts,
                    name=file_name,
                    md5_checksum=md5_sum.hexdigest() if md5_sum else None,
                )

        save_file_mod.SaveFile.save_file = _turbo_save_file
        Client.save_file = _turbo_save_file
        _MTPROTO_PATCHED = True
        logger.info("Applied Lock-Free Multi-Socket Turbo Engine (pool=%d).", target_pool)
    except Exception as exc:
        logger.warning("Turbo MTProto engine patch skipped: %s", exc)


def auto_boost_client(client: Client) -> None:
    """Pre-configures client concurrency gates and applies MTProto turbo hooks."""
    try:
        client._session_creation_gate = asyncio.Semaphore(16)
        client.get_file_semaphore = asyncio.Semaphore(128)
        client.save_file_semaphore = asyncio.Semaphore(128)
    except Exception:
        pass
    _patch_turbo_mtproto_engine(target_pool=24)


# =========================================================================
# SECTION 2: ANIMATED PROGRESS BAR & TELEMETRY PARSER
# =========================================================================

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


def render_animated_bar(percentage: float, length: int = 10, frame_idx: int = 0) -> str:
    """Renders a smooth animated progress bar with rotating indicator pulses."""
    clamped_pct = max(0.0, min(100.0, percentage))
    filled_len = int(round((clamped_pct / 100.0) * length))
    spinner = SPINNER_FRAMES[frame_idx % len(SPINNER_FRAMES)]

    if filled_len >= length:
        bar = "▰" * length
    elif filled_len > 0:
        bar = ("▰" * (filled_len - 1)) + spinner + ("▱" * (length - filled_len))
    else:
        bar = spinner + ("▱" * (length - 1))
    return f"[{bar}]"


# =========================================================================
# SECTION 3: RE-ENCODING-FREE TORRENT AUDIO MUX ENGINE
# =========================================================================

ACTIVE_TORRENT_TASKS: Dict[int, Dict[str, Any]] = {}
VIDEO_EXTENSIONS = (".mkv", ".mp4", ".avi", ".mov", ".webm", ".ts", ".m4v", ".flv")
AUDIO_EXTENSIONS = (".mp3", ".aac", ".m4a", ".flac", ".wav", ".opus", ".ogg", ".ac3", ".eac3", ".dts")


async def _delayed_delete(*messages, delay: float = 1800.0) -> None:
    await asyncio.sleep(delay)
    for msg in messages:
        if msg is not None:
            try:
                await msg.delete()
            except Exception:
                pass


def _find_primary_video(target_dir: str) -> Optional[str]:
    if os.path.isfile(target_dir):
        return target_dir
    candidate, max_size = None, 0
    for root, _, files in os.walk(target_dir):
        for file in files:
            if file.lower().endswith(VIDEO_EXTENSIONS):
                full_path = os.path.join(root, file)
                sz = os.path.getsize(full_path)
                if sz > max_size:
                    max_size, candidate = sz, full_path
    return candidate


async def _download_torrent_aria2(torrent_source: str, download_dir: str, status_msg: Message) -> bool:
    """
    Downloads torrent with aria2c configured for maximum peer saturation.
    Displays dynamic speed, animated progress bar, seeds, and leechers.
    """
    if not shutil.which("aria2c"):
        raise RuntimeError("`aria2c` binary not found in PATH.")

    os.makedirs(download_dir, exist_ok=True)

    cmd = [
        "aria2c",
        f"--dir={download_dir}",
        "--seed-time=0",
        "--max-upload-limit=1K",
        "--max-connection-per-server=16",
        "--split=16",
        "--min-split-size=1M",
        "--summary-interval=1",
        "--follow-torrent=mem",
        "--enable-dht=true",
        "--enable-peer-exchange=true",
        "--bt-enable-lpd=true",
        "--bt-max-peers=128",
        "--bt-request-peer-speed-limit=100M",
        "--auto-file-renaming=false",
        "--allow-overwrite=true",
        torrent_source,
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    last_update = time.time()
    frame_idx = 0

    while True:
        line = await process.stdout.readline()
        if not line:
            break
        decoded = line.decode("utf-8", errors="ignore").strip()

        now = time.time()
        # Throttled to 4.0s to completely avoid Telegram FloodWait
        if now - last_update >= 4.0:
            pct_m = re.search(r"\((\d+(?:\.\d+)?)\%\)", decoded)
            dl_m = re.search(r"DL:([0-9.]+[A-Za-z]+)", decoded)
            eta_m = re.search(r"ETA:([0-9A-Za-z]+)", decoded)
            cn_m = re.search(r"CN:(\d+)", decoded)
            sd_m = re.search(r"SD:(\d+)", decoded)

            if pct_m and dl_m:
                pct = float(pct_m.group(1))
                speed = dl_m.group(1)
                eta = eta_m.group(1) if eta_m else "N/A"
                leechers = cn_m.group(1) if cn_m else "0"
                seeds = sd_m.group(1) if sd_m else "0"

                bar = render_animated_bar(pct, length=10, frame_idx=frame_idx)
                frame_idx += 1

                progress_text = (
                    "<blockquote>⚡ <b>ᴛᴏʀʀᴇɴᴛ ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ...</b></blockquote>\n"
                    f"╭─ 📊 <b>ᴘʀᴏɢʀᴇss :</b> <code>{bar} {pct:.1f}%</code>\n"
                    f"├─ 🚀 <b>sᴘᴇᴇᴅ :</b> <code>{speed}/s</code>\n"
                    f"├─ ⏱️ <b>ᴇᴛᴀ :</b> <code>{eta}</code>\n"
                    f"╰─ 👥 <b>sᴇᴇᴅs :</b> <code>{seeds}</code> | <b>ʟᴇᴇᴄʜᴇʀs :</b> <code>{leechers}</code>"
                )
                try:
                    await status_msg.edit(progress_text)
                    last_update = now
                except FloodWait as fw:
                    await asyncio.sleep(fw.value)
                except Exception:
                    pass

        await asyncio.sleep(0.02)

    return_code = await process.wait()
    return return_code == 0


async def _mux_audio_stream_copy(video_input: str, audio_input: str, output_path: str) -> bool:
    """Stream-copy muxing with FFmpeg using ZERO re-encoding to preserve CPU."""
    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_input,
        "-i", audio_input,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-map", "0:a?",
        "-map", "0:s?",
        "-c", "copy",
        "-disposition:a", "0",
        "-disposition:a:0", "default",
        output_path,
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    await asyncio.sleep(0.5)

    if process.returncode != 0:
        logger.error("FFmpeg stream-copy error: %s", stderr.decode("utf-8", errors="ignore"))
        return False
    return os.path.exists(output_path) and os.path.getsize(output_path) > 0


# =========================================================================
# SECTION 4: PYROGRAM BOT HANDLERS
# =========================================================================

@Client.on_message(
    filters.private
    & (
        filters.command(["tmux", "torrent", "torrent_audio"])
        | filters.regex(r"^(magnet:\?xt=|https?://.*?\.(torrent))")
    )
)
async def torrent_start(client: Client, message: Message):
    auto_boost_client(client)
    user_id = int(message.from_user.id)

    if await Mythicbotz.is_banned(user_id):
        return await message.reply(
            "<blockquote>🚫 <b>ᴀᴄᴄᴇss ᴅᴇɴɪᴇᴅ</b></blockquote>\n"
            "╰─ <b>ʏᴏᴜ ᴀʀᴇ ʙᴀɴɴᴇᴅ ꜰʀᴏᴍ ᴜsɪɴɢ ᴛʜɪs ʙᴏᴛ. ᴄᴏɴᴛᴀᴄᴛ @CosmicBotz.</b>"
        )

    torrent_source = None
    if message.matches:
        torrent_source = message.text.strip()
    elif len(message.command) > 1:
        torrent_source = message.text.split(None, 1)[1].strip()
    elif message.reply_to_message and message.reply_to_message.text:
        reply_txt = message.reply_to_message.text.strip()
        if reply_txt.startswith("magnet:?xt=") or ".torrent" in reply_txt:
            torrent_source = reply_txt

    if not torrent_source:
        return await message.reply_text(
            "<blockquote>⚠️ <b>ᴍɪssɪɴɢ ᴛᴏʀʀᴇɴᴛ sᴏᴜʀᴄᴇ</b></blockquote>\n\n"
            "╰─ <i>Send the command along with a magnet link or .torrent URL:</i>\n"
            "<code>/tmux magnet:?xt=urn:btih:...</code>",
            reply_to_message_id=message.id,
        )

    old_task = ACTIVE_TORRENT_TASKS.pop(user_id, None)
    if old_task:
        ram_workspace.cleanup_files(old_task.get("torrent_video"))
        if os.path.exists(old_task.get("torrent_dir", "")):
            shutil.rmtree(old_task.get("torrent_dir"), ignore_errors=True)

    status_msg = await message.reply_text(
        "<blockquote>🚀 <b>ɪɴɪᴛɪᴀʟɪᴢɪɴɢ ᴛᴏʀʀᴇɴᴛ ᴇɴɢɪɴᴇ...</b></blockquote>",
        reply_to_message_id=message.id,
    )

    work_dir = os.path.join("/tmp", f"torrent_{user_id}_{int(time.time())}")
    os.makedirs(work_dir, exist_ok=True)

    try:
        success = await _download_torrent_aria2(torrent_source, work_dir, status_msg)
        if not success:
            shutil.rmtree(work_dir, ignore_errors=True)
            return await status_msg.edit("<blockquote>❌ <b>ᴛᴏʀʀᴇɴᴛ ᴅᴏᴡɴʟᴏᴀᴅ ꜰᴀɪʟᴇᴅ. ᴄʜᴇᴄᴋ sᴇᴇᴅs.</b></blockquote>")
    except Exception as e:
        shutil.rmtree(work_dir, ignore_errors=True)
        return await status_msg.edit(f"<blockquote>❌ <b>ᴇʀʀᴏʀ :</b> <code>{e}</code></blockquote>")

    video_file = _find_primary_video(work_dir)
    if not video_file:
        shutil.rmtree(work_dir, ignore_errors=True)
        return await status_msg.edit("<blockquote>❌ <b>ɴᴏ ᴠᴀʟɪᴅ ᴠɪᴅᴇᴏ ꜰɪʟᴇ ꜰᴏᴜɴᴅ ɪɴ ᴛᴏʀʀᴇɴᴛ.</b></blockquote>")

    vid_name = os.path.basename(video_file)
    vid_size = humanbytes(os.path.getsize(video_file))

    prompt = await message.reply_text(
        "<blockquote>🎵 <b>sᴇɴᴅ ᴀᴜᴅɪᴏ / ᴠɪᴅᴇᴏ ᴛᴏ sᴇᴛ ᴀs ᴅᴇꜰᴀᴜʟᴛ</b></blockquote>\n\n"
        f"╭─ 🎬 <b>ᴛᴏʀʀᴇɴᴛ ᴠɪᴅᴇᴏ :</b> <code>{vid_name}</code>\n"
        f"├─ 📦 <b>sɪᴢᴇ :</b> <code>{vid_size}</code>\n"
        "╰─ <i>Reply to this message with an Audio or Video file whose audio track you want to inject as default.</i>",
        reply_markup=ForceReply(True),
    )

    ACTIVE_TORRENT_TASKS[user_id] = {
        "torrent_video": video_file,
        "torrent_dir": work_dir,
        "torrent_name": vid_name,
        "prompt_id": prompt.id,
        "timestamp": time.time(),
    }

    try:
        await status_msg.delete()
    except Exception:
        pass

    async def _auto_abort():
        await asyncio.sleep(900)
        task = ACTIVE_TORRENT_TASKS.get(user_id)
        if task and task.get("prompt_id") == prompt.id:
            ACTIVE_TORRENT_TASKS.pop(user_id, None)
            if os.path.exists(work_dir):
                shutil.rmtree(work_dir, ignore_errors=True)
            try:
                await prompt.edit("<blockquote>⏱️ <b>ᴛᴏʀʀᴇɴᴛ ᴍᴜxɪɴɢ sᴇssɪᴏɴ ᴇxᴘɪʀᴇᴅ.</b></blockquote>")
            except Exception:
                pass

    asyncio.create_task(_auto_abort())


@Client.on_message(filters.private & filters.reply & (filters.audio | filters.video | filters.document))
async def handle_mux_reply(bot: Client, message: Message):
    auto_boost_client(bot)
    user_id = int(message.from_user.id)
    reply_msg = message.reply_to_message

    if not (reply_msg and reply_msg.reply_markup and isinstance(reply_msg.reply_markup, ForceReply)):
        return

    task = ACTIVE_TORRENT_TASKS.get(user_id)
    if not task or task.get("prompt_id") != reply_msg.id:
        return

    media = getattr(message, message.media.value) if message.media else None
    if not media:
        return await message.reply_text("<blockquote>⚠️ <b>ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴀ ᴠᴀʟɪᴅ ᴍᴇᴅɪᴀ ꜰɪʟᴇ.</b></blockquote>")

    fname = getattr(media, "file_name", "") or ""
    is_valid_media = (
        message.media in (MessageMediaType.AUDIO, MessageMediaType.VIDEO)
        or fname.lower().endswith(AUDIO_EXTENSIONS + VIDEO_EXTENSIONS)
        or (getattr(media, "mime_type", "") or "").startswith(("audio/", "video/"))
    )

    if not is_valid_media:
        return await message.reply_text("<blockquote>⚠️ <b>ᴛʜɪs ꜰɪʟᴇ ᴅᴏᴇs ɴᴏᴛ ᴄᴏɴᴛᴀɪɴ ᴀ ʀᴇᴄᴏɢɴɪᴢᴇᴅ ᴀᴜᴅɪᴏ/ᴠɪᴅᴇᴏ sᴛʀᴇᴀᴍ.</b></blockquote>")

    ACTIVE_TORRENT_TASKS.pop(user_id, None)

    torrent_video = task["torrent_video"]
    torrent_dir = task["torrent_dir"]
    torrent_name = task["torrent_name"]

    user_data = await Mythicbotz.get_user_data(user_id) or {}
    prefix = user_data.get("prefix")
    suffix = user_data.get("suffix")
    _bool_metadata = bool(user_data.get("metadata", False))
    user_metadata_code = user_data.get("metadata_code") or "By :- @CosmicBotz"
    c_caption = user_data.get("caption")
    c_thumb = user_data.get("file_id")
    dest_channel = user_data.get("destination_channel")

    base_out_name = os.path.splitext(torrent_name)[0] + ".mkv"
    try:
        new_filename = add_prefix_suffix(base_out_name, prefix, suffix)
    except Exception:
        new_filename = base_out_name

    user_media_path = os.path.join(torrent_dir, f"input_audio_{media.file_id[:8]}")
    muxed_output_path = os.path.join(torrent_dir, f"muxed_{new_filename}")
    meta_output_path, ph_path, cover_path = None, None, None

    # Step A: Download Audio/Video Replacement Track
    dl_header = "<blockquote>📥 <b>ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ ʏᴏᴜʀ ᴀᴜᴅɪᴏ...</b> ⚡</blockquote>"
    ms, dl_start = await init_progress_message(message, dl_header, getattr(media, "file_size", 0) or 0)

    dl_client = getattr(bot, "helper_client", None) or getattr(bot, "premium_client", None) or bot
    auto_boost_client(dl_client)
    try:
        user_media_path = await dl_client.download_media(
            message=message,
            file_name=user_media_path,
            progress=progress_for_pyrogram,
            progress_args=(dl_header, ms, dl_start),
        )
    except Exception as e:
        clear_transfer_cancellation(user_id, ms.id)
        shutil.rmtree(torrent_dir, ignore_errors=True)
        return await ms.edit(f"<blockquote>❌ <b>ᴀᴜᴅɪᴏ ᴅᴏᴡɴʟᴏᴀᴅ ꜰᴀɪʟᴇᴅ :</b> <code>{e}</code></blockquote>")

    # Step B: Zero-encoding Stream Copy Muxing
    await ms.edit(
        "<blockquote>⚙️ <b>ᴍᴜxɪɴɢ ᴀᴜᴅɪᴏ sᴛʀᴇᴀᴍ...</b> ⚡</blockquote>\n"
        "╰─ <i>Lossless stream-copy in progress (zero re-encoding)...</i>"
    )
    await asyncio.sleep(1.0)

    success_mux = await _mux_audio_stream_copy(torrent_video, user_media_path, muxed_output_path)
    if not success_mux:
        shutil.rmtree(torrent_dir, ignore_errors=True)
        return await ms.edit("<blockquote>❌ <b>ꜰꜰᴍᴘᴇɢ ᴍᴜxɪɴɢ ꜰᴀɪʟᴇᴅ. ᴄʜᴇᴄᴋ ᴀᴜᴅɪᴏ ᴄᴏᴍᴘᴀᴛɪʙɪʟɪᴛʏ.</b></blockquote>")

    final_upload_path = muxed_output_path

    # Step C: Metadata Application
    if _bool_metadata:
        try:
            await ms.edit(
                "<blockquote>🏷️ <b>ᴀᴘᴘʟʏɪɴɢ ᴍᴇᴛᴀᴅᴀᴛᴀ...</b> ⚡</blockquote>\n"
                "╰─ <i>Writing metadata tags...</i>"
            )
            meta_dir = os.path.join(torrent_dir, "meta_out")
            os.makedirs(meta_dir, exist_ok=True)
            meta_output_path = os.path.join(meta_dir, new_filename)

            res_meta = await add_metadata(muxed_output_path, meta_output_path, user_metadata_code, ms)
            if res_meta and os.path.exists(meta_output_path):
                final_upload_path = meta_output_path
        except Exception as e:
            logger.error("Metadata application failed: %s", e)
            final_upload_path = muxed_output_path

    # Step D: Media Probing (Duration, Width, Height)
    duration, width, height = 0, 1280, 720
    try:
        p_w, p_h, p_dur = await probe_video_dimensions_and_duration(final_upload_path)
        if p_w > 0:
            width = int(p_w)
        if p_h > 0:
            height = int(p_h)
        if p_dur > 0:
            duration = int(p_dur)
    except Exception:
        pass

    if not duration or not width or not height:
        try:
            parser = createParser(final_upload_path)
            if parser:
                with parser:
                    meta_info = extractMetadata(parser)
                    if meta_info:
                        if not duration and meta_info.has("duration"):
                            duration = meta_info.get("duration").seconds
                        if meta_info.has("width"):
                            width = int(meta_info.get("width") or 1280)
                        if meta_info.has("height"):
                            height = int(meta_info.get("height") or 720)
        except Exception:
            pass

    # Step E: Thumbnail Generation
    video_cover = None
    try:
        if c_thumb:
            _, _, ph_path = await get_cached_user_thumb(bot, c_thumb, user_id)
            video_cover = c_thumb or ph_path
        else:
            frame_w, frame_h, ph_path = await extract_auto_thumbnail(
                bot=bot,
                video_path=final_upload_path,
                media=media,
                duration=duration,
                user_id=user_id,
                filename=new_filename,
                media_type=MessageMediaType.VIDEO,
                upload_type="video",
            )
            cover_path = get_hd_cover_path(ph_path)
            video_cover = cover_path or ph_path
            if not width and frame_w:
                width = int(frame_w)
            if not height and frame_h:
                height = int(frame_h)
    except Exception as e:
        logger.warning("Thumbnail extraction skipped: %s", e)

    # Step F: Caption Construction
    final_size = os.path.getsize(final_upload_path)
    if c_caption:
        try:
            caption = c_caption.format(
                filename=f"<b>{new_filename}</b>",
                filesize=humanbytes(final_size),
                duration=convert(duration),
            )
        except Exception:
            caption = f"<b>{new_filename}</b>"
    else:
        caption = f"<b>{new_filename}</b>"

    # Step G: Multi-Socket Turbo Upload
    ul_header = "<blockquote>💠 <b>ᴜᴘʟᴏᴀᴅɪɴɢ ᴍᴜxᴇᴅ ᴍᴇᴅɪᴀ...</b> ⚡</blockquote>"
    ms, ul_start = await init_progress_message(ms, ul_header, final_size)

    try:
        sent_message = await bot.send_video(
            chat_id=user_id,
            video=final_upload_path,
            file_name=new_filename,
            caption=caption,
            duration=duration,
            width=width,
            height=height,
            supports_streaming=True,
            thumb=ph_path,
            video_cover=video_cover,
            progress=progress_for_pyrogram,
            progress_args=(ul_header, ms, ul_start),
        )

        if Config.BIN_CHANNEL:
            try:
                bin_caption = (
                    f"<blockquote>🎬 <b>{new_filename}</b></blockquote>\n"
                    f"╭─ 👤 <b>ᴜsᴇʀ :</b> {message.chat.first_name} (<code>{user_id}</code>)\n"
                    f"├─ 📦 <b>sɪᴢᴇ :</b> <code>{humanbytes(final_size)}</code>\n"
                    f"╰─ ⏱️ <b>ᴅᴜʀᴀᴛɪᴏɴ :</b> <code>{convert(duration)}</code>"
                )
                await bot.copy_message(
                    chat_id=Config.BIN_CHANNEL,
                    from_chat_id=user_id,
                    message_id=sent_message.id,
                    caption=bin_caption,
                )
            except Exception as e:
                logger.error("Failed copying to BIN_CHANNEL: %s", e)

        if dest_channel:
            try:
                await bot.copy_message(
                    chat_id=int(dest_channel),
                    from_chat_id=user_id,
                    message_id=sent_message.id,
                )
            except Exception as e:
                logger.error("Failed copying to dest_channel: %s", e)

        await Mythicbotz.increase_rename_count(user_id)

        deletion_msg = await sent_message.reply(
            "<blockquote>🗑️ <b>ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ɴᴏᴛɪᴄᴇ</b></blockquote>\n"
            "╰─ <b>ᴛʜɪs ꜰɪʟᴇ ᴡɪʟʟ ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ɪɴ <code>30 ᴍɪɴᴜᴛᴇs</code>. ꜰᴏʀᴡᴀʀᴅ / sᴀᴠᴇ ɪᴛ ɴᴏᴡ!</b>"
        )
        asyncio.create_task(_delayed_delete(sent_message, deletion_msg, delay=1800.0))

    except StopTransmission:
        clear_transfer_cancellation(user_id, ms.id)
        return
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return
    except Exception as e:
        logger.error("Upload failed: %s", e)
        clear_transfer_cancellation(user_id, ms.id)
        return await ms.edit(f"<blockquote>❌ <b>ᴜᴘʟᴏᴀᴅ ꜰᴀɪʟᴇᴅ :</b> <code>{e}</code></blockquote>")
    finally:
        ram_workspace.cleanup_files(ph_path, cover_path, meta_output_path)
        if os.path.exists(torrent_dir):
            shutil.rmtree(torrent_dir, ignore_errors=True)
        try:
            await ms.delete()
            await reply_msg.delete()
        except Exception:
            pass