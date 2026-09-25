CITY TYCOON V13 — MEGA UPDATE

This build is based on the uploaded V6 Expanded Monopoly.

V13 adds persistent global progression:
- player level / XP
- V13 season and global leaderboard
- daily reward + streak
- seasonal tasks and claimable rewards
- persistent avatar, clothes, car and map selection
- persistent businesses with upgrades and passive income collection
- expanded V13 dashboard inside the Mini App
- existing rooms, Monopoly board, trading, chat, auctions, mortgages, jail, achievements and required-channel admin are preserved

Render:
Build Command: pip install -r requirements_city_tycoon_v5.txt
Start Command: python city_tycoon_v13.py

Environment:
PYTHON_VERSION=3.13.5
BOT_TOKEN=...
DATABASE_URL=...
WEB_APP_URL=https://YOUR-SERVICE.onrender.com
ALLOW_BROWSER_DEMO=false
INIT_DATA_MAX_AGE=86400
DB_POOL_MAX=12
ADMIN_IDS=YOUR_TELEGRAM_ID

IMPORTANT: put city_tycoon_v13.py and requirements_city_tycoon_v5.txt in the ROOT of the GitHub repository.
Then Render -> Manual Deploy -> Clear build cache & deploy.
The PostgreSQL schema migrates automatically on startup.
