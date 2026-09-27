import asyncio
import os
import random
import shutil
import time
from typing import Any, Optional, Tuple
from PIL import Image, ImageStat
from bot.core.cache import cache_manager, ram_workspace

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".webm",
    ".flv",
    ".m4v",
    ".ts",
    ".wmv",
    ".3gp",
    ".mpg",
    ".mpeg",
}


def is_video_file(
    filename: Optional[str] = None,
    media_type: Any = None,
    upload_type: Optional[str] = None,
) -> bool:
    """
    Detect whether the file being renamed is a video (regardless of whether
    it was sent as a Telegram Document or Video, and regardless of metadata setting).
    """
    if upload_type and str(upload_type).lower() == "video":
        return True
    if media_type and "video" in str(media_type).lower():
        return True
    if filename:
        ext = os.path.splitext(str(filename))[1].lower()
        if ext in VIDEO_EXTENSIONS:
            return True
    return False


def _is_blank_or_dark_frame(image_path: str) -> bool:
    """
    Check if an extracted video frame is nearly pure black, pure white, or a solid blank screen.
    Returns True if the frame looks blank/black so the caller can try another timestamp.
    """
    try:
        with Image.open(image_path) as img:
            gray = img.convert("L")
            stat = ImageStat.Stat(gray)
            mean_luma = stat.mean[0]
            stddev_luma = stat.stddev[0]
            # Nearly black (< 12/255), nearly white (> 245/255), or flat solid color (stddev < 3.5)
            if mean_luma < 12.0 or mean_luma > 245.0 or stddev_luma < 3.5:
                return True
            return False
    except Exception:
        return True


def _build_seek_candidates(duration: int = 0, preferred_ttl: int = 30) -> list[int]:
    """
    Build an ordered list of seek timestamps (in seconds) prioritizing ~30s
    so intro black frames are skipped, with graceful fallbacks for shorter clips.
    """
    candidates: list[int] = []
    if duration and duration > 35:
        candidates.extend([
            max(30, preferred_ttl),
            min(duration - 2, max(45, duration // 3)),
            min(duration - 2, max(60, duration // 2)),
            15,
            5,
            1,
            0,
        ])
    elif duration and duration >= 10:
        candidates.extend([
            max(5, int(duration * 0.5)),
            max(3, int(duration * 0.3)),
            min(duration - 1, 10),
            2,
            0,
        ])
    elif duration and duration > 0:
        candidates.extend([max(1, duration // 2), 1, 0])
    else:
        # Unknown duration (e.g., video sent as Document without duration attribute):
        # Try 30s first; if video is shorter than 30s, FFmpeg falls back to 15s -> 5s -> 1s -> 0s
        candidates.extend([max(30, preferred_ttl), 45, 15, 5, 1, 0])

    # Deduplicate while preserving order
    seen = set()
    ordered = []
    for sec in candidates:
        sec_int = max(0, int(sec))
        if sec_int not in seen:
            seen.add(sec_int)
            ordered.append(sec_int)
    return ordered


async def fix_thumb(thumb: Optional[str]) -> Tuple[int, int, Optional[str]]:
    """
    Normalize a thumbnail image to RGB JPEG (<= 320x320) suitable for Telegram uploads.
    """
    width = 0
    height = 0
    try:
        if thumb is not None and os.path.exists(thumb):
            with Image.open(thumb) as img:
                rgb_img = img.convert("RGB")
                rgb_img.thumbnail((320, 320), Image.Resampling.LANCZOS)
                width, height = rgb_img.size
                rgb_img.save(thumb, "JPEG", quality=88, optimize=True)
    except Exception as e:
        print(f"fix_thumb error: {e}")
        thumb = None

    return width, height, thumb


async def get_cached_user_thumb(
    bot, c_thumb: str, user_id: int
) -> Tuple[int, int, Optional[str]]:
    """
    Retrieve a user's custom thumbnail from the in-memory `thumb_cache` if cached,
    or download + normalize once and store the JPEG bytes in RAM for subsequent renames.
    """
    cached_entry = cache_manager.thumb_cache.get(c_thumb)
    if cached_entry is not None:
        width, height, jpeg_bytes = cached_entry
        out_path = ram_workspace.resolve_thumb_path(
            f"thumb_{user_id}_{int(time.time() * 1000)}.jpg"
        )
        with open(out_path, "wb") as f:
            f.write(jpeg_bytes)
        return width, height, out_path

    raw_dest = ram_workspace.resolve_thumb_path(
        f"raw_thumb_{user_id}_{int(time.time() * 1000)}.jpg"
    )
    downloaded = await bot.download_media(c_thumb, file_name=raw_dest)
    width, height, fixed_path = await fix_thumb(downloaded)
    if fixed_path and os.path.exists(fixed_path):
        try:
            with open(fixed_path, "rb") as f:
                jpeg_bytes = f.read()
            cache_manager.thumb_cache.set(c_thumb, (width, height, jpeg_bytes))
        except Exception:
            pass
    return width, height, fixed_path


async def take_screen_shot(
    video_file: str, output_directory: str, ttl: int = 30, duration: int = 0
) -> Optional[str]:
    """
    Extract a non-blank video frame starting around `ttl` seconds (default 30s) using FFmpeg.
    Automatically skips black/blank intro frames by probing multiple seek offsets and
    verifying frame luminance/variance via Pillow.
    """
    if not shutil.which("ffmpeg"):
        return None

    os.makedirs(output_directory, exist_ok=True)
    out_put_file_name = os.path.join(
        output_directory, f"shot_{int(time.time() * 1000)}_{random.randint(100, 999)}.jpg"
    )
    fallback_file_name = os.path.join(
        output_directory, f"shot_fb_{int(time.time() * 1000)}_{random.randint(100, 999)}.jpg"
    )

    seek_candidates = _build_seek_candidates(duration=duration, preferred_ttl=ttl)

    for seek_sec in seek_candidates:
        try:
            if os.path.lexists(out_put_file_name):
                os.remove(out_put_file_name)
        except Exception:
            pass

        file_genertor_command = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-threads",
            "2",
            "-ss",
            str(max(0, int(seek_sec))),
            "-i",
            video_file,
            "-vf",
            "thumbnail=15",
            "-frames:v",
            "1",
            "-q:v",
            "2",
            out_put_file_name,
        ]
        try:
            process = await asyncio.create_subprocess_exec(
                *file_genertor_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            if os.path.lexists(out_put_file_name) and os.path.getsize(out_put_file_name) > 0:
                if not _is_blank_or_dark_frame(out_put_file_name):
                    # Clean up any saved fallback frame and return this rich frame
                    if os.path.lexists(fallback_file_name):
                        try:
                            os.remove(fallback_file_name)
                        except Exception:
                            pass
                    return out_put_file_name
                # Save the first valid decoded frame as fallback in case the entire clip is dark
                if not os.path.lexists(fallback_file_name):
                    try:
                        shutil.copyfile(out_put_file_name, fallback_file_name)
                    except Exception:
                        pass
        except Exception:
            pass

    if os.path.lexists(fallback_file_name) and os.path.getsize(fallback_file_name) > 0:
        try:
            shutil.move(fallback_file_name, out_put_file_name)
            return out_put_file_name
        except Exception:
            return fallback_file_name

    return None


async def extract_auto_thumbnail(
    bot,
    video_path: str,
    media: Any,
    duration: int = 0,
    user_id: int = 0,
    filename: Optional[str] = None,
    media_type: Any = None,
    upload_type: Optional[str] = None,
) -> Tuple[int, int, Optional[str]]:
    """
    Automatically obtain a thumbnail when the user has not set a custom thumbnail
    (works completely independently of whether user metadata is ON or OFF):
      1. Extracts a non-blank video frame via FFmpeg (`take_screen_shot`, seeking ~30s in
         to skip black intros) if the file is a video.
      2. Falls back to downloading `media.thumbs[0]` from Telegram if FFmpeg is
         unavailable or the file is not a video.
    """
    thumb_dir = (
        ram_workspace.shm_dir
        if ram_workspace.shm_available
        else os.path.dirname(os.path.abspath(video_path))
    )

    # 1. Extract frame directly from video file (seeking to ~30s first to avoid black start frames)
    if video_path and os.path.exists(video_path) and is_video_file(filename, media_type, upload_type):
        preferred_ttl = 30 if (not duration or duration > 35) else max(1, int(duration * 0.4))
        shot_path = await take_screen_shot(
            video_path, thumb_dir, ttl=preferred_ttl, duration=duration or 0
        )
        if shot_path:
            w, h, fixed = await fix_thumb(shot_path)
            if fixed:
                return w, h, fixed

    # 2. Fallback to embedded Telegram thumbnail if present
    thumbs = getattr(media, "thumbs", None)
    if thumbs:
        try:
            raw_dest = ram_workspace.resolve_thumb_path(
                f"tg_thumb_{user_id}_{int(time.time() * 1000)}.jpg"
            )
            dl_thumb = await bot.download_media(thumbs[0].file_id, file_name=raw_dest)
            if dl_thumb:
                return await fix_thumb(dl_thumb)
        except Exception:
            pass

    return 0, 0, None


async def add_metadata(
    input_path: str, output_path: str, metadata: str, ms
) -> Optional[str]:
    try:
        await ms.edit(
            "<blockquote>⚙️ <b>ᴍᴇᴛᴀᴅᴀᴛᴀ ᴇɴɢɪɴᴇ</b></blockquote>\n"
            "╭─ <b>sᴛᴀᴛᴜs :</b> <code>ɪɴᴊᴇᴄᴛɪɴɢ ᴍᴇᴛᴀᴅᴀᴛᴀ...</code> ⚡\n"
            f"╰─ <b>ᴛᴀɢ :</b> <code>{metadata}</code>"
        )
        command = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-threads",
            "2",
            "-i",
            input_path,
            "-map",
            "0",
            "-c:s",
            "copy",
            "-c:a",
            "copy",
            "-c:v",
            "copy",
            "-metadata",
            f"title={metadata}",
            "-metadata",
            f"author={metadata}",
            "-metadata:s:s",
            f"title={metadata}",
            "-metadata:s:a",
            f"title={metadata}",
            "-metadata:s:v",
            f"title={metadata}",
            "-metadata",
            f"artist={metadata}",
            output_path,
        ]

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        e_response = stderr.decode().strip()
        t_response = stdout.decode().strip()
        if e_response:
            print(e_response)
        if t_response:
            print(t_response)

        if os.path.exists(output_path):
            await ms.edit(
                "<blockquote>✅ <b>ᴍᴇᴛᴀᴅᴀᴛᴀ ᴇɴɢɪɴᴇ</b></blockquote>\n"
                "╰─ <b>sᴛᴀᴛᴜs :</b> <code>ᴍᴇᴛᴀᴅᴀᴛᴀ ɪɴᴊᴇᴄᴛᴇᴅ sᴜᴄᴄᴇssꜰᴜʟʟʏ!</code>"
            )
            return output_path
        else:
            await ms.edit(
                "<blockquote>❌ <b>ᴍᴇᴛᴀᴅᴀᴛᴀ ᴇɴɢɪɴᴇ</b></blockquote>\n"
                "╰─ <b>sᴛᴀᴛᴜs :</b> <code>ꜰᴀɪʟᴇᴅ ᴛᴏ ɪɴᴊᴇᴄᴛ ᴍᴇᴛᴀᴅᴀᴛᴀ</code>"
            )
            return None
    except Exception as e:
        print(f"Error occurred while adding metadata: {str(e)}")
        await ms.edit(
            "<blockquote>⚠️ <b>ᴍᴇᴛᴀᴅᴀᴛᴀ ᴇɴɢɪɴᴇ</b></blockquote>\n"
            "╰─ <b>sᴛᴀᴛᴜs :</b> <code>ᴇʀʀᴏʀ ᴡʜɪʟᴇ ᴀᴅᴅɪɴɢ ᴍᴇᴛᴀᴅᴀᴛᴀ</code>"
        )
        return None


# Developer @CosmicBotz
# Telegram Channel @CosmicBotz
