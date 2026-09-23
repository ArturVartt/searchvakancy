# SearchVakancy

Агрегатор вакансий Frontend-разработчиков (HH.ru, Habr Career, SuperJob,
Zarplata.ru, IT-Jobs.uz, VK, Staff.am, HH.uz — подробности по каждому
источнику см. "Скрейпинг вакансий" ниже) с real-time обновлениями и
уведомлениями в Telegram.

Полный план разработки: см. историю чата / документ плана. Статус по фазам — ниже.

## Статус

- ✅ **Phase 1** — Django-проект, модели БД (`Job`, `JobSource`, `UserJobFilter`,
  `JobNotification`), Celery + Redis, Django Channels (WebSocket `/ws/jobs/`),
  Docker Compose, базовый read-only REST API.
- 🟡 **Phase 2** — восемь источников: HH.ru (`hh_scraper.py`, официальный API —
  **закрыт HH с апреля 2026**, см. ниже), Habr Career (`habr_scraper.py`,
  HTML career.habr.com/vacancies — публичного API нет), SuperJob
  (`superjob_scraper.py`, официальный API, нужен бесплатный App ID),
  Zarplata.ru (`zarplata_scraper.py`, HTML — та же платформа/база, что у
  HH.ru, см. нюанс ниже), IT-Jobs.uz (`itjobsuz_scraper.py`, вакансии по
  Узбекистану — HTML с inline JSON, публичного API нет), VK
  (`vk_scraper.py`, HTML team.vk.company — публичный корпоративный
  карьерный сайт холдинга VK, не путать с закрытым `vk.com/jobs`, см.
  нюанс ниже), Staff.am (`staffam_scraper.py`, вакансии по Армении —
  HTML с embedded JSON `__NEXT_DATA__`, публичного API нет, см. нюанс
  ниже) и HH.uz (`hhuz_scraper.py`, вакансии по Узбекистану, та же
  платформа HH Group, что у Zarplata.ru — **⚠️ подключён вопреки
  `robots.txt`, осознанное решение владельца проекта, см. нюанс ниже**).
  `BaseScraper` — общий контракт, `run_all_scrapers` по расписанию каждые
  30 мин через Celery Beat.
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
│   │                  AuthContext.tsx, theme.ts, format.ts, viewedJobs.ts,
│   │                  countryBadge.ts (бейдж "UZ" для IT-Jobs.uz — см. ниже)
│   └── types.ts     — TS-типы, зеркалящие сериализаторы backend
└── vite.config.ts
```

Дев-сервер (Vite) уже поднимается вместе с остальным стеком через
`docker compose up`. Локально без Docker: `cd frontend && npm install && npm run dev`
(нужен `frontend/.env` с `VITE_API_BASE_URL`, см. `.env.example`).

Валидация пароля при регистрации — стандартная Django `validate_password`
(минимум 8 символов, не слишком простой и т.п.), своей формы валидации
сверх этого нет.

### Вакансии из Узбекистана (IT-Jobs.uz) — UI

- Карточка вакансии и чекбокс в фильтре "Источник" показывают голубой
  бейдж **"UZ"** рядом с названием источника (`sourceBadge()` в
  `lib/countryBadge.ts`) — чтобы не путать с рублёвым рынком, когда
  вакансии смешаны в общем списке.
- Сознательно **текстовый бейдж, а не флаг-эмодзи** 🇺🇿: на Windows
  (шрифт Segoe UI Emoji) флаги стран исторически не рендерятся картинкой —
  показываются как два обычных символа кода страны ("uz"), выглядит как
  опечатка, а не как бейдж. Проверено вживую скриншотом на этой машине.
- Валюта UZS (добавлена в `Job.Currency`) — суммы в десятки миллионов
  (`15 000 000–18 000 000 UZS`), это нормально, не баг форматирования.
- Фильтр "Источник" (`JobFilters.tsx`) — чекбоксы по всем активным
  источникам, позволяет полностью скрыть/показать IT-Jobs.uz одним
  кликом. Список источников подтягивается `GET /api/jobs/sources/`.

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

Запустить скрейпер вручную (`hh`, `habr`, `superjob`, `zarplata`, `itjobsuz`, `vk`, `staffam` или `hhuz`):

```bash
docker compose exec backend python manage.py shell -c "from apps.jobs.tasks import run_scraper; print(run_scraper('habr'))"
```

При первом прогоне источника (`JobSource.last_sync` ещё `null`) вакансии
сохраняются молча, без Telegram-уведомлений — иначе первый же подписчик
получил бы спам из всей найденной истории разом. Уведомления начинают
идти со второго и последующих прогонов (см. `is_first_sync` в
`BaseScraper.run()` и `apps/jobs/tasks.py`).

> **HH.ru** отдаёт `{"errors":[{"type":"forbidden"}]}` — и это **не баг и не
> бан по IP дата-центра** (как можно было бы подумать). С апреля 2026 HH.ru
> закрыл публичный `GET /vacancies` для всех неавторизованных запросов —
> ключ теперь дают только работодателям/рекрутинговым сервисам с
> верификацией аккаунта. Тот же 403 будет и с обычного домашнего интернета.
> Источник: https://habr.com/ru/news/1069286/. Легального способа тянуть
> вакансии с HH.ru без такого ключа сейчас нет — источник фактически
> недоступен для этого проекта, пока не появится employer-ключ.

> **Habr Career** публичного API не имеет — парсим HTML `career.habr.com/vacancies`
> (BeautifulSoup). Два нюанса, на которые стоит обратить внимание при
> поддержке (проверено вручную на живом сайте 17.09.2026):
> - `?specializations=frontend_developer` **не фильтрует** список вообще
>   (сервер отдаёт общую ленту) — рабочий вариант — полнотекстовый поиск
>   `?q=frontend`, но и он не строгий, поэтому `is_frontend_relevant()`
>   по заголовку — обязательная вторая проверка, не подстраховка.
> - Диапазон зарплаты на сайте — **"от X до Y ₽"** (словами), а не "X – Y ₽"
>   через тире, как можно было бы предположить с ходу.

> **SuperJob** — единственный источник с открытым официальным API. Нужен
> бесплатный App ID: зарегистрироваться на superjob.ru как работодатель →
> https://api.superjob.ru/register/ → полученный Secret key вписать в
> `SUPERJOB_API_KEY` (`.env`/`.env.prod`). Без ключа скрейпер тихо
> пропускает прогон (не ошибка, см. `fetch_raw_jobs`). Нюансы (проверено
> вживую 22.09.2026):
> - `robots.txt` superjob.ru явно запрещает краулить `/vacancy/` и
>   `/vacancy/search/*` — поэтому именно API, не HTML-скрейпинг, как у Habr.
> - `?keyword=` ищет по всему тексту вакансии, а не только по названию —
>   параметр `srws=1` ("искать только в названии") эффекта не дал (либо не
>   тот параметр, либо не работает). Поэтому `is_frontend_relevant()` тут
>   проверяет **только заголовок**, а не заголовок+описание, как у
>   остальных скрейперов — иначе в выдачу лезли карточки вроде "Старший
>   инженер по исследованиям в области ИИ" только потому, что слово
>   "frontend" где-то мелькнуло в тексте описания.
> - Текст (`profession`, `candidat`, навыки) приходит с неэкранированными
>   HTML-сущностями (`"Python &amp; React"` вместо `"Python & React"`) —
>   раскодируется через `html.unescape()`.

> **Zarplata.ru** — HTML-скрейпинг (BeautifulSoup), публичного API нет.
> ⚠️ Важная оговорка: это тот же движок/база, что и у HH.ru (те же
> `data-qa`-атрибуты, дизайн-система "Magritte", в её собственном JS-конфиге
> `apiHost: "https://api.hh.ru"` — их SSR-бэкенд сам ходит в закрытый в
> апреле 2026 API HH.ru и рендерит результат в HTML любому посетителю).
> `robots.txt` zarplata.ru явно разрешает `/vacancies/*?page=` и запрещает
> только `/vacancy/*` (детальные страницы, сюда и не ходим) — технически и
> формально чисто, но по сути это тот же источник данных, доступ к которому
> HH Group намеренно закрыла на своём основном домене. Решение подключить
> источник несмотря на это принял владелец проекта осознанно (22.09.2026).
> Нюансы разметки:
> - Список не отдаёт дату публикации вакансии вообще (`posted_at=None` для
>   всех вакансий отсюда) — раньше это ломало сортировку (см. ниже).
> - Опыт и зарплата ОБА рендерятся через `<data value="...">` — отличаются
>   только по содержимому `value` (цифры = сумма, `RUB`/`USD`/`EUR` =
>   валюта, `"1-3"` и т.п. = опыт), общего `data-qa` для суммы зарплаты нет.
> - Enum опыта (`noExperience`/`between1And3`/`between3And6`/`moreThan6`)
>   идентичен HH.ru — переиспользуется та же логика маппинга.

> **IT-Jobs.uz** — вакансии по Узбекистану, `robots.txt` открытый
> (`Allow: /`, запрещены только `/api/` и `/admin/`), публичного API нет.
> Next.js, но данные не догружаются JS'ом отдельным запросом — сервер сам
> зашивает их в HTML как inline JSON (React Server Components
> flight-payload), поэтому обычный GET достаточен, headless-браузер не
> нужен (в отличие от GetMatch). Валюта — почти всегда **UZS** (узбекский
> сум, добавлен в `Job.Currency`), суммы поэтому в десятки миллионов —
> это нормально, не баг форматирования. Нюансы:
> - JSON внутри HTML ещё раз завёрнут в JS-строку — кавычки экранированы
>   ОДНИМ обратным слэшем (`\"title\":\"...`). Обычный `json.loads()` не
>   применим (это не самостоятельный JSON-документ). При переводе рабочих
>   regex из ручной JS-проверки (node) в Python-raw-строки один слэш
>   потерялся при написании — `_JOB_BLOCK_SPLIT` не матчился вообще ни
>   разу, скрейпер молча возвращал 0 вакансий. Поймано тестами до
>   деплоя. Исправлено через `re.escape()` на обычных (не raw) строках —
>   там `\\` однозначно значит один backslash, меньше шансов ошибиться
>   вручную при экранировании.
> - `?category=frontend` в URL не фильтрует (как и у Habr/SuperJob) — сайт
>   отдаёт всё одним списком (сейчас ~16 IT-вакансий по всей стране),
>   фильтруем по `categoryName == "Фронтенд"` + `is_frontend_relevant()`.
> - Объём небольшой (5-6 фронтенд-вакансий разом) — маленький нишевый
>   рынок, это ожидаемо, не признак того, что скрейпер что-то недобирает.
> - `companyName` у части вакансий буквально `"Unknown"` — это реальные
>   данные сайта (аноним-постинги), не дефолт скрейпера.

> **Postgres NULL + `ORDER BY -posted_at`**: по умолчанию Postgres считает
> NULL "больше любого значения", поэтому вакансии без даты публикации
> (Zarplata.ru) оказывались бы выше реально свежих. Исправлено через
> `nulls_last=True` — и в `Job.Meta.ordering` (сортировка по умолчанию), и
> отдельно в `NullsLastOrderingFilter` (`apps/jobs/filters.py`) для случая,
> когда сортировка явно запрошена через `?ordering=-posted_at` — обычный
> DRF `OrderingFilter` эту настройку модели не учитывает.

> **VK** (`team.vk.company`) — не путать с `vk.com/jobs` (см. ниже, тупиковый
> вариант). Триггер для этого источника: пользователь показал
> hirehi.ru/moscow-frontend-jobs и спросил, как тот агрегирует вакансии ВК и
> Сбера, раз у нас "нельзя". Проверка показала, что у hirehi нет никакого
> особого доступа — по его собственной статье на vc.ru и открытым данным, он
> собирает вакансии из Telegram-каналов, сайтов самих компаний, LinkedIn и
> hh.ru, а не через приватные API. `team.vk.company` — официальный
> корпоративный карьерный сайт всего холдинга VK (ВКонтакте, OK, Dzen,
> Mail.ru, RuStore, VK Play и др.), обычный серверно-рендеренный HTML без
> JS-магии; `robots.txt` запрещает только `/load_more/` и `/render_partial/`
> (внутренние AJAX-эндпоинты догрузки списка, сюда и не ходим). Список
> (`?specialty=287` — id специализации "Frontend" в таксономии VK) не отдаёт
> зарплату/описание — только заголовок/команду/город, поэтому за полными
> данными идём на детальную страницу каждой вакансии (проверено вживую
> 22.09.2026: сейчас там всего 3-4 фронтенд-вакансии, так что N+1 запросов
> не проблема). Страница вакансии размечена настоящим schema.org
> `JobPosting` (`itemprop="title"`/`hiringOrganization`/`addressLocality`/
> `description`/`datePosted`) — редкий случай, когда парсинг проще, чем у
> остальных источников. Зарплату VK нигде не публикует (как и Habr Career) —
> `salary_from`/`salary_to` всегда `None`, это не баг. Формат работы/
> уровень/график — три отдельных `.vacancy-tag`-блока без schema.org,
> подписанные соседним `h4.vacancy-title` ("Формат работы"/"Уровень"/
> "График работы"); `employment_type=REMOTE` выставляется только если среди
> опций формата *единственный* вариант — "Дистанционный" (иначе, если
> предложен ещё офис/гибрид, считаем обычным полным днём, как у остальных
> скрейперов проекта).

### `vk.com/jobs` и Сбер (`rabota.sber.ru`) — тупиковые варианты

`vk.com/jobs` — **не общая биржа вакансий**, а другая, более старая
карьерная SPA-страница самого ВКонтакте (не holdings-сайт выше). Работает
через приватный VK API (`method/jobs.vacancies`) с анонимным токеном и
`client_secret`, зашитым прямо в HTML лендинга — реверс-инжинирить такой
полу-приватный flow не имеет смысла: хрупко и не даёт вакансий у *разных*
компаний, только у самого VK (см. `team.vk.company` выше — там то же самое,
но нормальным публичным HTML).

У Сбера тоже есть публичный карьерный сайт (`rabota.sber.ru`), но проверка
22.09.2026 показала, что он отдаёт `503` уже на `robots.txt` — WAF банка
агрессивно режет нечеловеческий трафик характерной `TS`-сессионной кукой.
Пробить это можно только полноценным headless-браузером с имитацией живого
пользователя, и то не гарантированно — заметно более хрупкое и рискованное
решение, чем всё остальное в проекте. Владелец проекта решил не тратить на
это время сейчас (22.09.2026).

> **Staff.am** (`staffam_scraper.py`) — крупнейший джоб-борд Армении
> (~80% локального рынка по независимым оценкам). Триггер добавления —
> тот же вопрос про hirehi.ru/VK/Сбер (см. VK выше), после которого
> владелец проекта попросил поискать что-то ещё по Узбекистану и Армении.
> `api.staff.am/robots.txt` запрещает всё (`Disallow: /`), но сам
> `staff.am` — обычный Next.js SSR с открытым `robots.txt`
> (`Allow: /`, `Disallow: /*?`, но `Allow: /*?page=` — пагинация разрешена
> явно) — та же логика, что и с VK: не дёргаем закрытый бэкенд напрямую,
> только то, что сам сайт отдаёт браузеру. Next.js встраивает пропсы
> страницы в `<script id="__NEXT_DATA__">` обычным (не экранированным)
> JSON — надёжнее парсить его, чем вёрстку (список — react-native-web,
> хэшированные CSS-классы вроде `css-175oi2r`, ломаются от билда к билду).
> Категория `/en/jobs/software-development` широкая (DevOps/Mobile/
> Backend/Data вперемешку, тот же случай, что у Habr), поэтому нужен
> `is_frontend_relevant()` — **но по заголовку + структурированным hard
> skills (`skills[].type == 2`), а не по всему тексту описания**. Причина:
> поймано вживую 22.09.2026 на "Senior .Net Engineer" (обычная бэкенд
> C#/.NET-вакансия), чьи requirements заканчивались фразой "knowledge of
> TypeScript and Angular is an advantage" — при фильтре по всему описанию
> это (и несколько похожих) утекало бы в выдачу только из-за вскользь
> упомянутого "будет плюсом" технологии, точно та же ловушка, что уже
> задокументирована у SuperJob. Skills у Staff.am — теги, расставленные
> самим работодателем (hard skills type=2 отдельно от soft skills type=1
> вроде "Teamwork"), поэтому фильтр по ним намного точнее, чем по прозе.
> Зарплату Staff.am почти никогда не публикует (как и VK/Habr).

> **⚠️ HH.uz** (`hhuz_scraper.py`) — единственный источник в проекте,
> подключённый ВОПРЕКИ `robots.txt`, осознанно. Та же платформа HH Group,
> что и Zarplata.ru/HH.ru: HTML `/search/vacancy` отдаётся нормально (не
> 403, как у закрытого с апреля 2026 hh.ru), но `robots.txt` для
> `User-agent: *` содержит `Disallow: *?*` — блокирует ЛЮБОЙ URL с
> query-строкой для обычных ботов, а поиск на этой платформе только через
> `?text=&area=` и не имеет path-based альтернативы. Для `User-agent:
> Yandex` у них отдельный, более мягкий блок (`Clean-param`, без общего
> `Disallow: *?*`) — то есть площадка сознательно пускает в индекс
> конкретно Яндекс, не ботов вообще.
>
> Первое решение (22.09.2026) было не подключать — та же логика, что и с
> `trudvsem.ru`/`Ishkop.uz` ниже. Но владелец проекта прямо спросил, что
> будет "по итогу" за нарушение, и после объяснения, что `robots.txt` —
> не закон и не техническое ограничение (это добровольный протокол,
> нарушение не создаёт юридической ответственности для маленького
> некоммерческого агрегатора; реальный риск — практический: бан IP,
> не более), осознанно решил всё равно подключить источник. Компромисс —
> не фиксированные паузы между запросами (1 сек, как у остальных
> скрейперов), а случайные "человеческие" (`HUMAN_DELAY_RANGE = (2.5,
> 5.5)` сек) — это снижает нагрузку и заметность трафика, но не отменяет
> сам факт игнорирования правила. area=97 — код региона "Узбекистан
> целиком" в таксономии HH Group (проверено вживую 22.09.2026).

### Узбекистан и Армения — что ещё проверялось и отклонено

По следам того же вопроса проверены и отклонены (22.09.2026):
- **Ishkop.uz** — `robots.txt` явно запрещает `/vacansii*` для всех
  ботов, и этот путь — реальная, живая страница "все вакансии"
  (проверено: `GET /vacansii` -> 200, заголовок "Работа, вакансии в
  Узбекистане", 117 КБ контента). Списочные страницы вакансий также лежат
  под Cyrillic-путём `/вакансии/<Должность>` — тот же функционал, что и
  под запрещённым `/vacansii*`, так что дух правила однозначен: не ходить
  по вакансиям вообще. Тот же случай, что и `trudvsem.ru`.
- **ГородРабот.uz** (gorodrabot.uz) — сам является мета-агрегатором
  9 чужих источников (as-is, по их собственному описанию). Скрейпить
  агрегатор агрегаторов — тот же архитектурный тупик, что и с
  `careerist.ru` (см. историю: careerist.ru тоже отклонён именно потому,
  что re-агрегирует чужие вакансии "партнёров" без первичных прав на них).
- **job.am** (второй по популярности джоб-борд Армении) — `robots.txt`
  явно запрещает `/api/*`, `/*/api/*` (с большой и маленькой буквы), что
  само по себе не блокирует HTML-страницы вакансий, но не проверялся
  глубже: Staff.am уже даёт качественное покрытие армянского рынка
  (~80%), решили не дублировать источник ради предельного покрытия — при
  необходимости можно вернуться к этой проверке отдельно.

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

Уведомления батчатся в одно сообщение, а не по одному на вакансию.
Два независимых уровня батчинга, оба нужны — по отдельности любой из них
всё равно давал бы несколько сообщений подряд за один тик:
- **`apps/jobs/tasks.py:run_all_scrapers`** — раньше каждый источник сам по
  себе вызывал `notify_users_for_jobs.delay(...)` сразу после своего
  скрейпинга (внутри `_run_one`), так что если за один тик (раз в 30 мин)
  сразу несколько из пяти источников находили новые вакансии, подписчик
  получал бы отдельное сообщение на каждый источник. Теперь `_run_one`
  только скрейпит и возвращает stats, `run_all_scrapers` собирает
  `new_job_ids` со всех источников тика и вызывает `notify_users_for_jobs`
  один раз со всеми ID сразу. Ручной запуск одного источника
  (`run_scraper`) по-прежнему уведомляет сразу же, своим отдельным вызовом.
- **`apps/telegram_bot/tasks.py:notify_users_for_jobs`** — раньше даже
  внутри одного вызова таска слался один `send_message` на пару
  (пользователь, вакансия), то есть 10 новых вакансий, подходящих одному
  подписчику, всё равно превращались бы в 10 сообщений. Теперь вакансии
  группируются по пользователю и на каждого уходит одно сообщение:
  `format_job_message` (подробная карточка) — если подходящая вакансия
  одна, `format_jobs_batch_message` (нумерованный список, до
  `MAX_JOBS_PER_MESSAGE=15` вакансий, остаток — сводкой) — если несколько.
  `JobNotification` в БД при этом по-прежнему создаётся по одной записи на
  вакансию (нужно для `/api/jobs/notifications/` и "отметить прочитанным")
  — батчится только сама отправка в Telegram, не история уведомлений.

## REST API (Phase 4)

Публично (без авторизации):
- `GET /api/jobs/` — список, фильтры `?min_salary=&max_salary=&location=&experience_level=&job_type=&employment_type=&source=&posted_after=`, поиск `?search=`, сортировка `?ordering=-posted_at`.
  `experience_level`/`job_type`/`employment_type`/`source` — через запятую в одном
  параметре (`?source=1,3`, не `?source=1&source=3`) — см. `JobFilterSet.filter_csv_in`
  в `apps/jobs/filters.py`.
- `GET /api/jobs/<id>/`, `GET /api/jobs/sources/` (только активные — см. `JobSourceViewSet`), `GET /api/jobs/stats/`

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
