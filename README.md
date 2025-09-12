# Telegram Daily Random Host Bot

Бот выбирает случайного участника чата и каждый будний день в 10:00 пишет:

> Сегодня дейли проводит: @username

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
```

3. Запустите:

```bash
python bot.py
```

## Права бота

- Добавьте бота в целевой чат и сделайте его администратором (нужно для чтения списка участников и отправки сообщений).

## Команды

- `/setchat` — зафиксировать чат для рассылки.
- `/chatid` — показать ID текущего чата (можно проверить, что бот в нужном чате).
- `/add` — добавить пользователя(ей) в пул. Поддерживаются списки:
  - Примеры: `/add @user1, @user2`, `/add Иван; Петр`, `/add @u1 @u2`, многострочно тоже работает.
- `/remove` — удалить пользователя(ей) из пула. Аналогично поддерживает списки.
- `/addall` — добавить всех известных участников чата в пул.
  - Бот узнаёт участников, когда они пишут сообщения, или при обновлениях статуса в чате. Если список пуст — попросите коллег написать любое сообщение, затем вызовите `/addall`.
- `/list` — показать текущий пул.
- `/today` — принудительно выбрать ведущего сейчас.
- `/testjob [сек]` — запланировать тестовый анонс через N секунд (по умолчанию 5), чтобы проверить, что задачи работают.

## Деплой

### Вариант 1: Docker Compose

1. Создайте `.env` рядом с `docker-compose.yml`:

```env
BOT_TOKEN=ваш_токен
TZ=Europe/Moscow
```

2. Соберите и запустите:

```bash
docker compose up -d --build
```

3. Бот хранит состояние в `state.json` смонтированном из хоста.

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

3. Создайте `/opt/telegram-daily-bot/.env` с переменными `BOT_TOKEN` и `TZ`.
4. Скопируйте unit-файл:

```bash
sudo cp deploy/telegram-daily-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now telegram-daily-bot.service
```

Логи:

```bash
journalctl -u telegram-daily-bot.service -f
```
