# .hours

[![CI](https://github.com/i-safonoff/dothours/actions/workflows/ci.yml/badge.svg)](https://github.com/i-safonoff/dothours/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[🇬🇧 English](README.md) · 🇷🇺 **Русский**

**Трекер времени, который превращает потраченные часы в город.**

Каждая категория, в которой вы трекаете время, растит своё здание: учёба —
школы и библиотеки, спорт — залы и стадионы. Друзья подталкивают друг друга
общими заданиями, компании строят общий город, а лучшие города попадают в
мировой топ. Геймификация — не украшение поверх трекера, а сама причина
открыть приложение завтра.

Это бэкенд-часть проекта: REST API + WebSocket. Полный план по этапам —
[`docs/API_SPEC.md`](docs/API_SPEC.ru.md); реализованы все этапы.

---

## Содержание

- [Возможности](#возможности)
- [Стек](#стек)
- [Быстрый старт](#быстрый-старт)
- [Локальная разработка](#локальная-разработка)
- [Обзор API](#обзор-api)
- [Мониторинг](#мониторинг)
- [Структура проекта](#структура-проекта)
- [Тесты и качество](#тесты-и-качество)
- [Документация](#документация)
- [Что дальше](#что-дальше)

---

## Возможности

| Что | Как это работает |
|---|---|
| **Аутентификация** | Регистрация, вход, JWT-bearer; цвет аватара назначается детерминированно от email |
| **Категории** | CRUD, у каждой — семейство зданий, цвет, форма и дневная цель |
| **Трекер** | Старт/стоп таймера, ручные записи, сводка за день по категориям |
| **Личный город** | Здание растёт от суммарных часов в категории и повышает уровень по таблице порогов |
| **Стрики** | Считаются по дням, в которые дневная цель закрыта |
| **Друзья** | Заявки, принятие/отклонение, список друзей с их сегодняшними минутами |
| **Парные задания** | Совместные челленджи; засчитываются по сумме или каждому участнику отдельно |
| **Лента и профили** | Посты, лайки, комментарии, публичный профиль без утечки email |
| **Компании** | Роли `owner`/`admin`/`member`, инвайт-коды, общий город из минут всех участников |
| **Мировой топ** | Кэшированные счёта городов: `all_time`, `weekly`, `monthly` |
| **Изораскладка** | Районы и детерминированные координаты, поворот и вариант каждого здания |
| **Уведомления** | Входящие в приложении: напоминания и предупреждения о стрике по времени пользователя |
| **Реалтайм** | WebSocket с событиями таймера, города, друзей, заданий и уведомлений |
| **Мониторинг** | `/metrics` для Prometheus и готовый дашборд Grafana |

## Стек

- **FastAPI** + **SQLAlchemy 2.0** (синхронная сессия) + **PostgreSQL**
- **Alembic** — миграции
- **JWT** (PyJWT + bcrypt) — аутентификация
- **Celery** + **Redis** — фоновые задачи и реалтайм pub/sub
- **Prometheus** + **Grafana** — метрики и дашборды
- **pytest** — тесты на SQLite в памяти, внешние сервисы не нужны
- **ruff** — линт и форматирование
- **Docker Compose** — весь стек одной командой

## Быстрый старт

```bash
git clone https://github.com/i-safonoff/dothours.git
cd dothours
cp .env.example .env
make up
```

Поднимутся API, PostgreSQL, Redis, Celery worker и beat. Миграции накатятся
автоматически при старте.

- API — http://localhost:8000
- Интерактивная документация — http://localhost:8000/docs
- Проверка живости — http://localhost:8000/health

Вместе с мониторингом:

```bash
make stack-up
```

- Prometheus — http://localhost:9090
- Grafana — http://localhost:3000 (`admin` / `admin`, дашборд «.hours API» уже на месте)

## Локальная разработка

Нужны Python 3.11+, [Poetry](https://python-poetry.org/) и запущенные
PostgreSQL с Redis (проще всего `docker compose up -d db redis`).

```bash
make install
cp .env.example .env        # DATABASE_URL укажите на localhost, а не на db
make migrate
make run                    # API с автоперезагрузкой
```

Фоновые задачи — в отдельных терминалах:

```bash
make worker
make beat
```

Все команды — `make help`. Перед первым коммитом стоит поставить хуки:

```bash
poetry run pre-commit install
```

### Переменные окружения

| Переменная | По умолчанию | Зачем |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg2://…@db:5432/dothours` | Подключение к БД |
| `JWT_SECRET_KEY` | — | Подпись токенов; **обязательно поменяйте** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `10080` | Время жизни токена |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Разрешённые источники |
| `CELERY_BROKER_URL` | `redis://redis:6379/0` | Брокер Celery |
| `WS_BACKEND` | `memory` | `redis` — фан-аут между процессами, `memory` — внутри одного |
| `LEADERBOARD_TTL_SECONDS` | `300` | Как долго отдаётся кэш лидерборда |
| `METRICS_ENABLED` | `true` | Включает `/metrics` |

## Обзор API

Всё под `/api/v1`, всё кроме `/auth/*` требует заголовок `Authorization: Bearer <token>`.

| Группа | Эндпоинты |
|---|---|
| Аутентификация | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` |
| Профиль | `GET/PATCH /users/me`, `GET /users/me/stats`, `GET /users/search`, `GET /users/{id}` |
| Категории | `GET/POST /categories`, `PATCH/DELETE /categories/{id}` |
| Трекер | `POST /time-entries/start`, `POST /time-entries/{id}/stop`, `GET /time-entries`, `GET /time-entries/summary` |
| Город | `GET /city/me`, `GET /city/districts`, `GET /building-families` |
| Друзья | `GET /friends`, `POST /friends/requests`, `POST /friends/requests/{id}/accept` |
| Парные задания | `POST /paired-tasks`, `GET /paired-tasks`, `GET /paired-tasks/{id}` |
| Лента | `POST/GET /posts`, `POST/DELETE /posts/{id}/like`, `GET/POST /posts/{id}/comments` |
| Компании | `POST/GET /companies`, `POST /companies/join`, `GET /companies/{id}/members`, `GET /companies/{id}/city` |
| Топ | `GET /leaderboard/companies`, `GET /leaderboard/companies/{id}` |
| Уведомления | `GET /notifications`, `POST /notifications/{id}/read`, `POST /notifications/read-all` |
| Реалтайм | `GET /ws?token=<JWT>` |

Полное описание с телами запросов — в OpenAPI на `/docs`.

## Мониторинг

`GET /metrics` отдаёт метрики Prometheus: RED-метрики по HTTP плюс доменные —
натреканные минуты по семействам зданий, старты и остановки таймеров,
апгрейды зданий, открытые сокеты, запуски и длительность Celery-задач.
Каждый ответ несёт `X-Request-ID`, а на каждый запрос пишется JSON-строка лога.

Подробности и таблица метрик — [`docs/OBSERVABILITY.md`](docs/OBSERVABILITY.ru.md).

## Структура проекта

```
app/
  api/routes/           HTTP-ручки, по модулю на ресурс
  services/             бизнес-логика поверх сессии БД
  models/               ORM-модели
  schemas/               Pydantic-контракты
  worker/                Celery: jobs.py — логика, tasks.py — обёртки
  events/                шина реалтайм-событий
  core/                  настройки, БД, JWT, метрики, логи, таймзоны
  building_families.py   каталог уровней зданий (конфиг, не таблица)
  city_districts.py      каталог районов, синкается в city_districts
alembic/                 миграции
ops/                     конфиг Prometheus и провижининг Grafana
tests/                   pytest, по файлу на ресурс
docs/                    спецификация и архитектурные заметки
```

## Тесты и качество

```bash
make test     # pytest на SQLite в памяти
make lint     # ruff check + format --check
make cov      # покрытие с HTML-отчётом
```

Тестов — 95, покрытие ~94%. Внешние сервисы для прогона не нужны: тесты
работают на SQLite в памяти, фоновые задачи вызываются напрямую с подставленным
«сейчас», а реалтайм — через внутрипроцессную шину.

CI на каждый PR прогоняет линт, тесты, сборку Docker-образа и отдельную
проверку миграций на настоящем PostgreSQL: по одной ревизии за раз, плюс
`alembic check` и полный цикл downgrade/upgrade. Это ловит ошибки, которые не
видны на чистой базе, — например, повторное создание уже существующего типа.

## Документация

| Документ | О чём |
|---|---|
| [`docs/API_SPEC.md`](docs/API_SPEC.ru.md) | Спецификация по этапам и принятые решения |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.ru.md) | Схема системы, слои, ключевые размены |
| [`docs/REALTIME.md`](docs/REALTIME.ru.md) | WebSocket: протокол, события, каналы |
| [`docs/NOTIFICATIONS.md`](docs/NOTIFICATIONS.ru.md) | Уведомления и расписание фоновых задач |
| [`docs/OBSERVABILITY.md`](docs/OBSERVABILITY.ru.md) | Метрики, логи, Prometheus и Grafana |
| [`CONTRIBUTING.md`](CONTRIBUTING.ru.md) | Как вести разработку в этом репозитории |

## Что дальше

- Внешние каналы уведомлений: почта и пуши поверх уже существующих строк
- Кэш стриков, когда чтение упрётся в производительность
- Экспортер Redis и алерты в Prometheus — когда появятся внятные SLO
- Трейсинг (OpenTelemetry), если сервис вырастет из метрик и логов

## Лицензия

[MIT](LICENSE)
