import asyncio
import json
import random
from datetime import datetime, timedelta
from unittest.mock import call
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from db import DB, utc_now_iso
from config import (
    BOT_TOKEN, DB_PATH,
    QUIZ_INTERVAL_HOURS, QUIZ_WINDOW_SECONDS,
    POINTS_PER_CORRECT, ADMIN_IDS
)

CALLBACK_PREFIX = "quiz"  # quiz:<quiz_id>:<choice_index>

db = DB(DB_PATH)
scheduler = AsyncIOScheduler(timezone=ZoneInfo("UTC"))

def is_admin_user(user_id: int) -> bool:
    return (user_id in ADMIN_IDS) if ADMIN_IDS else True  # если список пуст, не ограничиваем

def build_quiz_kb(quiz_id: int, options: list[str]):
    kb = InlineKeyboardBuilder()
    for i, opt in enumerate(options):
        kb.button(text=opt, callback_data=f"{CALLBACK_PREFIX}:{quiz_id}:{i}")
    kb.adjust(1)
    return kb.as_markup()

async def start_quiz_in_chat(bot: Bot, chat_id: int) -> bool:
    if not await db.is_chat_enabled(chat_id):
        return False

    await db.ensure_chat(chat_id)

    active = await db.get_active_quiz(chat_id)
    if active:
        return False

    q = await db.get_random_active_question()
    if not q:
        await bot.send_message(chat_id, "⚠️ Вопросов нет. Добавь вопросы, и я начну викторины.")
        return False

    # варианты + перемешивание
    options = [q.correct, q.wrong1, q.wrong2, q.wrong3]
    random.shuffle(options)
    correct_index = options.index(q.correct)

    # времена окна
    now = datetime.now(tz=ZoneInfo("Europe/Berlin"))  # можно потом читать timezone из chats
    start_at = now
    end_at = now + timedelta(seconds=QUIZ_WINDOW_SECONDS)

    # создаем запись квиза без message_id (пока)
    quiz_id = await db.create_quiz(
        chat_id=chat_id,
        question_id=q.id,
        start_at=start_at.isoformat(),
        end_at=end_at.isoformat(),
        options=options,
        correct_index=correct_index,
        message_id=None,
    )

    text = (
        f"🧠 **Викторина #{quiz_id}**\n\n"
        f"❓ {q.text}\n\n"
        f"⏳ Время: {QUIZ_WINDOW_SECONDS//60} мин\n"
        f"🎯 1 попытка\n"
        f"🏆 +{POINTS_PER_CORRECT} очков за правильный"
    )

    msg = await bot.send_message(chat_id, text, reply_markup=build_quiz_kb(quiz_id, options), parse_mode="Markdown")

    # обновим message_id
    # (простым апдейтом через connect)
    async with db.session() as conn:
        await conn.execute("UPDATE quizzes SET message_id=? WHERE id=?", (msg.message_id, quiz_id))
        await conn.commit()

    await db.log_event(chat_id, "quiz_started", {"quiz_id": quiz_id, "question_id": q.id})

    # запланировать закрытие
    scheduler.add_job(
        close_quiz_job,
        "date",
        run_date=end_at.astimezone(ZoneInfo("UTC")),  # apscheduler лучше в UTC
        args=[bot, chat_id, quiz_id],
        id=f"close:{chat_id}:{quiz_id}",
        replace_existing=True,
    )
    
    return True

async def cmd_dbg(message: Message):
    await message.reply(
        f"DBG\ntext={message.text!r}\nchat_id={message.chat.id}\nuser_id={message.from_user.id}"
    )

async def close_quiz_job(bot: Bot, chat_id: int, quiz_id: int):
    # если уже закрыт — выходим
    active = await db.get_active_quiz(chat_id)
    if not active or int(active["id"]) != quiz_id:
        # мог быть закрыт вручную или заменен
        return

    await db.close_quiz(quiz_id)
    total, correct = await db.count_attempts(quiz_id)

    options = json.loads(active["options_json"])
    correct_idx = int(active["correct_option_index"])
    correct_text = options[correct_idx]

    summary = (
        f"✅ **Викторина #{quiz_id} завершена**\n"
        f"Правильный ответ: **{correct_text}**\n\n"
        f"📊 Ответов: {total}\n"
        f"🎯 Верно: {correct}"
    )

    # попробуем убрать клавиатуру (если сообщение доступно)
    try:
        if active["message_id"]:
            await bot.edit_message_reply_markup(chat_id, int(active["message_id"]), reply_markup=None)
    except Exception:
        pass

    await bot.send_message(chat_id, summary, parse_mode="Markdown")
    await db.log_event(chat_id, "quiz_closed", {"quiz_id": quiz_id, "answers_total": total, "answers_correct": correct})

# --- handlers ---

async def cmd_addpoints(message: Message):
    if not is_admin_user(message.from_user.id):
        return await message.reply("Нет доступа.")

    parts = (message.text or "").split()

    if len(parts) != 3:
        return await message.reply("Формат: /addpoints <user_id> <количество>")

    try:
        target_user_id = int(parts[1])
        delta = int(parts[2])
    except ValueError:
        return await message.reply("user_id и количество должны быть числами.")

    await db.add_points(message.chat.id, target_user_id, delta)
    await message.reply(f"✅ Пользователю {target_user_id} добавлено {delta} очков.")

async def cmd_start(message: Message):
    if message.chat.type in ("group", "supergroup"):
        await db.ensure_chat(message.chat.id)
        await message.reply("Готово. Викторины будут выходить по расписанию. Команды: !очки, !топ, /pause, /resume")
    else:
        await message.reply("Добавь меня в группу и сделай админом (желательно), чтобы я мог проводить викторины.")

async def cmd_pause(message: Message):
    if not is_admin_user(message.from_user.id):
        return await message.reply("Нет доступа.")
    await db.set_chat_enabled(message.chat.id, False)
    await message.reply("⏸ Викторины поставлены на паузу.")

async def cmd_resume(message: Message):
    if not is_admin_user(message.from_user.id):
        return await message.reply("Нет доступа.")
    await db.set_chat_enabled(message.chat.id, True)
    await message.reply("▶️ Викторины включены.")

async def cmd_addq(message: Message):
    """
    Формат:
    /addq Вопрос? | Правильный | Неправ1 | Неправ2 | Неправ3
    """
    if not is_admin_user(message.from_user.id):
        return await message.reply("Нет доступа.")

    text = message.text or ""
    payload = text.split(" ", 1)
    if len(payload) < 2 or "|" not in payload[1]:
        return await message.reply(
            "Формат:\n/addq Вопрос? | Правильный | Неправ1 | Неправ2 | Неправ3"
        )

    parts = [p.strip() for p in payload[1].split("|")]
    if len(parts) != 5 or any(not p for p in parts):
        return await message.reply("Нужно ровно 5 частей через |")

    qid = await db.add_question(parts[0], parts[1], parts[2], parts[3], parts[4])
    await message.reply(f"✅ Добавлен вопрос #{qid}")

async def cmd_import(message: Message):
    """
    /import data/questions.json
    (файл должен быть на сервере; для MVP так)
    """
    if not is_admin_user(message.from_user.id):
        return await message.reply("Нет доступа.")

    payload = (message.text or "").split(" ", 1)
    if len(payload) < 2:
        return await message.reply("Формат: /import data/questions.json")

    path = payload[1].strip()
    try:
        added = await db.import_questions_json(path)
        await message.reply(f"✅ Импортировано вопросов: {added}")
    except Exception as e:
        await message.reply(f"⚠️ Ошибка импорта: {e}")

async def cmd_points(message: Message):
    pts = await db.get_points(message.chat.id, message.from_user.id)
    await message.reply(f"🏅 У тебя {pts} очков")

def _md_escape(s: str) -> str:
    # Markdown (не V2)
    return (
        s.replace("\\", "\\\\")
         .replace("_", "\\_")
         .replace("*", "\\*")
         .replace("`", "\\`")
    )

def _format_name(user: dict | None, uid: int) -> str:
    if user:
        if user.get("username"):
            return f"@{user['username']}"
        if user.get("full_name"):
            return user["full_name"]
    return str(uid)

async def cmd_top(message: Message):
    chat_id = message.chat.id
    top = await db.get_top(chat_id, limit=10)
    if not top:
        return await message.reply("Пока нет очков.")

    lines = ["🏆 *Топ-10*"]
    for i, (uid, pts) in enumerate(top, start=1):
        user = await db.get_user(uid)  # ✅ добавим в db.py
        name = _md_escape(_format_name(user, uid))
        lines.append(f"{i}. {name} — *{pts}*")

    await message.reply("\n".join(lines), parse_mode="Markdown")

async def on_answer(call: CallbackQuery, bot: Bot):
    data = call.data or ""
    try:
        _, quiz_id_s, choice_s = data.split(":")
        quiz_id = int(quiz_id_s)
        choice = int(choice_s)
    except Exception:
        return await call.answer("Некорректно.", show_alert=False)

    chat_id = call.message.chat.id
    user_id = call.from_user.id
    # ✅ сохраняем отображаемое имя пользователя для топа
    u = call.from_user
    await db.upsert_user(
    user_id=user_id,
    username=u.username,      # может быть None
    full_name=u.full_name     # обычно есть
)


    active = await db.get_active_quiz(chat_id)
    if not active or int(active["id"]) != quiz_id:
        return await call.answer("Этот квиз уже завершён.", show_alert=False)

    # проверим окно времени (на всякий)
    end_at = datetime.fromisoformat(active["end_at"])
    now = datetime.now(tz=end_at.tzinfo)
    if now > end_at:
        return await call.answer("Время вышло.", show_alert=False)

    correct_idx = int(active["correct_option_index"])
    is_correct = (choice == correct_idx)

    inserted = await db.record_attempt(quiz_id, chat_id, user_id, choice, is_correct)
    if not inserted:
        return await call.answer("У тебя уже была попытка.", show_alert=False)

    if is_correct:
        await db.add_points(chat_id, user_id, POINTS_PER_CORRECT)
        await db.log_event(chat_id, "answer", {"quiz_id": quiz_id, "user_id": user_id, "correct": True})
        return await call.answer(f"✅ Верно! +{POINTS_PER_CORRECT}", show_alert=False)
    else:
        await db.log_event(chat_id, "answer", {"quiz_id": quiz_id, "user_id": user_id, "correct": False})
        return await call.answer("❌ Неверно.", show_alert=False)

# --- scheduler setup ---

async def schedule_quizzes(bot: Bot, chat_id: int):
    """
    Каждый 2 часа ровно. Для MVP: стартуем циклическую задачу interval.
    Важно: "ровно по часам" лучше делать cron (0 минут, каждый 2-й час).
    """
    # cron: на 00 минут каждого 2-го часа
    scheduler.add_job(
        start_quiz_in_chat,
        "cron",
        minute=0,
        hour="*",
        args=[bot, chat_id],
        id=f"cron_quiz:{chat_id}",
        replace_existing=True,
    )

async def cmd_next(message: Message, bot: Bot):
    if not is_admin_user(message.from_user.id):
        return await message.reply("Нет доступа.")

    chat_id = message.chat.id
    active = await db.get_active_quiz(chat_id)
    if active:
        return await message.reply("Сейчас уже идёт активный квиз. Используй /next_force чтобы закрыть и запустить новый.")

    started = await start_quiz_in_chat(bot, chat_id)
    if started:
        await message.reply("✅ Запустил следующий вопрос.")
    else:
        await message.reply("⚠️ Не удалось запустить: проверь, что в базе есть активные вопросы.")


async def cmd_next_force(message: Message, bot: Bot):
    if not is_admin_user(message.from_user.id):
        return await message.reply("Нет доступа.")

    chat_id = message.chat.id
    active = await db.get_active_quiz(chat_id)

    if active:
        quiz_id = int(active["id"])
        try:
            scheduler.remove_job(f"close:{chat_id}:{quiz_id}")
        except Exception:
            pass
        await close_quiz_job(bot, chat_id, quiz_id)

    started = await start_quiz_in_chat(bot, chat_id)
    if started:
        await message.reply("✅ Закрыл текущий и запустил следующий вопрос.")
    else:
        await message.reply("⚠️ Закрыл текущий, но новый не запустился: в базе нет активных вопросов.")



async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан. Добавь в .env")

    await db.init()

    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()
    
    dp.message.register(cmd_start, Command("start_q"))
    dp.message.register(cmd_pause, Command("pause"))
    dp.message.register(cmd_resume, Command("resume"))
    dp.message.register(cmd_addq, Command("addq"))
    dp.message.register(cmd_import, Command("import"))
    dp.message.register(cmd_next, Command("next"))
    dp.message.register(cmd_next_force, Command("next_force"))
    dp.message.register(cmd_addpoints, Command("addpoints"))
    dp.message.register(cmd_dbg, Command("dbg"))


    # “пользовательские” команды через префикс ! (обычно так в чатах удобнее)
    dp.message.register(cmd_points, F.text.in_({"!очки", "!points"}))
    dp.message.register(cmd_top, F.text.in_({"!топ", "!top"}))

    dp.callback_query.register(on_answer, F.data.startswith(f"{CALLBACK_PREFIX}:"))
    
    scheduler.start()

    # MVP: расписание на один чат создаём после /start в группе.
    # Но чтобы “само” работало, можно при старте пробежать chats из БД и поставить cron на каждый.
    async with db.session() as conn:
        rows = await (await conn.execute("SELECT chat_id FROM chats WHERE is_enabled=1")).fetchall()
        for r in rows:
            await schedule_quizzes(bot, int(r["chat_id"]))

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
