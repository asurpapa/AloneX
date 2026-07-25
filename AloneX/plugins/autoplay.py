# Copyright (c) 2025 TheHamkerAlone
# Licensed under the MIT License.
# Autoplay with Timer - ASURPAPA

import asyncio
from pyrogram import filters, types
from AloneX import app, anon, db, lang, queue

autoplay_status = {}
timers = {}


@app.on_message(
    filters.command(["autoplay"]) & filters.group & ~app.bl_users
)
@lang.language()
async def autoplay_toggle(_, m: types.Message):
    """Toggle autoplay on/off"""
    
    current = autoplay_status.get(m.chat.id, True)
    new_status = not current
    autoplay_status[m.chat.id] = new_status
    
    status_text = "✅ ON" if new_status else "❌ OFF"
    
    await m.reply_text(
        f"🎵 **Autoplay:** {status_text}",
        quote=True
    )


@app.on_message(
    filters.command(["forcenext"]) & filters.group & ~app.bl_users
)
@lang.language()
async def force_next_song(_, m: types.Message):
    """Force play next song"""
    try:
        if not await db.get_call(m.chat.id):
            return await m.reply_text("❌ Nothing is playing!", quote=True)
        
        # Cancel existing timer
        if m.chat.id in timers:
            timers[m.chat.id].cancel()
            timers.pop(m.chat.id)
        
        await anon.play_next(m.chat.id)
        await m.reply_text("⏭️ Next song!", quote=True)
    except Exception as e:
        await m.reply_text(f"❌ Error: {str(e)}", quote=True)


# Auto-advance when song ends (timer-based fallback)
@app.on_message(filters.command(["play", "vplay"]) & filters.group)
@lang.language()
async def monitor_play(_, m: types.Message):
    """Monitor song playback and auto-advance"""
    
    # Cancel previous timer if exists
    if m.chat.id in timers:
        timers[m.chat.id].cancel()
    
    # Get current song duration
    try:
        media = queue.get_current(m.chat.id)
        if media and hasattr(media, 'duration'):
            # Parse duration (format: MM:SS)
            parts = str(media.duration).split(':')
            if len(parts) == 2:
                duration = int(parts[0]) * 60 + int(parts[1])
            else:
                duration = 180  # Default 3 min
            
            # Add buffer time
            wait_time = duration + 3
            
            # Create timer task
            async def auto_next():
                await asyncio.sleep(wait_time)
                if autoplay_status.get(m.chat.id, True):
                    try:
                        await anon.play_next(m.chat.id)
                    except:
                        pass
                timers.pop(m.chat.id, None)
            
            # Start timer
            task = asyncio.create_task(auto_next())
            timers[m.chat.id] = task
    except Exception as e:
        print(f"Monitor error: {e}")
