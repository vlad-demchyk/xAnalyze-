# XAnalyze (Українська)

Десктопний та headless аналізатор: виявлення AI-згенерованого тексту, символів без клавіатури та повний аудит доступності сайту/репозиторію.

[English](README.md) | [Italiano](README_it.md)

---

## Можливості

- **Виявлення AI-патернів** — евристичний (кліше, структурні патерни) та на основі embeddings (sentence-transformers)
- **Символи без клавіатури** — zero-width пробіли, curly quotes, em dash, homoglyphs
- **Аудит доступності** — правила WCAG, SEO, продуктивність, найкращі практики (40+ правил)
- **Повне сканування** — AI-патерни + доступність в одній команді
- **Стилізовані звіти** — брендовані PDF/HTML для людей
- **Брифінги для агентів** — markdown/JSON для coding agents
- **CLI + GUI** — один бінарник, два інтерфейси

## Швидкий старт

### GUI (macOS)

```bash
curl -L -o XAnalyze.app.zip https://github.com/vlad-demchyk/xAnalyze-/releases/latest/download/XAnalyze.app.zip
unzip XAnalyze.app.zip
mv XAnalyze.app /Applications/
```

### CLI (macOS/Linux)

```bash
curl -L -o xanalyze https://github.com/vlad-demchyk/xAnalyze-/releases/latest/download/xanalyze
chmod +x xanalyze
sudo mv xanalyze /usr/local/bin/xanalyze
```

### З вихідного коду

```bash
git clone https://github.com/vlad-demchyk/xAnalyze-.git
cd xAnalyze-
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# GUI
python main.py

# CLI
python cli.py fullscan https://example.com --json
```

## Команди CLI

| Команда | Опис |
|---|---|
| `xanalyze scan` | Звіт про знахідки без зміни файлів |
| `xanalyze fix` | Перезаписати символи без клавіатури |
| `xanalyze audit` | Аудит URL/папки: доступність, SEO, продуктивність |
| `xanalyze fullscan` | Комбіновано: AI-патерни + доступність + звіти |
| `xanalyze compare` | Порівняти детектори на одних файлах |
| `xanalyze cache` | Управління кешем сканування |
| `xanalyze ai` | Операції з AI-провайдерами |
| `xanalyze clean` | Фільтр тексту з stdin до stdout |

## Приклади

```bash
# Повне сканування зі звітами
xanalyze fullscan https://example.com \
  --styled-report report.html \
  --report agent-briefing.md \
  --json

# Тільки AI-патерни
xanalyze scan ./src --detector offline --scope both --json

# Аудит доступності
xanalyze audit https://example.com --browser --breakpoints all
```

## Детектори

| Детектор | Тип | Вартість |
|---|---|---|
| `offline` | Евристичний (кліше + символи) | Безкоштовно |
| `embedding` | Семантична схожість (sentence-transformers) | Безкоштовно |
| `claude-llm-judge` | LLM-as-judge (Anthropic API) | Платно |
| `xformat-llm-judge` | LLM-as-judge (підписка xFormat) | Платно |
| `hybrid` | Offline + LLM judge | Платно |

## Видалення

### CLI

```bash
rm /usr/local/bin/xanalyze
# або якщо встановлено в ~/bin:
rm ~/bin/xanalyze
```

### GUI

```bash
rm -rf /Applications/XAnalyze.app
```

### Конфіг та кеш

```bash
rm -rf ~/.config/xanalyze
rm -rf ~/.xanalyze
```

## Вимоги

- Python 3.9+
- PySide6 (для GUI)
- sentence-transformers (для embedding детектора)

## Ліцензія

MIT
