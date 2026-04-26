"""Telegram Bot channel plugin.

Handles inbound messages (polling) and outbound message delivery.
Uses python-telegram-bot library with Application builder (v21+).
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import structlog

from ds_agent.channels.base import (
    BaseChannelPlugin,
    ChannelCapabilities,
    ChannelMeta,
    DeliveryResult,
    InboundMessage,
    OutboundMessage,
)
from ds_agent.tools.path_utils import is_within_workspace

logger = structlog.get_logger()

_MAX_SEND_RETRIES = 3


class TelegramPlugin(BaseChannelPlugin):
    """Telegram Bot API integration using Application builder."""

    def __init__(
        self,
        bot_token: str,
        allow_from: list[str] | None = None,
        workspace_dir: str | None = None,
    ) -> None:
        self._token = bot_token
        self._allow_from = set(allow_from or [])
        self._workspace_dir = (
            None if workspace_dir is None else Path(workspace_dir).expanduser().resolve()
        )
        self._running = False
        self._app: object | None = None
        self._message_queue: asyncio.Queue[InboundMessage] = asyncio.Queue()

    @property
    def meta(self) -> ChannelMeta:
        return ChannelMeta(
            id="telegram",
            name="Telegram",
            description="Telegram Bot API integration",
        )

    @property
    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(
            threads=True,
            media=True,
            markdown=True,
            reactions=True,
            max_message_length=4096,
            streaming=False,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Initialize Application and start internal polling."""
        try:
            from telegram.ext import (
                Application,
                CallbackQueryHandler,
                MessageHandler,
                filters,
            )

            app = Application.builder().token(self._token).build()

            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_text))
            app.add_handler(MessageHandler(filters.COMMAND, self._on_text))
            app.add_handler(CallbackQueryHandler(self._on_callback_query))

            await app.initialize()
            await app.start()
            await app.updater.start_polling(  # type: ignore[union-attr]
                timeout=30,
                allowed_updates=["message", "callback_query"],
            )

            self._app = app
            self._running = True
            logger.info("telegram_started")
        except ImportError:
            logger.error(
                "telegram_import_error",
                hint="Install: pip install python-telegram-bot",
            )
            raise

    async def stop(self) -> None:
        """Stop polling and shut down Application."""
        self._running = False
        if self._app is not None:
            app = self._app
            try:
                await app.updater.stop()  # type: ignore[union-attr]
                await app.stop()  # type: ignore[union-attr]
                await app.shutdown()  # type: ignore[union-attr]
            except Exception:
                logger.debug("telegram_shutdown_error", exc_info=True)
        logger.info("telegram_stopped")

    # ------------------------------------------------------------------
    # Inbound handlers (called by Application's internal polling)
    # ------------------------------------------------------------------

    async def _on_text(self, update: object, context: object) -> None:
        """Handle text messages (including commands)."""
        msg = getattr(update, "message", None)
        if msg is None or not getattr(msg, "text", None):
            return

        from_user = getattr(msg, "from_user", None)
        sender_id = str(from_user.id) if from_user else ""
        text = str(getattr(msg, "text", "") or "")
        is_pairing_message = text.strip().lower().startswith("/pair ")
        if self._allow_from and sender_id not in self._allow_from and not is_pairing_message:
            return

        inbound = InboundMessage(
            channel_id="telegram",
            account_id=self._token.split(":")[0],
            conversation_id=str(msg.chat.id),
            sender_id=sender_id,
            text=msg.text,
            thread_id=(
                str(msg.message_thread_id) if getattr(msg, "message_thread_id", None) else None
            ),
            raw=update.to_dict() if hasattr(update, "to_dict") else {},
        )
        await self._message_queue.put(inbound)

    async def _on_callback_query(self, update: object, context: object) -> None:
        """Handle inline keyboard button presses."""
        query = getattr(update, "callback_query", None)
        if query is None:
            return

        from_user = getattr(query, "from_user", None)
        sender_id = str(from_user.id) if from_user else ""
        if self._allow_from and sender_id not in self._allow_from:
            return

        source_msg = getattr(query, "message", None)
        chat_id = str(source_msg.chat.id) if source_msg else ""
        thread_id = (
            str(source_msg.message_thread_id)
            if source_msg and getattr(source_msg, "message_thread_id", None)
            else None
        )

        inbound = InboundMessage(
            channel_id="telegram",
            account_id=self._token.split(":")[0],
            conversation_id=chat_id,
            sender_id=sender_id,
            text=getattr(query, "data", "") or "",
            thread_id=thread_id,
            raw=update.to_dict() if hasattr(update, "to_dict") else {},
            callback_data=getattr(query, "data", None),
            callback_query_id=str(query.id) if hasattr(query, "id") else None,
            source_message_id=(
                str(source_msg.message_id)
                if source_msg and hasattr(source_msg, "message_id")
                else None
            ),
        )
        await self._message_queue.put(inbound)

    # ------------------------------------------------------------------
    # Outbound: send text
    # ------------------------------------------------------------------

    async def send_text(self, msg: OutboundMessage) -> DeliveryResult:
        """Send text message, auto-chunking for length limit."""
        bot = self._get_bot()
        if bot is None:
            return DeliveryResult(success=False, error="Bot not initialized")

        chunks = self.chunk_text(msg.text)
        last_id = None

        try:
            for chunk in chunks:
                result = await self._send_with_retry(
                    bot.send_message,
                    chat_id=msg.conversation_id,
                    text=chunk,
                    parse_mode="MarkdownV2" if msg.parse_mode == "markdown" else None,
                    reply_to_message_id=self._optional_int(msg.reply_to_id),
                    message_thread_id=self._optional_int(msg.thread_id),
                    reply_markup=self._normalize_reply_markup(getattr(msg, "reply_markup", None)),
                )
                last_id = str(result.message_id)

            return DeliveryResult(success=True, message_id=last_id)

        except Exception as e:
            logger.error("telegram_send_error", error=str(e))
            return DeliveryResult(success=False, error=str(e))

    # ------------------------------------------------------------------
    # Outbound: send file
    # ------------------------------------------------------------------

    async def send_file(
        self,
        conversation_id: str,
        file_path: str,
        *,
        thread_id: str | None = None,
        reply_to_id: str | None = None,
        caption: str | None = None,
    ) -> DeliveryResult:
        """Send a file (plot, report, model).

        Validates that *file_path* is inside the configured workspace
        before sending, preventing path-traversal leakage via Telegram.
        """
        bot = self._get_bot()
        if bot is None:
            return DeliveryResult(success=False, error="Bot not initialized")

        workspace_dir = self._workspace_dir or Path(os.getcwd())
        if not is_within_workspace(Path(file_path), workspace_dir):
            logger.warning("telegram_send_file_blocked", file_path=file_path)
            return DeliveryResult(success=False, error="Access denied: path outside workspace")

        try:
            with open(file_path, "rb") as f:
                result = await self._send_with_retry(
                    bot.send_document,
                    chat_id=conversation_id,
                    document=f,
                    caption=caption,
                    reply_to_message_id=self._optional_int(reply_to_id),
                    message_thread_id=self._optional_int(thread_id),
                )
            return DeliveryResult(success=True, message_id=str(result.message_id))
        except Exception as e:
            return DeliveryResult(success=False, error=str(e))

    # ------------------------------------------------------------------
    # Outbound: callback query and message editing
    # ------------------------------------------------------------------

    async def answer_callback_query(
        self,
        query_id: str,
        text: str | None = None,
        show_alert: bool = False,
    ) -> bool:
        """Acknowledge a callback query (required by Telegram).

        Must be called within a few seconds of receiving the query,
        otherwise the user sees a perpetual loading spinner.
        """
        bot = self._get_bot()
        if bot is None:
            return False
        try:
            await self._send_with_retry(
                bot.answer_callback_query,
                callback_query_id=query_id,
                text=text,
                show_alert=show_alert,
            )
            return True
        except Exception:
            logger.debug("telegram_answer_callback_error", exc_info=True)
            return False

    async def edit_message_text(
        self,
        chat_id: str,
        message_id: str,
        text: str,
        *,
        reply_markup: object | None = None,
        parse_mode: str | None = None,
    ) -> DeliveryResult:
        """Edit a previously sent message's text and optional inline keyboard."""
        bot = self._get_bot()
        if bot is None:
            return DeliveryResult(success=False, error="Bot not initialized")
        try:
            result = await self._send_with_retry(
                bot.edit_message_text,
                chat_id=chat_id,
                message_id=int(message_id),
                text=text,
                reply_markup=self._normalize_reply_markup(reply_markup),
                parse_mode=parse_mode,
            )
            mid = str(result.message_id) if hasattr(result, "message_id") else message_id
            return DeliveryResult(success=True, message_id=mid)
        except Exception as e:
            return DeliveryResult(success=False, error=str(e))

    async def edit_message_reply_markup(
        self,
        chat_id: str,
        message_id: str,
        reply_markup: object | None = None,
    ) -> DeliveryResult:
        """Replace an inline keyboard on a previously sent message."""
        bot = self._get_bot()
        if bot is None:
            return DeliveryResult(success=False, error="Bot not initialized")
        try:
            result = await self._send_with_retry(
                bot.edit_message_reply_markup,
                chat_id=chat_id,
                message_id=int(message_id),
                reply_markup=self._normalize_reply_markup(reply_markup),
            )
            mid = str(result.message_id) if hasattr(result, "message_id") else message_id
            return DeliveryResult(success=True, message_id=mid)
        except Exception as e:
            return DeliveryResult(success=False, error=str(e))

    async def set_my_commands(self, commands: list[tuple[str, str]]) -> bool:
        """Register bot commands visible in the Telegram command menu.

        *commands* is a list of ``(command, description)`` pairs.
        """
        bot = self._get_bot()
        if bot is None:
            return False
        try:
            bot_commands: list[object] = []
            try:
                from telegram import BotCommand

                bot_commands = [BotCommand(cmd, desc) for cmd, desc in commands]
            except ImportError:
                bot_commands = [{"command": cmd, "description": desc} for cmd, desc in commands]
            await self._send_with_retry(bot.set_my_commands, commands=bot_commands)
            return True
        except Exception:
            logger.debug("telegram_set_commands_error", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Queue (contract for TelegramGatewayRunner)
    # ------------------------------------------------------------------

    async def get_next_message(self) -> InboundMessage:
        """Get next inbound message from queue."""
        return await self._message_queue.get()

    async def poll_updates(self) -> None:
        """Keep-alive task. Actual polling is managed by Application internally."""
        while self._running:
            await asyncio.sleep(1)

    # ------------------------------------------------------------------
    # Text chunking
    # ------------------------------------------------------------------

    def chunk_text(self, text: str) -> list[str]:
        """Split text for Telegram while preferring paragraph boundaries."""
        limit = self.capabilities.max_message_length
        if limit <= 0:
            return [text] if text else []
        normalized = text.replace("\r\n", "\n")
        if len(normalized) <= limit:
            return [normalized]

        chunks: list[str] = []
        current = ""
        paragraphs = normalized.split("\n\n")
        for paragraph in paragraphs:
            candidate = paragraph.strip()
            if not candidate:
                continue
            combined = candidate if not current else f"{current}\n\n{candidate}"
            if len(combined) <= limit:
                current = combined
                continue
            if current:
                chunks.append(current)
                current = ""
            if len(candidate) <= limit:
                current = candidate
                continue
            chunks.extend(self._split_long_text(candidate, limit))

        if current:
            chunks.append(current)
        return chunks if chunks else super().chunk_text(normalized)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_bot(self) -> object | None:
        """Return the underlying Bot instance from Application."""
        if self._app is not None and hasattr(self._app, "bot"):
            return self._app.bot  # type: ignore[union-attr]
        return None

    @staticmethod
    async def _send_with_retry(method: object, **kwargs: object) -> object:
        """Call a Bot API method with automatic retry on 429 (flood control).

        Respects Telegram's ``retry_after`` header.
        """
        for attempt in range(_MAX_SEND_RETRIES):
            try:
                return await method(**kwargs)  # type: ignore[operator]
            except Exception as exc:
                retry_after = getattr(exc, "retry_after", None)
                if retry_after is not None and attempt < _MAX_SEND_RETRIES - 1:
                    logger.info(
                        "telegram_rate_limited",
                        retry_after=retry_after,
                        attempt=attempt + 1,
                    )
                    await asyncio.sleep(float(retry_after))
                    continue
                raise
        raise RuntimeError("unreachable")  # pragma: no cover

    @staticmethod
    def _split_long_text(text: str, limit: int) -> list[str]:
        chunks: list[str] = []
        remaining = text.strip()
        while remaining:
            if len(remaining) <= limit:
                chunks.append(remaining)
                break
            split_at = max(
                remaining.rfind("\n", 0, limit),
                remaining.rfind(". ", 0, limit),
                remaining.rfind(" ", 0, limit),
            )
            if split_at <= 0:
                split_at = limit
            elif remaining[split_at : split_at + 2] == ". ":
                split_at += 1
            chunk = remaining[:split_at].rstrip()
            if not chunk:
                chunk = remaining[:limit]
                split_at = limit
            chunks.append(chunk)
            remaining = remaining[split_at:].lstrip()
        return chunks

    @staticmethod
    def _optional_int(value: str | None) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    @staticmethod
    def _normalize_reply_markup(reply_markup: object | None) -> object | None:
        """Convert portable inline-keyboard dicts into Telegram objects when available."""
        if not isinstance(reply_markup, dict):
            return reply_markup

        inline_keyboard = reply_markup.get("inline_keyboard")
        if not isinstance(inline_keyboard, list):
            return reply_markup

        try:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        except ImportError:
            return reply_markup

        rows: list[list[object]] = []
        for row in inline_keyboard:
            if not isinstance(row, list):
                continue
            buttons: list[object] = []
            for item in row:
                if not isinstance(item, dict):
                    continue
                buttons.append(
                    InlineKeyboardButton(
                        text=str(item.get("text", "")),
                        callback_data=(
                            str(item["callback_data"])
                            if item.get("callback_data") is not None
                            else None
                        ),
                    )
                )
            if buttons:
                rows.append(buttons)
        if not rows:
            return None
        return InlineKeyboardMarkup(rows)
