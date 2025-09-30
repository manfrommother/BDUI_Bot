import os
import json
import random
import logging
from datetime import time, timedelta
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from pytz import timezone
from telegram import Update, User, ChatMemberUpdated
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    ChatMemberHandler,
    filters,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
TZ = os.getenv("TZ", "Europe/Moscow")

STATE_FILE = os.getenv("STATE_FILE", "state.json")

# Ссылка на дейлик (можно переопределить переменной окружения DAILY_LINK)
DAILY_LINK = os.getenv(
    "DAILY_LINK",
    "https://x5group.ktalk.ru/23a64c1ee4e4443cbe66c80fd7326727",
)


# --------------- State helpers ---------------

def _default_state() -> Dict[str, Any]:
    return {"chat_id": None, "participants": [], "known_users": {}}


def _read_state() -> Dict[str, Any]:
    if not os.path.exists(STATE_FILE):
        return _default_state()
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # обеспечить новые поля по умолчанию
            if "known_users" not in data:
                data["known_users"] = {}
            if "participants" not in data:
                data["participants"] = []
            if "chat_id" not in data:
                data["chat_id"] = None
            return data
    except Exception as exc:
        logger.warning("Failed to read state file: %s", exc)
        return _default_state()


def _write_state(state: Dict[str, Any]) -> None:
    try:
        dir_name = os.path.dirname(STATE_FILE)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.error("Failed to write state file: %s", exc)


def _get_display_name(user: Optional[User], fallback: Optional[str] = None) -> str:
    if user and user.username:
        return f"@{user.username}"
    if user and (user.full_name or user.first_name):
        return user.full_name or user.first_name
    return fallback or "неизвестный"


# --------------- Parsing helpers ---------------

def _normalize_name(arg: str) -> str:
    arg = arg.strip()
    if not arg:
        return arg
    if arg.startswith("@"):  # оставить как есть
        return arg
    return arg


def _name_key(name: str) -> str:
    # Ключ для сравнения: без @ и регистронезависимый
    return _normalize_name(name).lstrip("@").strip().casefold()


def _parse_names(args_text: str) -> List[str]:
    # Разделители: запятая, точка с запятой, перевод строки, таб, и несколько пробелов
    raw = args_text.replace("\n", ",").replace(";", ",")
    parts = []
    for chunk in raw.split(","):
        sub = [p for p in chunk.strip().split() if p]
        if not sub and chunk.strip():
            parts.append(chunk.strip())
        else:
            parts.extend(sub)
    names = []
    seen = set()
    for p in parts:
        n = _normalize_name(p)
        if not n:
            continue
        key = _name_key(n)
        if key in seen:
            continue
        seen.add(key)
        names.append(n)
    return names


# --------------- Known users tracking ---------------

def _remember_user(state: Dict[str, Any], chat_id: int, user: Optional[User]) -> None:
    if user is None:
        return
    known: Dict[str, Dict[str, str]] = state.get("known_users", {})
    chat_key = str(chat_id)
    if chat_key not in known:
        known[chat_key] = {}
    display = _get_display_name(user)
    known[chat_key][str(user.id)] = display
    state["known_users"] = known


async def _track_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat and update.effective_user:
        state = _read_state()
        _remember_user(state, update.effective_chat.id, update.effective_user)
        _write_state(state)


async def _track_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not isinstance(update.my_chat_member, ChatMemberUpdated) and not isinstance(update.chat_member, ChatMemberUpdated):
        return
    cmu: Optional[ChatMemberUpdated] = update.my_chat_member or update.chat_member
    if cmu and cmu.chat and cmu.from_user:
        state = _read_state()
        _remember_user(state, cmu.chat.id, cmu.from_user)
        if cmu.new_chat_member and cmu.new_chat_member.user:
            _remember_user(state, cmu.chat.id, cmu.new_chat_member.user)
        _write_state(state)


# --------------- Commands ---------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg:
        await msg.reply_text(
            "Привет! Я выберу случайного ведущего дейли по будням в 10:00.\n"
            "Команды: /setchat, /add, /remove, /list, /today, /chatid, /testjob, /addall"
        )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg:
        await msg.reply_text(
            "/setchat — зафиксировать текущий чат для рассылки\n"
            "/add @username | Имя — добавить участника (поддерживается список)\n"
            "/remove @username | Имя — удалить участника (поддерживается список)\n"
            "/list — показать пул участников\n"
            "/today — выбрать ведущего сейчас\n"
            "/chatid — показать ID текущего чата\n"
            "/testjob [сек] — тест: запустить анонс через N секунд (по умолчанию 5)\n"
            "/addall — добавить в пул всех известных участников чата"
        )


async def chatid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if update.effective_chat is None or msg is None:
        return
    await msg.reply_text(f"Chat ID: {update.effective_chat.id}")


async def setchat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if update.effective_chat is None or msg is None:
        return
    state = _read_state()
    state["chat_id"] = update.effective_chat.id
    _write_state(state)
    await msg.reply_text(
        f"Чат установлен: {update.effective_chat.title or update.effective_chat.id}"
    )


async def add_participant(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg is None:
        return
    state = _read_state()
    args_text = (" ".join(context.args)).strip() if context.args else ""
    if not args_text:
        if update.effective_user:
            names = [_get_display_name(update.effective_user)]
        else:
            await msg.reply_text("Укажите @username или имя(имена).")
            return
    else:
        names = _parse_names(args_text)
        if not names:
            await msg.reply_text("Не удалось распознать имена. Укажите через запятую/перенос строки.")
            return

    participants: List[str] = state.get("participants", [])

    added: List[str] = []
    skipped: List[str] = []

    existing_keys = {_name_key(p) for p in participants}

    for name in names:
        key = _name_key(name)
        if key in existing_keys:
            skipped.append(name)
            continue
        participants.append(name)
        existing_keys.add(key)
        added.append(name)

    state["participants"] = participants
    _write_state(state)

    parts = []
    if added:
        parts.append("Добавлены: " + ", ".join(added))
    if skipped:
        parts.append("Уже были: " + ", ".join(skipped))
    if not parts:
        parts.append("Ничего не добавлено.")
    await msg.reply_text("\n".join(parts))


async def add_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    if msg is None or chat is None:
        return
    state = _read_state()
    known = state.get("known_users", {}).get(str(chat.id), {})
    if not known:
        await msg.reply_text("Пока не знаю участников этого чата. Напишите что-нибудь, чтобы я запомнил.")
        return

    names = list(known.values())

    participants: List[str] = state.get("participants", [])
    existing_keys = {_name_key(p) for p in participants}

    added: List[str] = []
    for display in names:
        key = _name_key(display)
        if key in existing_keys:
            continue
        participants.append(display)
        existing_keys.add(key)
        added.append(display)

    state["participants"] = participants
    _write_state(state)

    if added:
        await msg.reply_text("Добавлены: " + ", ".join(added))
    else:
        await msg.reply_text("Все известные участники уже в списке.")


async def remove_participant(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg is None:
        return
    state = _read_state()
    if not context.args:
        await msg.reply_text("Укажите @username или имя(имена) для удаления.")
        return

    names = _parse_names(" ".join(context.args))
    if not names:
        await msg.reply_text("Не удалось распознать имена.")
        return

    participants: List[str] = state.get("participants", [])

    removed: List[str] = []
    not_found: List[str] = []

    participant_keys = [_name_key(p) for p in participants]

    for name in names:
        key = _name_key(name)
        if key in participant_keys:
            participants = [p for p in participants if _name_key(p) != key]
            removed.append(name)
            participant_keys = [_name_key(p) for p in participants]
        else:
            not_found.append(name)

    state["participants"] = participants
    _write_state(state)

    parts = []
    if removed:
        parts.append("Удалены: " + ", ".join(removed))
    if not_found:
        parts.append("Не найдены: " + ", ".join(not_found))
    if not parts:
        parts.append("Ничего не изменилось.")
    await msg.reply_text("\n".join(parts))


async def list_participants(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg is None:
        return
    state = _read_state()
    participants: List[str] = state.get("participants", [])
    if not participants:
        await msg.reply_text("Список участников пуст. Добавьте через /add.")
        return
    text = "\n".join(f"• {p}" for p in participants)
    await msg.reply_text(f"Текущий список:\n{text}")


def _choose_random_participant(participants: List[str]) -> Optional[str]:
    if not participants:
        return None
    return random.choice(participants)


async def _announce_today(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    state = _read_state()
    participants: List[str] = state.get("participants", [])
    chosen = _choose_random_participant(participants)
    if not chosen:
        await context.bot.send_message(chat_id=chat_id, text="Список участников пуст. Добавьте через /add.")
        return
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"Сегодня дейли проводит: {chosen}\n"
            f"Подключиться: <a href=\"{DAILY_LINK}\">ссылка</a>"
        ),
        parse_mode=ParseMode.HTML,
        disable_notification=False,
    )


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    state = _read_state()
    chat_id = state.get("chat_id") or (update.effective_chat.id if update.effective_chat else None)
    if not chat_id:
        if msg:
            await msg.reply_text("Сначала выполните /setchat в нужном чате.")
        return
    await _announce_today(context, chat_id)


async def testjob(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    state = _read_state()
    chat_id = state.get("chat_id") or (update.effective_chat.id if update.effective_chat else None)
    if not chat_id:
        if msg:
            await msg.reply_text("Сначала выполните /setchat в нужном чате.")
        return
    try:
        delay = int(context.args[0]) if context.args else 5
        delay = max(1, min(delay, 3600))
    except Exception:
        delay = 5
    when = timedelta(seconds=delay)

    async def one_off(context_: ContextTypes.DEFAULT_TYPE) -> None:
        await _announce_today(context_, chat_id)

    if context.job_queue is None:
        if msg:
            await msg.reply_text("JobQueue не инициализирован. Проверьте установку зависимостей.")
        return

    context.job_queue.run_once(one_off, when=when, name=f"testjob-{chat_id}")
    if msg:
        await msg.reply_text(f"Тестовая задача запланирована через {delay} сек.")


# --------------- Scheduler job ---------------

async def daily_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    state = _read_state()
    chat_id = state.get("chat_id")
    if not chat_id:
        logger.info("Skip daily job: chat_id not set")
        return
    await _announce_today(context, chat_id)


def _setup_schedule(app: Application) -> None:
    tz = timezone(TZ)
    # В python-telegram-bot: 0=Monday, 1=Tuesday, ..., 6=Sunday
    # Выбираем будни: понедельник-пятница (0,1,2,3,4)
    app.job_queue.run_daily(
        callback=daily_job,
        time=time(hour=10, minute=0, tzinfo=tz),
        days=(0, 1, 2, 3, 4),  # Monday to Friday
        name="daily-standup",
    )
    logger.info("Scheduled daily job at 10:00 %s on weekdays (Mon-Fri)", TZ)


# --------------- Error handler ---------------

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled exception", exc_info=context.error)


# --------------- Main ---------------

def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан. Укажите его в .env или переменных окружения.")

    app = Application.builder().token(BOT_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("chatid", chatid))
    app.add_handler(CommandHandler("setchat", setchat))
    app.add_handler(CommandHandler("add", add_participant))
    app.add_handler(CommandHandler("addall", add_all))
    app.add_handler(CommandHandler("remove", remove_participant))
    app.add_handler(CommandHandler("list", list_participants))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("testjob", testjob))

    # Трекинг участников
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, _track_message))
    app.add_handler(ChatMemberHandler(_track_chat_member, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(ChatMemberHandler(_track_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))

    _setup_schedule(app)

    app.add_error_handler(error_handler)

    logger.info("Bot is starting...")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
