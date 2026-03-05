# QuizBot

Telegram-бот для квизов в группах и чатах на **Python + aiogram**.

Бот публикует вопросы, принимает ответы через кнопки, начисляет очки и показывает рейтинг участников.

## Возможности

- вопросы с вариантами ответов;
- начисление очков за правильные ответы;
- таблица лидеров / топ игроков;
- хранение данных в SQLite;
- загрузка вопросов из JSON-файлов;
- работа в Telegram-группах и беседах.

## Стек

- Python 3.12
- aiogram 3
- aiohttp
- aiosqlite
- APScheduler
- python-dotenv

## Установка

### 1. Клонирование репозитория

```bash
git clone https://github.com/AlekseyKokorin24/QuizBot.git
cd QuizBot
```

### 2. Создание виртуального окружения

**Windows (PowerShell):**

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

## Настройка

Создай файл `.env` в корне проекта.

Пример:

```env
BOT_TOKEN=your_telegram_bot_token
ADMIN_ID=123456789
DB_PATH=./data/quizbot.sqlite3
TZ=Europe/Amsterdam
```

> Файл `.env` не должен попадать в GitHub.

## Запуск

Если точка входа — `main.py`:

```bash
python main.py
```

Если точка входа — `bot.py`:

```bash
python bot.py
```

## Структура проекта

Примерная структура:

```text
QuizBot/
├── data/
│   ├── q_cars.json
│   ├── q_investing.json
│   └── q_uk_koap.json
├── .env
├── .gitignore
├── requirements.txt
├── main.py / bot.py
└── README.md
```

## Данные вопросов

Вопросы обычно хранятся в папке `data/` в формате JSON.

Если у тебя несколько наборов вопросов, можно разделять их по темам:

- `q_cars.json`
- `q_investing.json`
- `q_uk_koap.json`

## База данных

Бот использует SQLite.

Обычно файл базы данных:

- `quizbot.sqlite3`
- или другой путь, указанный в `.env`

Если в проекте есть SQL-файл для инициализации структуры, его можно применить отдельно.

## GitHub

### Не загружать в репозиторий

- `.venv/`
- `.env`
- `__pycache__/`
- `*.pyc`
- `*.sqlite3`, `*.db` (если там реальные данные)
- `logs/`
- `.vscode/`, `.idea/`
- `.venv.zip`

### Обязательно загрузить

- исходный код бота;
- `requirements.txt`;
- `.gitignore`;
- `README.md`;
- JSON-файлы с вопросами (если это часть проекта и там нет приватных данных).

## Полезные Git-команды

Первый пуш:

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/AlekseyKokorin24/QuizBot.git
git push -u origin main
```

Если GitHub уже содержит коммит:

```bash
git pull --rebase origin main
git push origin main
```

## Типичные проблемы

### `error: failed to push some refs`

На удалённом репозитории уже есть изменения.

Решение:

```bash
git pull --rebase origin main
git push origin main
```

### `cannot pull with rebase: You have unstaged changes`

Есть незакоммиченные изменения.

Решение:

```bash
git add -A
git commit -m "Save local changes"
git pull --rebase origin main
```

### Предупреждение про `LF will be replaced by CRLF`

Это предупреждение Git про окончания строк в Windows. На работу проекта обычно не влияет.

## Лицензия

Пока не указана. При желании можно добавить `MIT`.
