# .hours — API, staged

🇬🇧 **English** · [🇷🇺 Русский](API_SPEC.ru.md)

Same idea and the same overall model as discussed (see the appendices
below), built in pieces. Each stage is a working slice: something real runs
on the frontend after it lands. Don't look ahead to the next stage before
the current one ships — some of it is deliberately left undecided (e.g.
`building_family` doesn't exist until Stage 2), so the MVP doesn't drag in
entities it doesn't need yet.

Common to every stage: entities have `id (uuid)` and `created_at` unless
stated otherwise. Everything lives under `/api/v1`, JWT bearer everywhere
except `/auth/*`.

---

## Stage 1 — Time tracker (core)

Closes the "Tracker" screen entirely: registration, categories,
start/stop timer, today's total by category.

**User**: `email`, `password_hash`, `name`, `daily_goal_minutes`
**Category**: `user_id`, `title`, `color`, `shape`, `minutes_per_day_target`, `archived`
**TimeEntry**: `user_id`, `category_id`, `started_at`, `ended_at` (null while running), `duration_seconds`, `source` (`timer`\|`manual`)

Endpoints:
- `POST /auth/register`, `POST /auth/login`, `GET /auth/me`
- `GET/POST/PATCH /categories`, `DELETE /categories/{id}` (soft → `archived=true`)
- `POST /time-entries/start` `{category_id}` — 409 if the user already has an active entry
- `POST /time-entries/{id}/stop`
- `GET /time-entries/active`, `GET /time-entries?from=&to=`
- `GET /time-entries/summary?period=day&date=` → `{category_id: minutes}` — feeds the ring and the chips

Deliberately NOT doing yet: the city, buildings, streaks, friends,
companies, the leaderboard. `building_family` doesn't exist as a field yet.

---

## Stage 2 — Personal city + streaks

Closes the "City" screen (personal only) and the streak in the tracker's header.

Changes: `Category` gains a `building_family` field (enum: `sport` /
`study` / `work` / `creativity` / `meditation` / `reading` / `custom`).

New:
- **BuildingFamily** — not a table, just config in code (see Appendix A)
- **CityBuilding**: `owner_type` (always `'user'` for now), `owner_id`, `building_family`, `level`, `total_minutes`, `updated_at`
- **DailyProgress**: `user_id`, `date`, `total_minutes`, `goal_minutes`, `goal_met`

Endpoints:
- `GET /building-families` — the static catalog
- `GET /city/me` → `{ buildings: [...] }` (no coordinates — just a list; grid layout is deferred to Stage 7)
- `GET /users/me/stats` → `{ today_minutes, streak, longest_streak }`

Logic: on `POST /time-entries/{id}/stop`, upsert today's `DailyProgress`
(by the user's own timezone) and recompute the `level` of the `CityBuilding`
for that `building_family` using the formula from Appendix A.

---

## Stage 3 — Friends

Closes the "Friends" screen.

**Friendship**: `requester_id`, `addressee_id`, `status` (`pending`\|`accepted`\|`declined`\|`blocked`), `responded_at`

Endpoints:
- `GET /friends`
- `POST /friends/requests` `{to_user_id}`
- `GET /friends/requests?direction=incoming|outgoing`
- `POST /friends/requests/{id}/accept`, `POST /friends/requests/{id}/decline`
- `DELETE /friends/{user_id}`

---

## Stage 4 — Paired tasks

Closes the "Tasks" screen. Participants can only be picked from accepted
friends (Stage 3).

**PairedTask**: `title`, `description`, `building_family`, `created_by`, `target_minutes`, `target_type` (`combined`\|`per_participant`), `status`, `due_at`
**PairedTaskParticipant**: `paired_task_id`, `user_id`, `minutes_logged`

`TimeEntry` gains an optional `paired_task_id` field — minutes count
toward the task if it's passed at start.

Endpoints:
- `POST /paired-tasks`, `GET /paired-tasks?mine=true&status=`, `GET /paired-tasks/{id}`

---

## Stage 5 — Companies and a shared city

Only now do groups show up. Personal tracking is fully working by this
point, so this is a pure addition, not a rework.

**Company**: `name`, `slug`, `description`, `avatar_color`, `is_public`, `created_by`
**CompanyMembership**: `company_id`, `user_id`, `role` (`owner`\|`admin`\|`member`), `contribution_minutes_total`
**CompanyInvite**: `company_id`, `code`, `expires_at`, `max_uses`, `uses_count`

`CityBuilding.owner_type` starts accepting `'company'` — it grows from the
sum of every member's `TimeEntry` rows in a category of the same
`building_family`.

Endpoints:
- `POST /companies`, `GET /companies?mine=`, `GET/PATCH/DELETE /companies/{id}`
- `GET /companies/{id}/members`, `PATCH .../{user_id}` (role), `DELETE .../{user_id}`
- `POST /companies/{id}/invites`, `GET /companies/{id}/invites`, `POST /companies/join {invite_code}`
- `GET /companies/{id}/city`

Decisions made (see Appendix C):
- A user can belong to **several** companies — their minutes grow the city
  of each one, and add to the `contribution_minutes_total` of the matching
  membership.
- Minutes only accrue from the moment of joining; nothing is backfilled.
- A private company is invisible from the outside (404, not 403, so its
  existence isn't leaked); a public one is visible to anyone and
  discoverable through `GET /companies?mine=false`.
- Permissions: `member` — read only; `admin` — edit the company and
  create invites; `owner` — plus changing roles and deleting the company.
  An owner can't leave without handing off the role first;
  `DELETE /companies/{id}/members/{me}` is how you leave.
- Invites: `POST /companies/{id}/invites {expires_in_hours, max_uses}` →
  a code; an expired or used-up one returns `410`.

---

## Stage 6 — World city leaderboard

**CityScore** (a cache, recomputed by a worker/cron): `company_id`, `period` (`all_time`\|`weekly`\|`monthly`), `period_key`, `score`, `rank`

Draft formula (see Appendix C on balancing):
`score = Σ(building.level^1.5 * family_weight) + completed_paired_tasks*50 + Σ(member.longest_streak)*2`

Endpoints:
- `GET /leaderboard/companies?period=&limit=&offset=`
- `GET /leaderboard/companies/{id}?period=` → `{rank, score, total, neighbors}`

Decisions made (see Appendix C, item 2):
- `weekly`/`monthly` are **slices over the same city**, not a reset. `all_time`
  is read off the `city_buildings` cache; a period score is computed from the
  members' minutes logged inside that period (as if those were the only
  minutes that ever existed). A young company can win a week without
  catching up on `all_time` at all.
- `period_key`: `all` / `2026-W35` / `2026-08` — past periods stay readable.
- Score components: `Σ(level^1.5 * family_weight)`, plus `50` for every
  completed paired task whose participants are all company members, plus
  `2` for every day a goal was met (for `all_time`, a member's
  `longest_streak` instead). `family_weight` is `1.0` for every family
  except `custom` (`0.8`) — its progression isn't a designed one.
- Only **public** companies appear in the world leaderboard; a private
  one's `GET /leaderboard/companies/{id}` returns 404.
- `PairedTask` gains `completed_at` — without it a task can't be attributed
  to a period.
- Recomputation is lazy: `city_scores` refreshes on read once it's gone
  stale (`LEADERBOARD_TTL_SECONDS`, default 300). There is no public
  recompute endpoint — `recompute_scores()` is called directly and will
  move to Celery beat later.

---

## Stage 7 — Isometric city layout

Only once the frontend actually picks up the pseudo-3D view. A pure field
addition, breaks nothing from earlier stages.

**CityDistrict** (a static catalog): `key`, `building_family` (null = a shared zone), `title`, `grid_x`, `grid_y`, `grid_w`, `grid_h`
`CityBuilding` gains: `district_id`, `position_x`, `position_y`, `rotation`, `variant`

Endpoint: `GET /city/districts`

Decisions made:
- The district catalog lives in code (`app/city_districts.py`), like
  building families, and is synced into the `city_districts` table — the
  table exists only so `CityBuilding.district_id` is an honest foreign
  key. The sync is idempotent and happens on read, so code and table
  can't drift apart.
- Layout is **deterministic from the building's `id`**: the district
  follows from the family, and the exact tile, rotation, and `variant`
  come from a hash of the `id`. A city renders identically on every
  client and after every restart, while two cities holding the same
  buildings don't look like twins. No layout-algorithm state needs to be
  stored anywhere.
- Layout is assigned once, at creation, and never changes again — a level
  upgrade never moves a building on the map.
- Buildings created before Stage 7 are backfilled lazily when
  `GET /city/me` or `GET /companies/{id}/city` is read.
- `position_x/y` are absolute grid coordinates, not an offset inside the
  district — the frontend doesn't have to add them to `grid_x/grid_y`
  itself.
- The centre holds a shared `plaza` with no family; districts never
  overlap (a test asserts this).

---

## Stage 8 — Feed and profile (built out of order)

Wasn't part of the original vision — added by a separate request: a
social feed of posts (post, view, like, comment) and a public profile.
Independent of Stages 5–7, changes nothing in them.

`User` gains `avatar_color` (assigned deterministically from the email at
registration) and `status` (a short profile status).

**Post**: `author_id`, `text`, `likes_count`, `comments_count` (cached, incremented on like/comment), `created_at`
**PostLike**: `post_id`, `user_id` — a unique pair
**Comment**: `post_id`, `author_id`, `text`, `created_at`

Endpoints:
- `POST /posts` `{text}`
- `GET /posts?author_id=&limit=&offset=` — without `author_id` this is the global feed (every post, newest first); with `author_id` it's one profile's posts
- `GET /posts/{id}`, `DELETE /posts/{id}` (author only)
- `POST /posts/{id}/like` (409 if already liked), `DELETE /posts/{id}/like` (404 if not liked)
- `GET /posts/{id}/comments`, `POST /posts/{id}/comments` `{text}`
- `DELETE /comments/{id}` (author only)

`GET /users/{id}` now returns `UserPublic` (no email — an email is only
ever visible to its own owner, through `/users/me` and `/auth/me`). The
frontend assembles a profile from `GET /users/{id}` + `GET /posts?author_id={id}`.

---

## Appendix A — building levels

The threshold is total hours in a category. Shared between a personal and
a company city (only whose hours get summed differs).

| Family | Lvl 1 (0h) | Lvl 2 (10h) | Lvl 3 (30h) | Lvl 4 (80h) | Lvl 5 (150h) |
|---|---|---|---|---|---|
| `sport` | Playground | Gym | Sports school | Stadium | Olympic complex |
| `study` | Classroom | School | Library | University | Institute |
| `work` | Garage startup | Office | Business centre | Tech park | Headquarters |
| `creativity` | Workshop | Studio | Gallery | Theatre | Cultural quarter |
| `meditation` | Quiet corner | Garden | Temple | Retreat centre | Mountain of enlightenment |
| `reading` | Bookshelf | Reading room | Library | Book quarter | National library |

## Appendix B — sample response

```json
// GET /city/me (Stage 2, no coordinates)
{
  "buildings": [
    { "id": "b1", "building_family": "work", "level": 4, "total_minutes": 5760 }
  ]
}
```

## Appendix C — open questions

Don't block Stages 1–4, but settle before Stage 5–6:

1. One company per user, or several? (the model sketched above assumes one)
2. Is the `weekly`/`monthly` ranking a different score slice over the same
   city, or does the city visually "reset" between periods?
3. A paired task outside a company — whose city does the building go to:
   the initiator's, both personal cities, or a separate monument that
   belongs to no one?
4. Do public, open-join companies belong in an early stage, or invite-code
   only for now?
5. `building_family = custom` — what's its level progression?
