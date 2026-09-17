# SearchVakancy

Агрегатор вакансий Frontend-разработчиков (HH.ru, Habr Career — про VK Jobs
см. "Скрейпинг вакансий" ниже) с real-time обновлениями и уведомлениями в Telegram.

Полный план разработки: см. историю чата / документ плана. Статус по фазам — ниже.

## Статус

- ✅ **Phase 1** — Django-проект, модели БД (`Job`, `JobSource`, `UserJobFilter`,
  `JobNotification`), Celery + Redis, Django Channels (WebSocket `/ws/jobs/`),
  Docker Compose, базовый read-only REST API.
- 🟡 **Phase 2** — скрейперы HH.ru (`hh_scraper.py`, официальный API) и
  Habr Career (`habr_scraper.py`, HTML career.habr.com/vacancies —
  публичного API нет). `BaseScraper` — общий контракт, `run_all_scrapers`
  по расписанию каждые 30 мин через Celery Beat.
  **VK Jobs не реализован** — `vk.com/jobs` оказался не общей биржей
  вакансий, а собственной карьерной страницей ВКонтакте (SPA на их
  внутреннем `jobs.vacancies` API с анонимным токеном) — см. README ниже.
- ✅ **Phase 3** — Telegram-бот (`apps/telegram_bot`): команды `/start`,
  `/subscribe`, `/unsubscribe`, `/latest`, `/filters`, `/trending`; Celery-таск
  `notify_users_for_jobs`, который при появлении новых вакансий проверяет
  фильтры подписанных пользователей и шлёт уведомления.
- ✅ **Phase 4** — полноценный REST API: `min_salary`/`max_salary`/
  `experience_level`/`job_type`/`employment_type`/`location`-фильтры,
  полнотекстовый поиск, `/api/jobs/filters/` (CRUD), `/api/jobs/<id>/favorite/`
  + `/api/jobs/favorites/`, `/api/jobs/notifications/` (+`mark_read`),
  `/api/jobs/stats/`. Авторизация — токен (`/api/auth/token/`).
- ✅ **Phase 5** — React-фронтенд (Vite + TypeScript + Tailwind v4 +
  React Router): список вакансий с фильтрами/поиском/пагинацией, real-time
  баннер новых вакансий через WebSocket, избранное, уведомления, тёмная тема,
  логин/регистрация.
- ✅ **Phase 6** — интеграция и прод-готовность: структурное логирование,
  `docker-compose.prod.yml` (daphne + whitenoise + nginx reverse-proxy на
  едином origin, без CORS), фикс `SECRET_KEY`/статики в проде.

## Стек

- Backend: Django 5 + DRF + Django Channels (Daphne) + Celery + Redis + PostgreSQL
- Frontend: React 19 + TypeScript + Vite + Tailwind CSS v4 + React Router 7
- Infra: Docker Compose

## Быстрый старт (Docker)

```bash
cp .env.example .env    # уже сделано, при необходимости отредактируйте
docker compose up --build
```

После старта:

- Frontend: http://localhost:5173/
- API: http://localhost:8010/api/jobs/
- Django admin: http://localhost:8010/admin/
- Swagger UI: http://localhost:8010/api/docs/
- WebSocket: ws://localhost:8010/ws/jobs/

Применить миграции и создать суперпользователя (в отдельном терминале,
пока `docker compose up` работает):

```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
```

## Структура backend

```
backend/
├── apps/
│   ├── accounts/      — кастомная модель пользователя Customer
│   ├── jobs/          — модели, API, WebSocket-consumer, tasks.py
│   ├── scraper/       — BaseScraper, HHScraper, registry.py, tests/
│   └── telegram_bot/  — bot.py, services.py, client.py, tasks.py, tests/
├── config/
│   ├── settings/    — base.py / dev.py / prod.py
│   ├── celery.py
│   ├── asgi.py      — WebSocket routing
│   ├── wsgi.py
│   └── urls.py
├── requirements/
└── manage.py
```

## Структура frontend

```
frontend/
├── src/
│   ├── pages/       — JobsPage, FavoritesPage, NotificationsPage, LoginPage
│   ├── components/  — Layout, JobCard, JobList, JobFilters, RequireAuth
│   ├── lib/         — api.ts (fetch-клиент), useJobUpdates.ts (WebSocket-хук),
│   │                  AuthContext.tsx, theme.ts, format.ts
│   └── types.ts     — TS-типы, зеркалящие сериализаторы backend
└── vite.config.ts
```

Дев-сервер (Vite) уже поднимается вместе с остальным стеком через
`docker compose up`. Локально без Docker: `cd frontend && npm install && npm run dev`
(нужен `frontend/.env` с `VITE_API_BASE_URL`, см. `.env.example`).

Валидация пароля при регистрации — стандартная Django `validate_password`
(минимум 8 символов, не слишком простой и т.п.), своей формы валидации
сверх этого нет.

## Локальный запуск без Docker

Требуется Python 3.12+, PostgreSQL и Redis, запущенные локально.

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements/dev.txt
python manage.py migrate
python manage.py runserver
```

WebSocket/ASGI-сервер для разработки без Docker:

```bash
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

Celery (в отдельных терминалах):

```bash
celery -A config worker -l info
celery -A config beat -l info
```

## Скрейпинг вакансий

Скрейперы наследуются от `apps/scraper/base.py:BaseScraper` и регистрируются
в `apps/scraper/registry.py`. По расписанию (каждые 30 мин, см.
`CELERY_BEAT_SCHEDULE` в `config/settings/base.py`) Celery Beat запускает
`apps.jobs.tasks.run_all_scrapers`.

Запустить скрейпер вручную (`hh` или `habr`):

```bash
docker compose exec backend python manage.py shell -c "from apps.jobs.tasks import run_scraper; print(run_scraper('habr'))"
```

При первом прогоне источника (`JobSource.last_sync` ещё `null`) вакансии
сохраняются молча, без Telegram-уведомлений — иначе первый же подписчик
получил бы спам из всей найденной истории разом. Уведомления начинают
идти со второго и последующих прогонов (см. `is_first_sync` в
`BaseScraper.run()` и `apps/jobs/tasks.py`).

> **HH.ru** отдаёт `{"errors":[{"type":"forbidden"}]}` при запросах с "плохих"
> (дата-центровых/облачных) IP — это блокировка на стороне их DDoS-Guard,
> не баг скрейпера. Запускайте с обычного сервера/дома, либо через прокси.

> **Habr Career** публичного API не имеет — парсим HTML `career.habr.com/vacancies`
> (BeautifulSoup). Два нюанса, на которые стоит обратить внимание при
> поддержке (проверено вручную на живом сайте 17.09.2026):
> - `?specializations=frontend_developer` **не фильтрует** список вообще
>   (сервер отдаёт общую ленту) — рабочий вариант — полнотекстовый поиск
>   `?q=frontend`, но и он не строгий, поэтому `is_frontend_relevant()`
>   по заголовку — обязательная вторая проверка, не подстраховка.
> - Диапазон зарплаты на сайте — **"от X до Y ₽"** (словами), а не "X – Y ₽"
>   через тире, как можно было бы предположить с ходу.

### VK Jobs — не реализован

`vk.com/jobs` — это **не общая биржа вакансий**, а карьерная страница самого
ВКонтакте (SPA, вакансии только в самой компании VK). Технически это
работает через приватный VK API (`method/jobs.vacancies`) с анонимным
токеном и `client_secret`, зашитым прямо в HTML лендинга — реверс-инжинирить
такой полу-приватный flow ради десятка вакансий одной компании не имеет
смысла: и хрупко (может измениться без предупреждения), и по сути не даёт
того, что нужно приложению (вакансии у *разных* компаний). Общей замены
"VK Jobs" среди русскоязычных агрегаторов на практике нет — HH.ru и
Habr Career вдвоём покрывают подавляющее большинство реальных вакансий.

## Telegram-бот

1. Получите токен у [@BotFather](https://t.me/BotFather) (`/newbot`).
2. Впишите его в `.env`: `TELEGRAM_BOT_TOKEN=...`.
3. Запустите бота отдельным профилем (он не поднимается вместе с остальным
   стеком по умолчанию, чтобы не падать в рестарт-луп без токена):

   ```bash
   docker compose --profile telegram up -d telegram_bot
   ```

Команды бота: `/start`, `/subscribe`, `/unsubscribe`, `/latest`, `/filters`
(`/filters min_salary=150000 keywords=react,vue locations=Москва,Удалённо
experience=junior,middle` — настройка; `/filters reset` — сброс), `/trending`.

При первом обращении к боту под пользователя автоматически создаётся
отдельный `Customer` (`accounts.Customer`, `telegram_chat_id` = chat_id из
Telegram) — он не связан с веб-аккаунтом, зарегистрированным через фронтенд.
Ручной привязки Telegram ↔ веб-аккаунт пока нет (не входила ни в один Phase).

Отправка уведомлений о новых вакансиях не зависит от того, запущен ли
процесс бота — это отдельный Celery-таск (`apps/telegram_bot/tasks.py`),
который запускается автоматически после каждого скрейпинга.

## REST API (Phase 4)

Публично (без авторизации):
- `GET /api/jobs/` — список, фильтры `?min_salary=&max_salary=&location=&experience_level=&job_type=&employment_type=&source=&posted_after=`, поиск `?search=`, сортировка `?ordering=-posted_at`
- `GET /api/jobs/<id>/`, `GET /api/jobs/sources/`, `GET /api/jobs/stats/`

Нужен токен (`Authorization: Token <token>`):
- `POST /api/auth/register/` (`username`, `password`, `email?`) — регистрация, сразу возвращает токен
- `POST /api/auth/token/` (`username`, `password`) — получить токен для существующего пользователя
- `GET/POST /api/jobs/filters/`, `GET/PATCH/DELETE /api/jobs/filters/<id>/` — свои фильтры
- `POST/DELETE /api/jobs/<id>/favorite/`, `GET /api/jobs/favorites/` — избранное
- `GET /api/jobs/notifications/`, `POST /api/jobs/notifications/<id>/mark_read/`

Есть демо-пользователь для ручных проверок через `/api/docs/` (кнопка Authorize,
схема `Token`): `demo` / `demo12345`.

## Продакшн (docker-compose.prod.yml)

Отдельный compose-файл: daphne (ASGI, статика через whitenoise) + Celery
worker/beat + Telegram-бот (профиль `telegram`) + фронтенд, собранный
`vite build` и отданный через nginx, который сам получает и продлевает
TLS-сертификат Let's Encrypt и проксирует `/api/`, `/admin/`, `/static/`,
`/media/`, `/ws/` на backend — фронт и API живут на одном HTTPS-origin,
поэтому в проде CORS не нужен вообще.

### Первый деплой на сервер

Нужен реальный домен, у которого A-запись уже указывает на IP этого
сервера, и открытые снаружи порты 80/443 (Let's Encrypt проверяет
владение доменом по HTTP на 80-м).

```bash
# на сервере, с кодом проекта
cp .env.prod.example .env.prod
nano .env.prod   # обязательно: DOMAIN, DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS, POSTGRES_PASSWORD

./init-letsencrypt.sh   # выпускает сертификат и поднимает весь стек одной командой
```

`init-letsencrypt.sh` — не самописная магия, а стандартная схема для
nginx+certbot в Docker (временный self-signed сертификат, чтобы nginx
вообще смог стартовать с 443 → настоящий через тот же nginx в
webroot-режиме). Дальше сертификат продлевается сам — сервис `certbot`
в compose крутится постоянно и раз в 12 часов гоняет `certbot renew`.

Затем — как обычно:

```bash
docker compose -p searchvakancy-prod -f docker-compose.prod.yml --env-file .env.prod exec backend python manage.py migrate
docker compose -p searchvakancy-prod -f docker-compose.prod.yml --env-file .env.prod exec backend python manage.py createsuperuser
```

Открыть: `https://<ваш-домен>/`.

> Если dev-стек (`docker-compose.yml`) тоже запущен на этой же машине —
> сервисы называются одинаково ("backend", "db"...), поэтому везде нужно
> отдельное имя проекта (`-p searchvakancy-prod`), иначе Compose перепутает
> контейнеры. `init-letsencrypt.sh` уже это учитывает.

Бот отдельным профилем: `docker compose -p searchvakancy-prod -f docker-compose.prod.yml --env-file .env.prod --profile telegram up -d telegram_bot`.

### Обновление кода после первого деплоя

Сертификат и его автопродление трогать не нужно — просто:

```bash
docker compose -p searchvakancy-prod -f docker-compose.prod.yml --env-file .env.prod up -d --build
docker compose -p searchvakancy-prod -f docker-compose.prod.yml --env-file .env.prod exec backend python manage.py migrate
```

## Тесты

```bash
docker compose exec backend python -m pytest
```

Фронтенд (типы + сборка + линт, автотестов на JS/TS пока нет):

```bash
cd frontend
npm run build
npm run lint
```
