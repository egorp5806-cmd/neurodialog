CITY TYCOON V5 — Render

1. Используй ту же PostgreSQL базу, что и V4. Данные удалять НЕ нужно.

Build Command:
pip install -r requirements_city_tycoon_v5.txt

Start Command:
python city_tycoon_v5.py

Environment Variables:
BOT_TOKEN=токен Telegram бота
DATABASE_URL=URL PostgreSQL от Render
WEB_APP_URL=https://твой-сервис.onrender.com
ALLOW_BROWSER_DEMO=false
INIT_DATA_MAX_AGE=86400
DB_POOL_MAX=12

Что добавлено в V5:
- реванш после завершения партии без удаления комнаты;
- карточки «Шанса» с расширенным набором событий;
- достижения игрока: первый ход, дубль, строитель, коллекционер;
- визуальные дома и отель на уровне 5;
- анимационный акцент клетки последнего хода;
- при банкротстве активы переходят кредитору;
- залог нельзя оформить, пока на улице есть улучшения;
- PostgreSQL сохраняется, миграции выполняются автоматически.

Важно: перед выкладкой V5 желательно сделать Deploy в Render и проверить /health. Живой PostgreSQL/Telegram здесь не подключался, поэтому после первого запуска проверь логи Render.
