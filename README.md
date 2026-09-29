# TTPU Student Data

Student data collection for **Turin Polytechnic University in Tashkent**:

- **Telegram bot:** students photograph their passport or ID card. The bot reads their data from it, then collects phone, group, a 3×4 photo and a CV.
- **Staff website:** admins, tutors and group leaders sign in with a **login and password** to view, filter, edit and export students.
- **Staff in the bot:** the same staff can browse, search, edit and export students from Telegram after `/login`.

Everything runs as **one process** on one server with **PostgreSQL** (SQLite for local testing). The interface is in **Uzbek, Russian and English**.

| | Student | Group leader | Tutor | Admin |
|---|---|---|---|---|
| Fill in own data once (bot) | ✔ | ✔ (leaders are usually students too) | | |
| See students (website + bot) | | their group | all groups | all groups |
| Edit students, replace files | | their group | ✔ | ✔ |
| Delete students | | | | ✔ |
| Groups, staff accounts, settings, activity log | | | | ✔ |

---

## How registration works

1. **Document.** The student sends a photo of the passport's main page, or of the **back** of the ID card. The bot reads the machine-readable zone (the lines with `<<<`): surname, name, date of birth, gender, document number, expiry date, PINFL and nationality. For an ID card, it then asks for the front side.
2. **Check.** The bot shows what it read and suggests the patronymic from the printed text (it isn't in the machine-readable lines), or asks for it. The student confirms.
3. **Phone** (share-contact button), **group**, **3×4 photo**, **CV** (PDF, Word, or photos of pages).
4. **Review card** with the 3×4 photo, then **Submit**. The group's leaders get a Telegram notification.

Before submitting, the student can fix any field separately: surname, name, patronymic and gender (in case glare garbled them), phone, group, photo, CV, or a new document photo. Values protected by check digits (document number, expiry, PINFL, date of birth) can only change with a new photo. Anything the student typed instead of what was read is shown in the activity log.

**After submitting, the data is locked for the student.** Only staff can correct it (website or bot).

The bot asks for a new photo, with the reason, when:
- the photo is blurry, too small, or the bottom lines are cut off or unreadable;
- the document has expired, or the age is outside the allowed range;
- the document is already registered from another Telegram account;
- the "3×4 photo" isn't a vertical portrait with exactly one face.

Every value protected by the document's check digits must match, so misread data isn't accepted silently.

Each step replaces the previous screen, so the chat stays short. Error messages replace each other instead of piling up.

## Privacy

- **Everything is processed on your server.** Text reading uses [RapidOCR](https://github.com/RapidAI/RapidOCR) (PaddleOCR models on ONNX Runtime) and face detection uses OpenCV's YuNet model. The models ship inside the installed packages and in `app/assets/`. There are **no network calls** in the image code, and no image or data is sent to any external or AI service.
- Students' files are sent through Telegram, since that's the channel they use. The bot reads them from Telegram when needed. Files that staff upload on the website are stored in `data/uploads`.
- Staff passwords are stored only as scrypt hashes. Sign-ins, edits (with before/after values), exports and every passport/CV view are recorded in the **activity log**.

---

## Quick start (local)

Requirements: Python 3.12+, Node.js 20+.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
(cd web && npm ci && npm run build)        # builds the website into web/dist
cp .env.example .env                       # set BOT_TOKEN and ADMIN_IDS
.venv/bin/python -m app.cli create-admin admin --name "Your Name"   # asks for a password
.venv/bin/python -m app                    # bot + website on http://localhost:8080
```

1. Create the bot with [@BotFather](https://t.me/BotFather) and put the token in `BOT_TOKEN`.
2. `ADMIN_IDS` (your Telegram ID, e.g. from [@userinfobot](https://t.me/userinfobot)) makes you an admin in the bot even before you have an account.
3. Sign in at `http://localhost:8080` with the admin login you created. In the bot, send `/login` to connect your Telegram to the same account.
4. **Groups → Import from EduPage** adds every group in the university's public timetable (https://ttpu.edupage.org). You can also type names in **Add groups**. Students can now register.
5. **Staff accounts → New account** for each tutor or group leader. You get a temporary password to hand over: the person must change it at the first sign-in, and sends `/login` to the bot to get the staff menus.

For frontend development with hot reload, run `npm run dev` in `web/` and open `http://localhost:5173`. It proxies `/api` to the Python app on :8080.

Forgot a password? Another admin can reset it on the website, or run `.venv/bin/python -m app.cli reset-password <login>`.

## Production (Docker, HTTPS)

You need a small server (2 vCPU / 2 GB RAM is enough; the OCR models use about 300 MB) and a domain pointing at it.

```bash
git clone https://github.com/malikov07/ttpu_data_collection_bot.git /opt/ttpu && cd /opt/ttpu
cp .env.example .env     # BOT_TOKEN, ADMIN_IDS, DOMAIN, POSTGRES_PASSWORD, BACKUP_PASSWORD
mkdir -p backups && chown 1000:1000 backups
docker compose up -d --build
docker compose exec bot python -m app.cli create-admin admin
docker compose exec bot python -m app.cli import-groups   # groups from EduPage
docker compose logs -f bot
```

Compose runs three services:
- **bot:** the Telegram bot and the website, in one container.
- **db:** PostgreSQL.
- **caddy:** gets an HTTPS certificate for `DOMAIN` automatically (once its DNS A record points at the server).

Database migrations run automatically on start. Run only **one** instance per bot token: stop the bot on your laptop before starting it on the server.

**Updating:** `cd /opt/ttpu && git pull && docker compose up -d --build`.

## Backups

Every day at `BACKUP_TIME` (03:00 Tashkent time by default) the bot:

1. dumps the database (`database.sql`) and the files staff uploaded on the website (`uploads/`) into one zip, **encrypted with `BACKUP_PASSWORD`** (AES-256);
2. saves it on the server in `/opt/ttpu/backups/` and deletes backups older than `BACKUP_KEEP_DAYS` (30);
3. sends it to every admin in Telegram (`ADMIN_IDS` and admin accounts connected with `/login`).

Admins can make one at any time with **/backup** in the bot. If a backup fails, admins get a message.

Open a backup with **7-Zip** (Windows), **Keka** (macOS) or `7z x file.zip` (Linux) and the backup password. Windows' built-in zip can't open AES-encrypted archives.

Students' photos, passports and CVs sent through the bot stay on Telegram's servers; the database keeps their file ids, which work with this bot's token. Keep the token.

**Restore** (replaces the current database):

```bash
cd /opt/ttpu
7z x backups/ttpu-backup-2026-01-31_0300.zip -o/tmp/restore     # asks for the backup password
docker compose stop bot
docker compose exec -T db psql -U bot -d ttpu_bot < /tmp/restore/database.sql
docker compose cp /tmp/restore/uploads/. bot:/app/data/uploads/   # if the archive has uploads
docker compose start bot
rm -rf /tmp/restore
```

## Bot profile

The bot's name, "About" text and description are in the translation files (`bot.name`, `bot.short_description`, `bot.description`) and are set in all three languages when the bot starts; only changed values are sent to Telegram.

The profile picture is `branding/avatar.svg` (rendered as `branding/avatar.png`). To upload it (or another image):

```bash
.venv/bin/python -m app.cli set-profile-photo              # branding/avatar.png
.venv/bin/python -m app.cli set-profile-photo other.jpg
```

## Configuration

Server settings live in `.env` (see [.env.example](.env.example)). Admins can change these on the website (**Settings**) or in the bot (`/admin` → Settings) without a restart:

| Setting | Meaning |
|---|---|
| Accept registrations | Off: students can't submit data |
| Notify group leaders | Telegram message to leaders about new students |
| Minimum / maximum age | Checked against the date of birth in the document |
| Max CV pages as photos | 1–10 |

## Staff features

| | Website | Bot |
|---|---|---|
| Browse by group, search (name, phone, document no., PINFL, @username) | ✔ | ✔ `/students`, `/find` |
| Student card with photo, passport, CV | ✔ (in-page viewer) | ✔ |
| Edit name, patronymic, birth date, gender, phone, group | ✔ | ✔ |
| Edit document number / expiry / PINFL, replace files | ✔ | |
| Excel export (in the user's language) | ✔ | ✔ `/export` |
| Delete students (admins) | ✔ | ✔ |
| Groups (incl. import from EduPage), staff accounts, settings (admins) | ✔ | ✔ `/admin` |
| Activity log (admins) | ✔ | |

## Security

- **Sign-in:** login and password (scrypt hashes). The same error is returned for an unknown login and a wrong password. Attempts are rate-limited per login and per IP. Temporary passwords must be changed at the first sign-in.
- **Sessions:** a random token in an `HttpOnly`, `SameSite=Lax` cookie (`Secure` over HTTPS). Only its hash is stored. Changing or resetting a password, or disabling an account, signs it out everywhere.
- **Requests:** CSRF is blocked by a required header with CORS disabled. A strict Content-Security-Policy, HSTS over HTTPS, and `nosniff` are set.
- **Permissions:** enforced server-side on every request. A leader asking for another group's student gets "not found".
- **Bot:** the `/login` password message is deleted immediately, and failed attempts lock out for 15 minutes.
- **Uploads:** file types are checked by content (magic bytes), not by name. Maximum 20 MB (the Telegram bot limit).

## Project layout

```
app/
  __main__.py          entry point: bot + website + background jobs
  cli.py               create-admin, reset-password
  config.py            settings from .env
  db/                  models, queries, migrations (Alembic), FSM storage
  handlers/            bot: common (/start, /login…), registration, staff, admin, ui (screens)
  web/                 website API (FastAPI): auth, students, groups, accounts, admin
  services/            mrz (parsing), vision (OCR + faces), export, passwords, validators, prefs
  assets/              YuNet face detection model
  i18n/                bot texts: uz, ru, en
web/                   website (React + TypeScript + Tailwind), texts in web/src/i18n
tests/                 MRZ parser, real OCR/face models, bot flows, website API, migrations
```

After changing `app/db/models.py`, create a migration with `.venv/bin/alembic revision --autogenerate -m "what changed"`.

## Tests

```bash
.venv/bin/python -m pytest          # 108 tests, including the real OCR/face models on synthetic images
(cd web && npm run typecheck)       # frontend types and translation completeness
```

## Notes

- Tested on synthetic passport and ID card images. Real photos vary (glare, angles, laminate), so try a few real documents before launch; blurry or glare-covered photos are rejected with a request to retake.
- The consent text refers to the Law of the Republic of Uzbekistan "On Personal Data". Have the university's legal/IT office review the wording and where the server is hosted.
