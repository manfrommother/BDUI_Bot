# Telegram Daily Random Host Bot

Бот выбирает случайного участника чата и каждый **рабочий день** (согласно производственному календарю РФ) в 10:00 пишет:

> Сегодня дейли проводит: @username

## Новые возможности

- ✅ **Производственный календарь РФ**: автоматическая проверка рабочих дней через API (isdayoff.ru)
- ✅ **Права администратора**: команды управления (`/add`, `/remove`, `/setchat`, `/addall`) доступны только администратору
- ✅ **Умная ротация**: автоматическое пополнение пула после того, как все участники провели дейли

## Настройка

1. Установите зависимости:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

2. Создайте файл `.env` на основе примера:

```env
BOT_TOKEN=ваш_токен
TZ=Europe/Moscow
# ID администратора (по умолчанию 445320878)
ADMIN_USER_ID=445320878
# Необязательный путь к состоянию (по умолчанию state.json в текущей директории)
# STATE_FILE=/data/state.json
```

3. Запустите:

```bash
python bot.py
```

## Права бота

- Добавьте бота в целевой чат и сделайте его администратором (нужно для чтения списка участников и отправки сообщений).

## Команды

### Команды администратора (только для ADMIN_USER_ID)

- `/setchat` — зафиксировать чат для рассылки.
- `/add` — добавить пользователя(ей) в пул. Поддерживаются списки:
  - Примеры: `/add @user1, @user2`, `/add Иван; Петр`, `/add @u1 @u2`, многострочно тоже работает.
- `/remove` — удалить пользователя(ей) из пула. Аналогично поддерживает списки.
- `/addall` — добавить всех известных участников чата в пул.
  - Бот узнаёт участников, когда они пишут сообщения, или при обновлениях статуса в чате. Если список пуст — попросите коллег написать любое сообщение, затем вызовите `/addall`.

### Общие команды

- `/chatid` — показать ID текущего чата (можно проверить, что бот в нужном чате).
- `/list` — показать текущий пул.
- `/today` — принудительно выбрать ведущего сейчас.
- `/testjob [сек]` — запланировать тестовый анонс через N секунд (по умолчанию 5), чтобы проверить, что задачи работают.

## Деплой

### Вариант 1: Docker Compose

1. Создайте `.env` рядом с `docker-compose.yml`:

```env
BOT_TOKEN=ваш_токен
TZ=Europe/Moscow
STATE_FILE=/data/state.json
```

2. Соберите и запустите:

```bash
docker compose up -d --build
```

3. Состояние хранится на именованном томе `bot_state` (в контейнере путь `/data`). Это решает проблемы прав.

Остановить:

```bash
docker compose down
```

### Вариант 2: systemd (без Docker)

1. Скопируйте проект на сервер, например в `/opt/telegram-daily-bot`.
2. Создайте venv и установите зависимости:

```bash
cd /opt/telegram-daily-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
``` 

3. Создайте `/opt/telegram-daily-bot/.env`:

```env
BOT_TOKEN=ваш_токен
TZ=Europe/Moscow
STATE_FILE=/opt/telegram-daily-bot/data/state.json
```

4. Создайте директорию под состояние и дайте права пользователю сервиса:

```bash
sudo mkdir -p /opt/telegram-daily-bot/data
sudo chown -R ubuntu:ubuntu /opt/telegram-daily-bot
```

5. Скопируйте unit-файл и включите сервис:

```bash
sudo cp deploy/telegram-daily-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now telegram-daily-bot.service
```

Логи:

```bash
journalctl -u telegram-daily-bot.service -f
```

### Если видите Permission denied при записи в STATE_FILE в Docker

Скорее всего, именованный том уже создан с неверными правами. Исправьте так:

```bash
docker compose down
# удалить существующий том
docker volume rm pythonproject1_bot_state || true
# пересобрать образ (создаст /data с владельцем botuser внутри образа)
docker compose build --no-cache
# поднять контейнер (новый том унаследует права)
docker compose up -d
```

Проверьте логи:
```bash
docker logs -f telegram-daily-bot
```
