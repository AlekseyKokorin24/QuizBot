import json
import aiosqlite
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import AsyncIterator

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass
class Question:
    id: int
    text: str
    correct: str
    wrong1: str
    wrong2: str
    wrong3: str
    category: str = "general"
    difficulty: int = 1
    active: int = 1

class DB:
    def __init__(self, path: str = "quizbot.sqlite3"):
        self.path = path

    @asynccontextmanager
    async def session(self) -> AsyncIterator[aiosqlite.Connection]:
        db = await aiosqlite.connect(self.path)
        try:
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA foreign_keys = ON;")
            yield db
        finally:
            await db.close()

    async def init(self) -> None:
        async with self.session() as db:
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS chats (
                    chat_id INTEGER PRIMARY KEY,
                    timezone TEXT NOT NULL DEFAULT 'Asia/Krasnoyarsk',
                    is_enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    correct TEXT NOT NULL,
                    wrong1 TEXT NOT NULL,
                    wrong2 TEXT NOT NULL,
                    wrong3 TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'general',
                    difficulty INTEGER NOT NULL DEFAULT 1,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS quizzes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    question_id INTEGER NOT NULL,
                    start_at TEXT NOT NULL,
                    end_at TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('active','closed')),
                    message_id INTEGER,
                    correct_option_index INTEGER,   -- 0..3 (после перемешивания)
                    options_json TEXT,              -- ["...","...","...","..."]
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(chat_id) REFERENCES chats(chat_id) ON DELETE CASCADE,
                    FOREIGN KEY(question_id) REFERENCES questions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    quiz_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    chosen_index INTEGER NOT NULL,  -- 0..3
                    is_correct INTEGER NOT NULL,     -- 0/1
                    created_at TEXT NOT NULL,
                    UNIQUE(quiz_id, user_id),
                    FOREIGN KEY(quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS scores (
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    points INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(chat_id, user_id)
                );
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
                
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    payload TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_questions_active ON questions(active);
                CREATE INDEX IF NOT EXISTS idx_quizzes_chat_status ON quizzes(chat_id, status);
                """
            )
            await db.commit()

    async def ensure_chat(self, chat_id: int, timezone_str: str = "Asia/Krasnoyarsk") -> None:
        async with self.session() as db:
            await db.execute(
                "INSERT OR IGNORE INTO chats(chat_id, timezone, is_enabled, created_at) VALUES(?,?,1,?)",
                (chat_id, timezone_str, utc_now_iso()),
            )
            await db.commit()

    async def set_chat_enabled(self, chat_id: int, enabled: bool) -> None:
        async with self.session() as db:
            await db.execute(
                "UPDATE chats SET is_enabled=? WHERE chat_id=?",
                (1 if enabled else 0, chat_id),
            )
            await db.commit()

    async def is_chat_enabled(self, chat_id: int) -> bool:
        async with self.session() as db:
            cur = await db.execute("SELECT is_enabled FROM chats WHERE chat_id=?", (chat_id,))
            row = await cur.fetchone()
            return bool(row["is_enabled"]) if row else True

    async def add_question(self, text: str, correct: str, wrong1: str, wrong2: str, wrong3: str,
                           category: str = "general", difficulty: int = 1) -> int:
        async with self.session() as db:
            cur = await db.execute(
                """
                INSERT INTO questions(text, correct, wrong1, wrong2, wrong3, category, difficulty, active, created_at)
                VALUES(?,?,?,?,?,?,?,1,?)
                """,
                (text, correct, wrong1, wrong2, wrong3, category, difficulty, utc_now_iso()),
            )
            await db.commit()
            return int(cur.lastrowid)

    async def import_questions_json(self, json_path: str) -> int:
        """
        JSON формат:
        [
          {"text":"...", "correct":"...", "wrong":["...","...","..."], "category":"general", "difficulty":1},
          ...
        ]
        """
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        added = 0
        async with self.session() as db:
            for item in data:
                wrong = item["wrong"]
                await db.execute(
                    """
                    INSERT INTO questions(text, correct, wrong1, wrong2, wrong3, category, difficulty, active, created_at)
                    VALUES(?,?,?,?,?,?,?,1,?)
                    """,
                    (
                        item["text"],
                        item["correct"],
                        wrong[0], wrong[1], wrong[2],
                        item.get("category", "general"),
                        int(item.get("difficulty", 1)),
                        utc_now_iso(),
                    ),
                )
                added += 1
            await db.commit()
        return added

    async def get_random_active_question(self) -> Optional[Question]:
        async with self.session() as db:
            cur = await db.execute(
                """
                SELECT * FROM questions
                WHERE active=1
                ORDER BY RANDOM()
                LIMIT 1
                """
            )
            row = await cur.fetchone()
            if not row:
                return None
            return Question(
                id=row["id"],
                text=row["text"],
                correct=row["correct"],
                wrong1=row["wrong1"],
                wrong2=row["wrong2"],
                wrong3=row["wrong3"],
                category=row["category"],
                difficulty=row["difficulty"],
                active=row["active"],
            )
            
    async def create_quiz(self, chat_id: int, question_id: int, start_at: str, end_at: str,
                          options: List[str], correct_index: int, message_id: Optional[int]) -> int:
        async with self.session() as db:
            cur = await db.execute(
                """
                INSERT INTO quizzes(chat_id, question_id, start_at, end_at, status, message_id,
                                    correct_option_index, options_json, created_at)
                VALUES(?,?,?,?, 'active', ?, ?, ?, ?)
                """,
                (chat_id, question_id, start_at, end_at, message_id, correct_index, json.dumps(options, ensure_ascii=False), utc_now_iso()),
            )
            await db.commit()
            return int(cur.lastrowid)

    async def close_quiz(self, quiz_id: int) -> None:
        async with self.session() as db:
            await db.execute("UPDATE quizzes SET status='closed' WHERE id=?", (quiz_id,))
            await db.commit()

    async def get_active_quiz(self, chat_id: int) -> Optional[aiosqlite.Row]:
        async with self.session() as db:
            cur = await db.execute(
                "SELECT * FROM quizzes WHERE chat_id=? AND status='active' ORDER BY id DESC LIMIT 1",
                (chat_id,),
            )
            return await cur.fetchone()

    async def record_attempt(self, quiz_id: int, chat_id: int, user_id: int, chosen_index: int, is_correct: bool) -> bool:
        """
        Возвращает True если попытка записана, False если попытка уже была (UNIQUE).
        """
        async with self.session() as db:
            try:
                await db.execute(
                    """
                    INSERT INTO attempts(quiz_id, chat_id, user_id, chosen_index, is_correct, created_at)
                    VALUES(?,?,?,?,?,?)
                    """,
                    (quiz_id, chat_id, user_id, chosen_index, 1 if is_correct else 0, utc_now_iso()),
                )
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                return False

    async def add_points(self, chat_id: int, user_id: int, delta: int) -> None:
        async with self.session() as db:
            await db.execute(
                """
                INSERT INTO scores(chat_id, user_id, points, updated_at)
                VALUES(?,?,?,?)
                ON CONFLICT(chat_id, user_id) DO UPDATE SET
                    points = points + excluded.points,
                    updated_at = excluded.updated_at
                """,
                (chat_id, user_id, delta, utc_now_iso()),
            )
            await db.commit()

    async def get_points(self, chat_id: int, user_id: int) -> int:
        async with self.session() as db:
            cur = await db.execute("SELECT points FROM scores WHERE chat_id=? AND user_id=?", (chat_id, user_id))
            row = await cur.fetchone()
            return int(row["points"]) if row else 0

    async def get_top(self, chat_id: int, limit: int = 10) -> List[Tuple[int, int]]:
        async with self.session() as db:
            cur = await db.execute(
                "SELECT user_id, points FROM scores WHERE chat_id=? ORDER BY points DESC LIMIT ?",
                (chat_id, limit),
            )
            rows = await cur.fetchall()
            return [(int(r["user_id"]), int(r["points"])) for r in rows]

    async def upsert_user(self, user_id: int, username: str | None, full_name: str | None) -> None:
        async with self.session() as db:
            await db.execute(
                """
                INSERT INTO users(user_id, username, full_name, updated_at)
                VALUES(?,?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    full_name = excluded.full_name,
                    updated_at = excluded.updated_at
                """,
                (user_id, username, full_name, utc_now_iso()),
            )
            await db.commit()

    async def get_user(self, user_id: int) -> dict | None:
        async with self.session() as db:
            cur = await db.execute(
                "SELECT username, full_name FROM users WHERE user_id=?",
                (user_id,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            return {"username": row["username"], "full_name": row["full_name"]}


    async def count_attempts(self, quiz_id: int) -> Tuple[int, int]:
        async with self.session() as db:
            cur = await db.execute(

                "SELECT COUNT(*) AS total, SUM(is_correct) AS correct FROM attempts WHERE quiz_id=?",
                (quiz_id,),
            )
            row = await cur.fetchone()
            total = int(row["total"]) if row and row["total"] is not None else 0
            correct = int(row["correct"]) if row and row["correct"] is not None else 0
            return total, correct

    async def log_event(self, chat_id: int, typ: str, payload: Dict[str, Any] | None = None) -> None:
        async with self.session() as db:
            await db.execute(
                "INSERT INTO events(chat_id, type, payload, created_at) VALUES(?,?,?,?)",
                (chat_id, typ, json.dumps(payload, ensure_ascii=False) if payload else None, utc_now_iso()),
            )
            await db.commit()
# dp.callback_query.register(lambda c: on_answer(c, bot), F.data.startswith("quiz:"))