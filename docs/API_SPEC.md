# .hours — API по этапам

Идея и общая модель — те же, что обсуждали (см. приложения ниже), но реализуем
по кускам. Каждый этап — рабочий срез: после него что-то реальное крутится на
фронте. Не заглядывай в следующий этап, пока текущий не поехал — там
специально не всё продумано заранее (например, `building_family` появляется
только в Этапе 2), чтобы не тащить в MVP сущности, которые пока не нужны.

Общее для всех этапов: у сущностей есть `id (uuid)` и `created_at`, если явно
не написано иное. Всё под `/api/v1`, JWT bearer кроме `/auth/*`.

---

## Этап 1 — Трекер времени (ядро)

Закрывает экран "Трекер" целиком: регистрация, категории, старт/стоп таймера,
сегодняшняя сумма по категориям.

**User**: `email`, `password_hash`, `name`, `daily_goal_minutes`
**Category**: `user_id`, `title`, `color`, `shape`, `minutes_per_day_target`, `archived`
**TimeEntry**: `user_id`, `category_id`, `started_at`, `ended_at` (null пока идёт), `duration_seconds`, `source` (`timer`\|`manual`)

Эндпоинты:
- `POST /auth/register`, `POST /auth/login`, `GET /auth/me`
- `GET/POST/PATCH /categories`, `DELETE /categories/{id}` (soft → `archived=true`)
- `POST /time-entries/start` `{category_id}` — 409, если уже есть активная запись у юзера
- `POST /time-entries/{id}/stop`
- `GET /time-entries/active`, `GET /time-entries?from=&to=`
- `GET /time-entries/summary?period=day&date=` → `{category_id: minutes}` — питает кольцо и чипы

Сознательно НЕ делаем: город, здания, стрик, друзья, компании, топ.
`building_family` как поле пока не существует.

---

## Этап 2 — Личный город + стрик

Закрывает экран "Город" (только личный) и стрик в шапке трекера.

Изменения: `Category` получает поле `building_family` (enum: `sport` /
`study` / `work` / `creativity` / `meditation` / `reading` / `custom`).

Новое:
- **BuildingFamily** — не таблица, просто конфиг в коде (см. Приложение А)
- **CityBuilding**: `owner_type` (пока всегда `'user'`), `owner_id`, `building_family`, `level`, `total_minutes`, `updated_at`
- **DailyProgress**: `user_id`, `date`, `total_minutes`, `goal_minutes`, `goal_met`

Эндпоинты:
- `GET /building-families` — статический каталог
- `GET /city/me` → `{ buildings: [...] }` (без координат — просто список, раскладку на сетке отложим до Этапа 7)
- `GET /users/me/stats` → `{ today_minutes, streak, longest_streak }`

Логика: в `POST /time-entries/{id}/stop` — апсертишь `DailyProgress` за
сегодня (по таймзоне юзера) и пересчитываешь `level` у `CityBuilding` этой
`building_family` по формуле из Приложения А.

---

## Этап 3 — Друзья

Закрывает экран "Друзья".

**Friendship**: `requester_id`, `addressee_id`, `status` (`pending`\|`accepted`\|`declined`\|`blocked`), `responded_at`

Эндпоинты:
- `GET /friends`
- `POST /friends/requests` `{to_user_id}`
- `GET /friends/requests?direction=incoming|outgoing`
- `POST /friends/requests/{id}/accept`, `POST /friends/requests/{id}/decline`
- `DELETE /friends/{user_id}`

---

## Этап 4 — Парные задания

Закрывает экран "Задания". Участники берутся только из принятых друзей (Этап 3).

**PairedTask**: `title`, `description`, `building_family`, `created_by`, `target_minutes`, `target_type` (`combined`\|`per_participant`), `status`, `due_at`
**PairedTaskParticipant**: `paired_task_id`, `user_id`, `minutes_logged`

`TimeEntry` получает необязательное поле `paired_task_id` — минуты идут в
зачёт задания, если передано при старте.

Эндпоинты:
- `POST /paired-tasks`, `GET /paired-tasks?mine=true&status=`, `GET /paired-tasks/{id}`

---

## Этап 5 — Компании и общий город

Только теперь заводим группы. Личный трекинг к этому моменту уже полностью
рабочий, так что это чисто добавка, а не переделка.

**Company**: `name`, `slug`, `description`, `avatar_color`, `is_public`, `created_by`
**CompanyMembership**: `company_id`, `user_id`, `role` (`owner`\|`admin`\|`member`), `contribution_minutes_total`
**CompanyInvite**: `company_id`, `code`, `expires_at`, `max_uses`, `uses_count`

`CityBuilding.owner_type` начинает принимать значение `'company'` — растёт от
суммы `TimeEntry` всех участников по категории того же `building_family`.

Эндпоинты:
- `POST /companies`, `GET /companies?mine=`, `GET/PATCH/DELETE /companies/{id}`
- `GET /companies/{id}/members`, `PATCH .../{user_id}` (роль), `DELETE .../{user_id}`
- `POST /companies/{id}/invites`, `GET /companies/{id}/invites`, `POST /companies/join {invite_code}`
- `GET /companies/{id}/city`

Принятые решения (см. Приложение В):
- Пользователь может состоять в **нескольких** компаниях — минуты идут в город
  каждой из них и в `contribution_minutes_total` соответствующего членства.
- Минуты начисляются только с момента вступления, задним числом ничего не
  пересчитывается.
- Приватная компания невидима извне (404 вместо 403, чтобы не палить
  существование), публичная видна всем и находится через `GET /companies?mine=false`.
- Права: `member` — только чтение; `admin` — правка компании и инвайты;
  `owner` — плюс смена ролей и удаление. Владелец не может выйти, не передав
  роль; `DELETE /companies/{id}/members/{me}` — это «выйти».
- Инвайт: `POST /companies/{id}/invites {expires_in_hours, max_uses}` → код;
  протухший или исчерпанный отдаёт `410`.

---

## Этап 6 — Мировой топ городов

**CityScore** (кэш, пересчитывается воркером/кроном): `company_id`, `period` (`all_time`\|`weekly`\|`monthly`), `period_key`, `score`, `rank`

Черновая формула (см. Приложение В про баланс):
`score = Σ(building.level^1.5 * family_weight) + completed_paired_tasks*50 + Σ(member.longest_streak)*2`

Эндпоинты:
- `GET /leaderboard/companies?period=&limit=&offset=`
- `GET /leaderboard/companies/{id}?period=` → `{rank, score, total, neighbors}`

Принятые решения (см. Приложение В, п.2):
- `weekly`/`monthly` — это **срезы поверх одного и того же города**, город не
  обнуляется. `all_time` считается по кэшу `city_buildings`, а периодный счёт —
  по минутам участников внутри периода (уровень считается так, будто только эти
  минуты и были). Молодая компания может выиграть неделю, не догнав никого по
  `all_time`.
- `period_key`: `all` / `2026-W35` / `2026-08` — прошлые периоды остаются
  читаемыми.
- Компоненты счёта: `Σ(level^1.5 * family_weight)` + `50` за каждое завершённое
  парное задание, все участники которого состоят в компании, + `2` за
  каждый день выполненной цели (в `all_time` — за `longest_streak` участника).
  `family_weight` = 1.0 у всех семейств, кроме `custom` (0.8) — у него
  прогрессия не спроектирована продуктом.
- В мировом топе участвуют **только публичные** компании; у приватной
  `GET /leaderboard/companies/{id}` отдаёт 404.
- `PairedTask` получает `completed_at` — без него нельзя отнести задание к периоду.
- Пересчёт ленивый: `city_scores` обновляются на чтении, если протухли
  (`LEADERBOARD_TTL_SECONDS`, по умолчанию 300). Публичной ручки пересчёта нет —
  `recompute_scores()` вызывается напрямую и позже уедет в Celery beat.

---

## Этап 7 — Изометрическая раскладка города

Только когда фронт реально возьмётся за псевдо-3D вид. Чисто добавка полей,
ничего из предыдущих этапов не ломает.

**CityDistrict** (статический каталог): `building_family` (null = общая зона), `title`, `grid_x`, `grid_y`, `grid_w`, `grid_h`
`CityBuilding` получает: `district_id`, `position_x`, `position_y`, `rotation`, `variant`

Эндпоинт: `GET /city/districts`

---

## Этап 8 — Лента и профиль (реализовано вне очереди)

Не было в исходном видении, добавлено по отдельному запросу — социальная
лента постов (постить, смотреть, лайкать, комментировать) и публичный
профиль. Независимо от Этапов 5–7, ничего в них не меняет.

`User` получает поля `avatar_color` (назначается детерминированно от email
при регистрации) и `status` (короткий статус в профиле).

**Post**: `author_id`, `text`, `likes_count`, `comments_count` (кэш, инкрементируются на лайке/комментарии), `created_at`
**PostLike**: `post_id`, `user_id` — уникальная пара
**Comment**: `post_id`, `author_id`, `text`, `created_at`

Эндпоинты:
- `POST /posts` `{text}`
- `GET /posts?author_id=&limit=&offset=` — без `author_id` это глобальная лента (все посты, новые сверху); с `author_id` — посты для конкретного профиля
- `GET /posts/{id}`, `DELETE /posts/{id}` (только автор)
- `POST /posts/{id}/like` (409, если уже лайкнул), `DELETE /posts/{id}/like` (404, если не лайкал)
- `GET /posts/{id}/comments`, `POST /posts/{id}/comments` `{text}`
- `DELETE /comments/{id}` (только автор)

`GET /users/{id}` теперь отдаёт `UserPublic` (без email — email виден только
самому себе через `/users/me` и `/auth/me`). Профиль пользователя на фронте
собирается из `GET /users/{id}` + `GET /posts?author_id={id}`.

---

## Приложение А — уровни зданий

Порог — суммарные часы в категории. Общий для личного и компанейского города
(отличается только то, чьи часы суммируются).

| Семейство | Ур.1 (0ч) | Ур.2 (10ч) | Ур.3 (30ч) | Ур.4 (80ч) | Ур.5 (150ч) |
|---|---|---|---|---|---|
| `sport` | Спортплощадка | Тренажёрный зал | Спортшкола | Стадион | Олимпийский комплекс |
| `study` | Класс | Школа | Библиотека | Университет | Институт |
| `work` | Гараж-стартап | Офис | Бизнес-центр | Технопарк | Штаб-квартира |
| `creativity` | Мастерская | Студия | Галерея | Театр | Культурный квартал |
| `meditation` | Уголок тишины | Сад | Храм | Ретрит-центр | Гора просветления |
| `reading` | Книжная полка | Читальня | Библиотека | Книжный квартал | Нац. библиотека |

## Приложение Б — пример ответа

```json
// GET /city/me (Этап 2, без координат)
{
  "buildings": [
    { "id": "b1", "building_family": "work", "level": 4, "total_minutes": 5760 }
  ]
}
```

## Приложение В — открытые вопросы

Не блокируют Этапы 1–4, но реши до Этапа 5–6:

1. Одна компания на пользователя или несколько? (модель выше предполагает одну)
2. `weekly`/`monthly` рейтинг — это разные срезы очков поверх одного и того же
   города, или город визуально "обнуляется" между периодами?
3. Парное задание вне компании — здание в чей город идёт: инициатора, в оба
   личных, или отдельный монумент вне чьих-либо городов?
4. Нужны ли публичные компании с открытым вступлением на раннем этапе, или
   только по инвайт-коду?
5. `building_family = custom` — какая у него прогрессия уровней?
