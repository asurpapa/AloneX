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
    filters.command(["autoplaystatus"]) & filters.group & ~app.bl_users
)
@lang.language()
async def check_status(_, m: types.Message):
    """Check autoplay status"""
    status = autoplay_status.get(m.chat.id, True)
    status_text = "✅ ENABLED" if status else "❌ DISABLED"
    await m.reply_text(f"🎵 **Autoplay:** {status_text}", quote=True)


@app.on_message(
    filters.command(["forcenext"]) & filters.group & ~app.bl_users
)
@lang.language()
async def force_next_song(_, m: types.Message):
    """Force play next song"""
    try:
        call_info = await db.get_call(m.chat.id)
        if not call_info:
            return await m.reply_text("❌ Nothing is playing!", quote=True)
        
        # Cancel timer
        if m.chat.id in timers:
            try:
                timers[m.chat.id].cancel()
            except:
                pass
            timers.pop(m.chat.id, None)
        
        # Check if queue has songs
        q = queue.get(m.chat.id)
        if not q or len(q) == 0:
            return await m.reply_text("❌ No songs in queue!", quote=True)
        
        await anon.play_next(m.chat.id)
        await m.reply_text("⏭️ Next song!", quote=True)
    except Exception as e:
        await m.reply_text(f"❌ Error: {str(e)[:100]}", quote=True)


@app.on_message(filters.command(["play", "vplay"]) & filters.group)
@lang.language()
async def monitor_play(_, m: types.Message):
    """Monitor song playback and auto-advance"""
    
    if m.chat.id in timers:
        timers[m.chat.id].cancel()
    
    try:
        media = queue.get_current(m.chat.id)
        if media and hasattr(media, 'duration'):
            parts = str(media.duration).split(':')
            if len(parts) == 2:
                duration = int(parts[0]) * 60 + int(parts[1])
            else:
                duration = 180
            
            wait_time = duration + 3
            
            async def auto_next():
                await asyncio.sleep(wait_time)
                if autoplay_status.get(m.chat.id, True):
                    try:
                        await anon.play_next(m.chat.id)
                    except:
                        pass
                timers.pop(m.chat.id, None)
            
            task = asyncio.create_task(auto_next())
            timers[m.chat.id] = task
    except Exception as e:
        print(f"Monitor error: {e}")
