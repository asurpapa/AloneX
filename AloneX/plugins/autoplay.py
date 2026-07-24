# Copyright (c) 2025 TheHamkerAlone
# Licensed under the MIT License.
# Enhanced Autoplay System - ASURPAPA

import asyncio
from pyrogram import filters, types
from AloneX import app, anon, db, lang, queue
import time

# Track play status
play_status = {}
stream_watchdog = {}


async def start_watchdog(chat_id: int):
    """Start monitoring song playback for auto-advance"""
    try:
        if chat_id in stream_watchdog:
            return
        
        stream_watchdog[chat_id] = True
        media = queue.get_current(chat_id)
        
        if not media:
            return
        
        duration = int(media.duration.split(":")[-1]) if ":" in media.duration else 180
        wait_time = duration + 2
        
        await asyncio.sleep(wait_time)
        
        if stream_watchdog.get(chat_id):
            await anon.play_next(chat_id)
            
    except Exception as e:
        print(f"Watchdog error: {e}")
    finally:
        stream_watchdog.pop(chat_id, None)


async def stop_watchdog(chat_id: int):
    """Stop monitoring for a chat"""
    stream_watchdog.pop(chat_id, None)


@app.on_message(
    filters.command(["autoplay"]) & filters.group & ~app.bl_users
)
@lang.language()
async def autoplay_toggle(_, m: types.Message):
    """Toggle autoplay on/off"""
    
    current = play_status.get(m.chat.id, True)
    new_status = not current
    play_status[m.chat.id] = new_status
    
    status_text = "✅ ON" if new_status else "❌ OFF"
    
    await m.reply_text(
        f"🎵 **Autoplay:** {status_text}\n\n"
        f"Next song will {'automatically' if new_status else 'NOT'} play when current song ends.",
        quote=True
    )


@app.on_message(
    filters.command(["autoplaystatus"]) & filters.group & ~app.bl_users
)
@lang.language()
async def check_autoplay_status(_, m: types.Message):
    """Check current autoplay status"""
    
    status = play_status.get(m.chat.id, True)
    status_text = "✅ ENABLED" if status else "❌ DISABLED"
    
    info_text = f"""
🎵 **Autoplay Status**

Current: {status_text}

When autoplay is enabled:
✅ Songs play automatically
✅ Queue advances automatically
✅ No manual skip needed

When autoplay is disabled:
❌ Manual skip required
❌ Use /skip command
❌ Or click skip button

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Use `/autoplay` to toggle
"""
    
    await m.reply_text(info_text, quote=True)


@app.on_message(
    filters.command(["forcenext"]) & filters.group & ~app.bl_users
)
@lang.language()
async def force_next_song(_, m: types.Message):
    """Force play next song (fallback for autoplay)"""
    try:
        if not await db.get_call(m.chat.id):
            return await m.reply_text("❌ Nothing is playing!", quote=True)
        
        await anon.play_next(m.chat.id)
        await m.reply_text("⏭️ Playing next song!", quote=True)
    except Exception as e:
        await m.reply_text(f"❌ Error: {str(e)}", quote=True)
