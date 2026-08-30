## Summary / Что и зачем

<!-- One paragraph: what this closes and why this approach. -->
<!-- Одним абзацем: какую задачу закрывает и почему именно так. -->

## How to verify / Как проверить

<!-- Commands or steps: what to run, what should happen. -->
<!-- Команды или шаги: что запустить, что должно произойти. -->

## Checklist / Чеклист

- [ ] `make lint` and `make test` pass / проходят
- [ ] If models changed — there's a migration, and `alembic check` is clean
      / Если менялись модели — есть миграция, и `alembic check` чист
- [ ] If the API contract changed — `docs/API_SPEC.md` is updated
      / Если менялся контракт API — обновлён `docs/API_SPEC.md`
- [ ] Decisions and deliberate simplifications are written down in code or `docs/`
      / Принятые решения и осознанные упрощения описаны в коде или в `docs/`
