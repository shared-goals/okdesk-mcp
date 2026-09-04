# okdesk-mcp

MCP-сервер для [Okdesk](https://okdesk.ru) — сервиса service desk. Предоставляет доступ к заявкам через Model Context Protocol.

## Видение

Тонкая, минималистичная обёртка над REST API Okdesk. **Без собственной бизнес-логики**: метрики и сценарии («критические за 24 часа», «паузы в ответах») живут в вызывающем агенте/скилле, а не здесь. Задача сервера — только отдать данные по единому контракту.

Цель — дать разработчикам Okdesk готовую точку входа в MCP-экосистему, которую они могут подхватить и развивать.

## Почему REST, а не SQL API

| | REST API | SQL API |
|---|---|---|
| Свежесть данных | real-time | раз в 4 часа |
| Авторизация | `api_token` (создаётся в UI) | письмо в саппорт + платная опция |
| Назначение | операции с заявками | BI/аналитика |

SQL API — отдельным слоем при необходимости глубокой аналитики.

## Стек

- Python 3.11+
- [`mcp`](https://github.com/modelcontextprotocol/python-sdk) — high-level API FastMCP
- `httpx`

## Инструменты (v0 — read-only)

| Tool | Назначение |
|---|---|
| `list_issues` | заявки с фильтрами: код приоритета, дата создания, дата изменения, состояние «без ответа» |
| `list_issue_priorities` | коды и определения приоритетов заявок |
| `list_issue_statuses` | статусы заявок и признак финального статуса |
| `list_issue_comments` | история комментариев заявки с автором и датой публикации |
| `get_issue` | карточка заявки по id |
| `issue_url` | прямая ссылка на заявку в service desk |

Write-операции (`create_issue`, `add_comment`) — отдельным этапом, с human-in-the-loop.
Сценарии «критические за 24 часа» и «без ответа более 48 часов» собираются
вызывающим Hermes-скиллом из `list_issues`, а не реализуются как отдельные MCP-инструменты.

`list_issues` возвращает **одну страницу** (по умолчанию 50 записей, максимум Okdesk).
Инструмент никогда не собирает историю целиком внутри себя — это защита от случайной
выгрузки тысяч заявок в контекст модели за один вызов. Вызывающая сторона (скилл) явно
запрашивает `page`/`page_size` и всегда сначала сужает выборку фильтрами
(`priority_codes`, `status_codes`, `created_since`, `without_answer`).

## Конфигурация

```bash
OKDESK_DOMAIN=https://<account>.okdesk.ru
OKDESK_API_TOKEN=<token>
```

Запросы к Okdesk всегда выполняются напрямую и не используют переменные proxy из окружения.

Для локальной отладки создайте `.env` из `.env.example`. Команда `make debug` загружает
только этот файл и использует следующие параметры отчёта:

```bash
CRITICAL_HOURS=24
UNANSWERED_HOURS=48
PAGE_SIZE=50
COMPANY_CATEGORY_ID=13
```

После изменения `.env` достаточно снова выполнить `make debug`; перезапуск Hermes не нужен.
`UNANSWERED_HOURS` показывает целевой возраст для строгой проверки в скилле: API
Okdesk возвращает только кандидатов по `without_answer`, поэтому сам debug-скрипт не
выдаёт его за окончательный фильтр.

Каждый debug-запуск показывает для всех заявок текущей страницы номер, компанию, контакт,
заголовок и время запроса. Полные ссылки печатаются отдельным списком в формате
`#TICKETID: URL`. При необходимости полный inventory доступных полей страниц
можно запросить один раз аргументом `--schema`:

```bash
make debug DEBUG_ARGS=--schema
```

Схема объединяет поля обеих выборок и выводится в формате `path: type` (например,
`contact.name: str` и `status.code: str`), без вывода полного тела заявки. Обычный
`make debug` схему не печатает.

В runtime MCP-сервера локальный `.env` не загружается. Hermes передаёт серверу
`OKDESK_DOMAIN` и `OKDESK_API_TOKEN` из `~/.hermes/.env` через конфигурацию MCP.

## Спецификация (TDD-контракт)

Каждый инструмент покрывается unit-тестом с замоканным `httpx`-клиентом. Контракт:

- `list_issues(status_codes=None, priority_codes=None, company_category_ids=None, created_since=None, updated_until=None, without_answer=None, page=1, page_size=50) -> list[Issue]` (одна страница; `page_size` не может превышать 50)
- `list_issue_priorities() -> list[Priority]`
- `list_issue_statuses() -> list[Status]`
- `list_issue_comments(issue_id: int) -> list[Comment]`
- `get_issue(id: int) -> Issue`
- ошибки API → типизированные исключения (`OkdeskError`), не сырой текст.

Точная схема полей `Issue` сверяется с [apidocs.okdesk.ru](https://apidocs.okdesk.ru/apidoc) на этапе имплементации — не выдумывается заранее.

## Roadmap

1. **v0** — read-only инструменты + тесты.
2. **v1** — write (создать заявку, комментарий) с approval.
3. **v2** — SQL API для аналитики (опционально).

## План пилота

Дев-чекаут: локально, вне `~/.hermes` (например `~/Projects/okdesk-mcp` или любой рабочий каталог).

1. Unit-тесты с замоканным `httpx` для v0-инструментов (TDD, см. контракт выше).
2. Локальная регистрация в Hermes для интеграционной проверки:
   ```bash
   hermes mcp add okdesk --command uv --args run --project <path-to-okdesk-mcp> okdesk-mcp \
     --env OKDESK_DOMAIN=https://<account>.okdesk.ru OKDESK_API_TOKEN=<token>
   hermes mcp test okdesk
   ```
   `OKDESK_API_TOKEN` создаётся вручную в Okdesk (Настройки → API, требует роль Администратор)
   и хранится только в `~/.hermes/.env` — не коммитится, не уходит в память агента.
3. Скилл-потребитель — `okdesk` в [`shared-goals/teamscore-hermes`](https://github.com/shared-goals/teamscore-hermes)
   (приватный репозиторий), пилотируется в инстансе Hermes одного из руководителей TeamScore,
   затем переезжает на общую инфраструктуру TeamScore вместе с самим сервером (те же тулы,
   свои учётные данные на стороне TeamScore).

## Лицензия

MIT
