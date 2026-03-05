# QuizBot

Telegram-бот для квизов в группах и чатах на **Python + aiogram**.

Бот публикует вопросы, принимает ответы через inline-кнопки, начисляет очки и показывает рейтинг участников.

## Возможности

- автоматический запуск викторин по расписанию;
- ручной запуск следующего вопроса;
- пауза и возобновление викторин;
- добавление вопросов вручную;
- импорт вопросов из JSON;
- начисление очков;
- личные очки и топ-10 игроков;
- хранение данных в SQLite.

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
TZ=Europe/Berlin
```

> Файл `.env` не должен попадать в GitHub.

## Запуск

```bash
python bot.py
```

## Команды бота

### Основные команды

- `/start_q` — включить бота для чата и подготовить викторины;
- `/pause` — поставить викторины на паузу;
- `/resume` — снова включить викторины;
- `/next` — запустить следующий вопрос, если активного квиза нет;
- `/next_force` — закрыть текущий квиз и сразу запустить новый;
- `/dbg` — отладочная команда: показывает текст сообщения, `chat_id` и `user_id`.

### Команды для работы с вопросами

- `/addq` — добавить один вопрос вручную.

Формат:

```text
/addq Вопрос? | Правильный | Неправ1 | Неправ2 | Неправ3
```

- `/import` — импортировать вопросы из JSON-файла, который уже находится на сервере.

Формат:

```text
/import data/questions.json
```

### Команды для очков и рейтинга

- `!очки` или `!points` — показать свои очки;
- `!топ` или `!top` — показать топ-10 игроков;
- `/addpoints <user_id> <количество>` — вручную добавить очки пользователю.

Пример:

```text
/addpoints 123456789 10
```

## Права доступа

Админские команды:

- `/pause`
- `/resume`
- `/addq`
- `/import`
- `/next`
- `/next_force`
- `/addpoints`

Если список `ADMIN_IDS` пустой, ограничения на эти команды фактически отключаются.

## Структура проекта

```text
QuizBot/
├── data/
│   ├── q_cars.json
│   ├── q_investing.json
│   └── q_uk_koap.json
├── .env
├── .gitignore
├── requirements.txt
├── bot.py
└── README.md
```

## Данные вопросов

Вопросы обычно хранятся в папке `data/` в формате JSON.

Примеры файлов:

- `q_cars.json`
- `q_investing.json`
- `q_uk_koap.json`

## База данных

Бот использует SQLite.

Обычно файл базы данных:

- `quizbot.sqlite3`
- или другой путь, указанный в `.env`

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
