# Copyright (c) 2025 TheHamkerAlone
# Licensed under the MIT License.
# This file is part of AloneXMusic
# ALONE-CODER

from ntgcalls import (ConnectionNotFound, TelegramServerError,
                      RTMPStreamingUnsupported)
from pyrogram.errors import MessageIdInvalid
from pyrogram.types import InputMediaPhoto, Message
from pytgcalls import PyTgCalls, exceptions, types
from pytgcalls.pytgcalls_session import PyTgCallsSession

from AloneX import app, config, db, lang, logger, queue, userbot, yt
from AloneX.helpers import Media, Track, buttons, thumb


class TgCall(PyTgCalls):
    def __init__(self):
        super().__init__(app)  # ✅ Pass app instance to parent class
        self.clients = []

    async def pause(self, chat_id: int) -> bool:
        """Pause the current playback"""
        client = await db.get_assistant(chat_id)
        await db.playing(chat_id, paused=True)
        return await client.pause(chat_id)

    async def resume(self, chat_id: int) -> bool:
        """Resume the current playback"""
        client = await db.get_assistant(chat_id)
        await db.playing(chat_id, paused=False)
        return await client.resume(chat_id)

    async def stop(self, chat_id: int) -> None:
        """Stop playback and clear queue"""
        client = await db.get_assistant(chat_id)
        try:
            queue.clear(chat_id)
            await db.remove_call(chat_id)
        except Exception as e:
            logger.error(f"Error in stop queue cleanup: {e}")
            pass

        try:
            if client:
                await client.leave_call(chat_id, close=False)
        except Exception as e:
            logger.error(f"Error leaving call: {e}")
            pass

    async def play_media(
        self,
        chat_id: int,
        message: Message,
        media: Media | Track,
        seek_time: int = 0,
    ) -> None:
        """Play media in voice chat"""
        client = await db.get_assistant(chat_id)
        _lang = await lang.get_lang(chat_id)
        _thumb = (
            await thumb.generate(media)
            if isinstance(media, Track)
            else config.DEFAULT_THUMB
        )

        if not media.file_path:
            await message.edit_text(_lang["error_no_file"].format(config.SUPPORT_CHAT))
            return await self.play_next(chat_id)

        stream = types.MediaStream(
            media_path=media.file_path,
            audio_parameters=types.AudioQuality.HIGH,
            video_parameters=types.VideoQuality.HD_720p,
            audio_flags=types.MediaStream.Flags.REQUIRED,
            video_flags=(
                types.MediaStream.Flags.AUTO_DETECT
                if media.video
                else types.MediaStream.Flags.IGNORE
            ),
            ffmpeg_parameters=f"-ss {seek_time}" if seek_time > 1 else None,
        )
        
        try:
            await client.play(
                chat_id=chat_id,
                stream=stream,
                config=types.GroupCallConfig(auto_start=False),
            )
            
            if not seek_time:
                media.time = 1
                await db.add_call(chat_id)
                text = _lang["play_media"].format(
                    media.url,
                    media.title,
                    media.duration,
                    media.user,
                )
                keyboard = buttons.controls(chat_id)
                
                try:
                    await message.edit_media(
                        media=InputMediaPhoto(
                            media=_thumb,
                            caption=text,
                        ),
                        reply_markup=keyboard,
                    )
                except MessageIdInvalid:
                    media.message_id = (await app.send_photo(
                        chat_id=chat_id,
                        photo=_thumb,
                        caption=text,
                        reply_markup=keyboard,
                    )).id
                    
        except FileNotFoundError:
            await message.edit_text(_lang["error_no_file"].format(config.SUPPORT_CHAT))
            await self.play_next(chat_id)
            
        except exceptions.NoActiveGroupCall:
            await self.stop(chat_id)
            await message.edit_text(_lang["error_no_call"])
            
        except exceptions.NoAudioSourceFound:
            await message.edit_text(_lang["error_no_audio"])
            await self.play_next(chat_id)
            
        except (ConnectionNotFound, TelegramServerError):
            await self.stop(chat_id)
            await message.edit_text(_lang["error_tg_server"])
            
        except RTMPStreamingUnsupported:
            await self.stop(chat_id)
            await message.edit_text(_lang["error_rtmp"])
            
        except Exception as e:
            logger.error(f"Unexpected error in play_media: {e}")
            await self.stop(chat_id)
            await message.edit_text(_lang["error_unknown"].format(str(e)))

    async def replay(self, chat_id: int) -> None:
        """Replay the current track"""
        if not await db.get_call(chat_id):
            return

        media = queue.get_current(chat_id)
        if not media:
            return
            
        _lang = await lang.get_lang(chat_id)
        msg = await app.send_message(chat_id=chat_id, text=_lang["play_again"])
        await self.play_media(chat_id, msg, media)

    async def play_next(self, chat_id: int) -> None:
        """Play the next track in queue"""
        media = queue.get_next(chat_id)
        
        try:
            if media and media.message_id:
                await app.delete_messages(
                    chat_id=chat_id,
                    message_ids=media.message_id,
                    revoke=True,
                )
                media.message_id = 0
        except Exception as e:
            logger.error(f"Error deleting message in play_next: {e}")
            pass

        if not media:
            return await self.stop(chat_id)

        _lang = await lang.get_lang(chat_id)
        msg = await app.send_message(chat_id=chat_id, text=_lang["play_next"])
        
        if not media.file_path:
            media.file_path = await yt.download(media.id, video=media.video)
            if not media.file_path:
                await self.stop(chat_id)
                return await msg.edit_text(
                    _lang["error_no_file"].format(config.SUPPORT_CHAT)
                )

        media.message_id = msg.id
        await self.play_media(chat_id, msg, media)

    async def ping(self) -> float:
        """Get average ping of all clients"""
        if not self.clients:
            return 0.0
        try:
            pings = [await client.ping() for client in self.clients if client]
            return round(sum(pings) / len(pings), 2) if pings else 0.0
        except Exception as e:
            logger.error(f"Error in ping: {e}")
            return 0.0

    async def decorators(self, client: PyTgCalls) -> None:
        """Register event handlers for a client"""
        
        @client.on_stream_end()
        async def stream_end_handler(_, update: types.StreamEnded) -> None:
            """Handle stream ended event"""
            try:
                if update.stream_type in [types.StreamEnded.Type.AUDIO, types.StreamEnded.Type.VIDEO]:
                    await self.play_next(update.chat_id)
            except Exception as e:
                logger.error(f"Error in stream_end_handler: {e}")

        @client.on_kicked()
        async def kicked_handler(_, chat_id: int) -> None:
            """Handle kicked from group event"""
            try:
                await self.stop(chat_id)
            except Exception as e:
                logger.error(f"Error in kicked_handler: {e}")

        @client.on_closed_voice_chat()
        async def closed_voice_chat_handler(_, chat_id: int) -> None:
            """Handle voice chat closed event"""
            try:
                await self.stop(chat_id)
            except Exception as e:
                logger.error(f"Error in closed_voice_chat_handler: {e}")

    async def boot(self) -> None:
        """Initialize and start all PyTgCalls clients"""
        PyTgCallsSession.notice_displayed = True
        
        for ub in userbot.clients:
            try:
                client = PyTgCalls(ub, cache_duration=100)
                await client.start()
                self.clients.append(client)
                await self.decorators(client)
                logger.info(f"PyTgCalls client started for user: {ub.me.username}")
            except Exception as e:
                logger.error(f"Error starting client: {e}")
                continue
                
        logger.info(f"PyTgCalls client(s) started. Total: {len(self.clients)}")
