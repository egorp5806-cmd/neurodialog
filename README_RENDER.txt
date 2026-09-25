CITY TYCOON V5 — CREATE ROOM FIX

GitHub ROOT must contain:
- city_tycoon_v5.py
- requirements_city_tycoon_v5.txt
- .python-version

Render:
Build Command: pip install -r requirements_city_tycoon_v5.txt
Start Command: python city_tycoon_v5.py
Environment: PYTHON_VERSION=3.13.5

Keep:
BOT_TOKEN=...
DATABASE_URL=...
WEB_APP_URL=https://YOUR-SERVICE.onrender.com
ALLOW_BROWSER_DEMO=false
INIT_DATA_MAX_AGE=86400
DB_POOL_MAX=12
ADMIN_IDS=YOUR_TELEGRAM_ID

This version adds JSON error responses and server-side logging for /api/rooms,
and fixes the client-side API error display so the actual HTTP/server error is visible.
