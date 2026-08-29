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
| `list_issues` | заявки с фильтрами: статус, приоритет, период |
| `get_issue` | карточка заявки по id |
| `critical_issues_since` | критические заявки за N часов |
| `unanswered_issues` | заявки без ответа более N дней |
| `issue_url` | прямая ссылка на заявку в service desk |

Write-операции (`create_issue`, `add_comment`) — отдельным этапом, с human-in-the-loop.

## Конфигурация

```bash
OKDESK_DOMAIN=https://<account>.okdesk.ru
OKDESK_API_TOKEN=<token>
```

## Спецификация (TDD-контракт)

Каждый инструмент покрывается unit-тестом с замоканным `httpx`-клиентом. Контракт:

- `list_issues(status=None, priority=None, since=None) -> list[Issue]`
- `get_issue(id: int) -> Issue`
- ошибки API → типизированные исключения (`OkdeskError`), не сырой текст.

Точная схема полей `Issue` сверяется с [apidocs.okdesk.ru](https://apidocs.okdesk.ru/apidoc) на этапе имплементации — не выдумывается заранее.

## Roadmap

1. **v0** — read-only инструменты + тесты.
2. **v1** — write (создать заявку, комментарий) с approval.
3. **v2** — SQL API для аналитики (опционально).

## Лицензия

MIT
