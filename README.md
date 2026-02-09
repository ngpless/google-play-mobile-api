# Google Play Mobile API Search

Drop-in замена для `google-play-scraper` с использованием мобильного API Android.

## Проблема

Оригинальная библиотека `google-play-scraper` использует веб-скрапинг:
- `play.google.com/store/` - лимит 30 результатов
- `play.google.com/work/` - до 250, но нерелевантный поиск, нет языковых флагов

## Решение

Использование мобильного API Google Play (`android.clients.google.com/fdfe/`):
- **Без лимита 30** - пагинация через `nextPageUrl`
- **Языковые флаги** - `lang` и `country` параметры работают
- **Релевантный поиск** - тот же алгоритм что в приложении Play Store

## Установка

```bash
# Зависимость
pip install -U git+https://github.com/AbhiTheModder/playstoreapi

# Или через requirements.txt
pip install -r requirements.txt
```

## Использование

### Простой вариант (drop-in replacement)

```python
# Вместо:
# from google_play_scraper import search

# Используйте:
from gplay_mobile_search import search

# Тот же интерфейс, но без лимита 30!
results = search("vpn", n_hits=100, lang="ru", country="ru")

for app in results:
    print(f"{app['title']} - {app['appId']}")
```

### Продвинутый вариант

```python
from gplay_mobile_search import MobilePlayAPI

# Инициализация с настройками
api = MobilePlayAPI(
    locale="ru_RU",
    timezone="Europe/Moscow", 
    delay=2.0  # Задержка между запросами (секунды)
)

# Анонимный логин (через Aurora Store dispenser)
api.login_anonymous()

# Или с Google аккаунтом
# api.login("email@gmail.com", "app_password")

# Поиск с пагинацией
results = api.search(
    query="vpn",
    n_hits=200,  # Получить до 200 результатов
    lang="ru",
    country="ru"
)

print(f"Найдено: {len(results)} приложений")

# Детали приложения
details = api.details("com.whatsapp")
print(details)
```

## Формат результата

Совместим с `google-play-scraper`:

```python
{
    "appId": "com.example.app",
    "title": "Example App",
    "score": 4.5,
    "developer": "Developer Name",
    "developerId": "developer_id",
    "icon": "https://...",
    "installs": "1,000,000+",
    "price": 0.0,
    "currency": "USD",
    "free": True,
    "summary": "Short description..."
}
```

## Rate Limiting

Google Play API имеет rate limiting. Решения:
1. Используйте `delay` параметр (по умолчанию 2 секунды)
2. При 429 ошибке скрипт автоматически ждёт и повторяет
3. Для массового парсинга используйте прокси

## Токены

Токены сохраняются в `~/.config/gplay_mobile_api.json` для переиспользования.
При истечении автоматически обновляются.

## Ограничения

- Требуется интернет-соединение
- Google может изменить API (но библиотека обновляется)
- Rate limiting при частых запросах

## Лицензия

MIT
