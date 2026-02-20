## Purpose
Short, actionable guidance for AI coding agents working on this Flask project.

## Big-picture architecture
- Single-process Flask app defined in `app.py` (no separate backend services).
- Uses PostgreSQL via `psycopg2` connection pool (`SimpleConnectionPool`) and raw SQL queries in `app.py`.
- Static assets served from `static/`; templates live in `templates/` and use Jinja2.
- Deployment target uses Gunicorn (see `Procfile`) and expects `PORT` env var.

## How to run locally
- Install dependencies: `pip install -r requirements.txt`.
- Recommended local run for development: `python app.py` (defaults to port 10000).
- Production/run by build system: Gunicorn command from `Procfile`: `gunicorn app:app --bind 0.0.0.0:$PORT`.

## Required environment variables
- `DATABASE_URL` — Postgres connection string used by `psycopg2` pool.
- `CLOUD_NAME`, `API_KEY`, `API_SECRET` — Cloudinary credentials used for uploads in `app.py`.
- Optional: `PORT` for Gunicorn/hosting platforms.

Create a `.env` locally (python-dotenv is present) with the above values for convenience.

## Key files and patterns (quick references)
- `app.py` — single source of truth for routes, DB access, and upload logic.
  - DB tables referenced: `portfolio` (columns: id, image_url, date, location, category, type) and `inquiries` (id, name, phone, message, image, status, created_at).
  - `get_random_hero(page, fallback_url)` selects hero images from `static/hero/<page>/` and returns a `url_for('static', filename='hero/<page>/<file>')` string.
  - DB usage pattern: `conn = get_connection()` → `cur = conn.cursor()` → execute → `cur.close()` → `db_pool.putconn(conn)`.
- `Procfile` — used for production process (Gunicorn). Keep Gunicorn args consistent with `app:app`.
- `requirements.txt` — lists Cloudinary, psycopg2-binary, Flask 3.x, Flask-WTF (note: CSRF is disabled in code), coolsms and bcrypt are present but may be used elsewhere.

## Templating & static conventions
- Templates extend `base.html` and expect variables like `hero_image`, `images`, `is_admin`.
- Put page-specific hero images in `static/hero/<page>/` (e.g. `static/hero/about/`). The app looks for images with extensions `.jpg .jpeg .png .webp`.
- Use `url_for('static', filename='...')` in templates; do not hardcode `/static/` paths — `get_random_hero` already returns a `url_for` result.

## Uploads & external integrations
- Image uploads are sent to Cloudinary via `cloudinary.uploader.upload(file)` (see `contact()` route in `app.py`).
- SMS integration library `coolsms-python-sdk` is listed in `requirements.txt` — search codebase before modifying related flows.

## Conventions & gotchas
- CSRF: `app.config['WTF_CSRF_ENABLED'] = False` — many forms post without CSRF tokens. Be cautious when enabling CSRF; update templates and POST handlers accordingly.
- DB pooling: functions use `SimpleConnectionPool`. Always `putconn` back to pool after finishing; reuse the existing pattern.
- Templates use server-side rendering only; JavaScript is used minimally in `templates/*.html` — prefer small, conservative UI changes.
- No test suite detected. Changes that touch DB or uploads should be tested manually or in a disposable environment.

## Debugging tips
- Use the helper route `/debug_hero/<page>` to inspect `static/hero/<page>` contents.
- To reproduce production behavior locally, set `PORT` and run Gunicorn: `gunicorn app:app --bind 0.0.0.0:10000`.

## Suggested first tasks for an AI agent
- When modifying DB queries, mirror the column order and names used in `app.py` to avoid template breakage.
- When adding uploads, follow the Cloudinary call site in `contact()` to keep consistent return data (`result['secure_url']`).
- Preserve existing cursor/connection close order to avoid leaking connections: `cur.close()` then `db_pool.putconn(conn)`.

## Where to look next in the repo
- `app.py` — route logic and SQL queries.
- `templates/` — examples of template variables and CSS/JS patterns (`index.html`, `about.html`, `inquiries.html`).
- `static/hero/` — content convention for hero images.

If any part of the app or env setup is incomplete or you want this doc to include additional run/debug commands, say which area to expand.
