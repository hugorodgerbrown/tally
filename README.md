# Workouts

Interval workouts built from a library of exercises, run hands-free on a
phone. A Django backend stores exercises, workouts and completed sessions;
a PWA runs the workout as a full-screen timer and works offline.

## Stack

| Piece | Choice |
| --- | --- |
| Python packaging | [uv](https://docs.astral.sh/uv/) (`pyproject.toml`, `uv.lock`) |
| Backend | Django 6.1, SQLite |
| Static files | WhiteNoise |
| Tests | pytest + pytest-django |
| Lint / format | Ruff |
| Front end | Plain JavaScript, no build step |
| Offline | Service worker (app shell and assets) and IndexedDB (workouts and unsent sessions) |

## Run it

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py seed_library      # 21 exercises and a sample workout
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

- `http://localhost:8000/` is the app. It signs in through the admin login.
- `http://localhost:8000/admin/` manages exercises and workouts.

Tests and lint:

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

To try it on a phone on the same network, run
`uv run python manage.py runserver 0.0.0.0:8000` and set
`DJANGO_ALLOWED_HOSTS`. Service workers only run on `localhost` or HTTPS,
so offline mode needs a deployed HTTPS host (or a tunnel) on a real phone.

## Layout

- `library/` holds exercise types, muscle groups, exercises, workouts and
  their ordered items. The five types (aerobic, anaerobic, strength,
  flexibility, fitness) are created by a data migration.
- `activity/` holds completed sessions and the PWA:
  - `api.py`: `GET /api/workouts/` and `POST /api/sessions/`
  - `static/activity/engine.js`: timeline and wall-clock timer
  - `static/activity/store.js`: IndexedDB and sync
  - `static/activity/app.js`: the screens
  - `templates/activity/sw.js`: the service worker, rendered by Django so it
    knows the static file URLs and changes its cache name when they change

## How the activity mode behaves

It follows the approved activity-screen design: summary screen, 5 s get
ready, work / rest / switch-sides / round-break screens, 3-2-1 beeps, a
pause screen with back, skip and end, and a finish screen with time by
type, muscles worked and an optional 1 to 10 effort score.

- One-sided exercises run as two intervals (left, right) with a 5 s switch.
  The duration on a workout item is per side.
- Rounds are a workout setting (default 1) with a break between rounds
  (default 120 s).
- Time on an exercise with several types is split evenly across them.
- Only time actually worked is logged, including when a workout is ended
  early. A session with no work time is not logged.
- The back button pauses the workout instead of leaving it.

## Offline and sync

- Once the app has loaded while signed in, the shell, scripts and the last
  fetched workouts are stored on the phone, and the app opens without a
  connection.
- A finished session goes into an IndexedDB outbox and uploads when the
  server is reachable: on load, when the connection returns, when the app
  comes back to the foreground, and every minute while anything is waiting.
- Each session has a UUID made on the phone, and the server upserts on it,
  so retries never create duplicates. Rating effort after the session has
  synced re-sends it and updates the stored copy.
- Progress is checkpointed while a workout runs. If the app is killed
  mid-workout, the work done so far is logged as ended early on next launch.

## Not built yet

- The desktop workout builder. Use the Django admin for now.
- Monthly reports. `ActivitySession` and `SessionEntry` record what they
  need: time per exercise, with the exercise's types and muscles in the
  library.
