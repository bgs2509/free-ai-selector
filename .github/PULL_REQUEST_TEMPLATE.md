## Description

<!-- Краткое описание изменений (1-3 предложения) -->

## Type of Change

- [ ] Bug fix (исправление ошибки)
- [ ] New feature (новая функциональность)
- [ ] Breaking change (изменение, ломающее обратную совместимость)
- [ ] Documentation update (обновление документации)
- [ ] Refactoring (рефакторинг без изменения функциональности)

## Related Issues

<!-- Ссылки на связанные issues: Closes #123, Fixes #456 -->

---

## Code Quality Checklist

### Required

- [ ] Код соответствует [coding standards](.aidd/conventions.md)
- [ ] Type hints добавлены для всех новых функций
- [ ] Docstrings в Google-стиле для публичных функций
- [ ] `make lint` проходит без ошибок
- [ ] `make test` проходит (coverage >= 75%)

### Testing

- [ ] Unit tests добавлены для новой логики
- [ ] Integration tests обновлены (если затронуты API)
- [ ] Тесты покрывают edge cases

---

## Documentation Checklist

### При изменении кода

- [ ] Docstrings обновлены для измененных функций
- [ ] `docs/ai-context/` обновлен (если изменена архитектура)

### При изменении API

- [ ] `docs/api/business-api.md` или `docs/api/data-api.md` обновлен
- [ ] Примеры curl/Python актуальны

### При архитектурных решениях

- [ ] ADR создан в `docs/adr/` (используйте [template](docs/adr/template.md))

### При изменении провайдеров

- [ ] `docs/project/ai-providers.md` обновлен
- [ ] `docs/ai-context/SERVICE_MAP.md` обновлен

---

## Screenshots / Logs

<!-- При изменении UI или при debugging - добавьте скриншоты или логи -->

---

## Additional Notes

<!-- Любая дополнительная информация для ревьюеров -->
