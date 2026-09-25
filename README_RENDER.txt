CITY TYCOON V5 — FINAL FIX

Upload ALL files from this folder to the ROOT of the GitHub repository.

Files:
- city_tycoon_v5.py
- requirements_city_tycoon_v5.txt
- .python-version

Render:
Build Command:
pip install -r requirements_city_tycoon_v5.txt

Start Command:
python city_tycoon_v5.py

Environment:
PYTHON_VERSION=3.13.5
BOT_TOKEN=...
DATABASE_URL=...
WEB_APP_URL=https://YOUR-SERVICE.onrender.com
ALLOW_BROWSER_DEMO=false
INIT_DATA_MAX_AGE=86400
DB_POOL_MAX=12
ADMIN_IDS=YOUR_TELEGRAM_ID

After GitHub commit: Render -> Manual Deploy -> Clear build cache & deploy.

This version fixes the Mini App frontend request handling and JavaScript auction syntax errors.
