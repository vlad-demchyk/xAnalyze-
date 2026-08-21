# XAnalyze (Українська)

Десктопний та headless аналізатор: виявлення AI-згенерованого тексту, символів без клавіатури та повний аудит доступності сайту/репозиторію.

[English](README.md) | [Italiano](README_it.md)

---

## Зміст

- [Можливості](#можливості)
- [Швидкий старт](#швидкий-старт)
- [Команди CLI](#команди-cli)
  - [fullscan](#fullscan---повне-сканування)
  - [scan](#scan---виявлення-ai-патернів)
  - [audit](#audit---доступність-seo-продуктивність)
  - [fix](#fix---застосування-виправлень)
  - [undo](#undo---скасування-виправлень)
  - [cache](#cache---управління-кешем)
  - [compare](#compare---порівняння-детекторів)
  - [ai](#ai---ai-операції)
  - [clean](#clean---фільтр-тексту)
  - [serve](#serve---локальний-http-сервер)
- [Методи детекції](#методи-детекції)
  - [Виявлення AI-патернів](#виявлення-ai-патернів)
  - [Символи без клавіатури](#символи-без-клавіатури)
  - [Аудит доступності](#аудит-доступності)
  - [Аудит SEO](#аудит-seo)
  - [Аудит продуктивності](#аудит-продуктивності)
  - [Найкращі практики](#найкращі-практики)
  - [Браузерний прохід](#браузерний-прохід)
- [Детектори](#детектори)
- [Звіти](#звіти)
- [Для AI агентів](#для-ai-агентів)
- [GUI](#gui)
- [Конфігурація](#конфігурація)
- [Видалення](#видалення)
- [Вимоги](#вимоги)
- [Ліцензія](#ліцензія)

---

## Можливості

- **Виявлення AI-патернів** — евристичний (кліше, структурні патерни, burstiness) та на основі embeddings (sentence-transformers)
- **Символи без клавіатури** — zero-width пробіли, curly quotes, em dash, homoglyphs
- **Аудит доступності** — правила WCAG, SEO, продуктивність, найкращі практики (49 правил)
- **Повне сканування** — AI-патерни + доступність в одній команді з автоматичним браузерним рендерингом
- **Стилізовані звіти** — брендовані PDF/HTML для людей
- **Брифінги для агентів** — markdown/JSON для coding agents
- **CLI + GUI** — один бінарник, два інтерфейси
- **Responsive аудит** — тестування на desktop, tablet та mobile ширині
- **Браузерний рендеринг** — реальний Chromium для клієнт-рендер сайтів (React, Vue, Next.js)

---

## Швидкий старт

### GUI (macOS)

```bash
curl -L -o XAnalyze.app.zip https://github.com/vlad-demchyk/xAnalyze-/releases/latest/download/XAnalyze.app.zip
unzip XAnalyze.app.zip
mv XAnalyze.app /Applications/
```

### CLI (macOS/Linux)

```bash
curl -L -o xanalyze-cli.tar.gz https://github.com/vlad-demchyk/xAnalyze-/releases/latest/download/xanalyze-cli-macos-arm64.tar.gz
tar -xzf xanalyze-cli.tar.gz
echo 'export PATH="$PWD/xanalyze:$PATH"' >> ~/.zshrc
source ~/.zshrc
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
python cli.py fullscan https://example.com
```

---

## Команди CLI

### `fullscan` - Повне сканування

Основна команда для комплексного аналізу. Поєднує виявлення AI-патернів, аудит доступності, SEO, продуктивність та найкращі практики в одному запуску.

**Автоматична поведінка для URL та HTML файлів:**
- Браузерний рендеринг увімкнено (обробляє React, Vue, Next.js тощо)
- Responsive breakpoints: desktop (1440px), tablet (834px), mobile (390px)
- JSON вивід для агента
- Стилізований PDF звіт зберігається в `~/Desktop`
- Брифінг для агента (Markdown) зберігається в `~/Desktop`

```bash
# Повне сканування сайту (все автоматично)
xanalyze fullscan https://xformat.net

# Повне сканування локального репозиторію (без браузера)
xanalyze fullscan ./my-project

# Тільки desktop breakpoint
xanalyze fullscan https://example.com --breakpoints desktop

# Desktop + mobile (без tablet)
xanalyze fullscan https://example.com --breakpoints desktop,mobile

# З глибиною кравлінгу
xanalyze fullscan https://example.com --depth 2 --max-pages 50

# Власні шляхи звітів
xanalyze fullscan https://example.com \
  --styled-report ./reports/site.pdf \
  --report ./reports/agent.md

# Звіти українською
xanalyze fullscan https://example.com --language uk
```

**Опції:**

| Опція | Опис |
|---|---|
| `target` | URL, директорія або `.html` файл |
| `--url` | Трактувати target як URL навіть без схеми |
| `--depth N` | Глибина кравлінгу (за замовчуванням: 0) |
| `--max-pages N` | Максимум сторінок (за замовчуванням: 30) |
| `--max-files N` | Максимум файлів (за замовчуванням: 5000) |
| `--ext ...` | Розширення файлів для сканування |
| `--exclude PATTERN` | Gitignore-стиль патерн виключення (повторюваний) |
| `--no-default-excludes` | Не пропускати `node_modules/`, `dist/`, `.git/` тощо |
| `--detector DETECTOR` | Детектор AI-патернів: `offline`, `embedding`, `hybrid`, `llm-judge` |
| `--scope SCOPE` | Що читати: `content`, `technical`, `both` |
| `--no-typography` | Не чіпати em dash та curly quotes |
| `--breakpoints NAMES` | Responsive breakpoints: `all`, `desktop`, `tablet`, `mobile` |
| `--styled-report PATH` | Шлях до брендованого PDF/HTML звіту |
| `--report PATH` | Шлях до брифінгу для агента (.md або .json) |
| `--check` | Вихід 1 при критичних/серйозних проблемах |
| `--language LANG` | Мова звітів: `uk`, `it`, `en` |
| `--agent` | Запустити сервер агент-судді (без API ключа) |
| `--agent-port PORT` | Порт сервера агент-судді (за замовчуванням: 8765) |

---

### `scan` - Виявлення AI-патернів

Сканує файли на наявність AI-згенерованого тексту та символів без клавіатури без їх зміни.

```bash
# Сканувати директорію
xanalyze scan ./src

# З конкретним детектором
xanalyze scan ./src --detector offline

# Тільки контент (не коментарі)
xanalyze scan ./src --scope content

# JSON вивід для CI/CD
xanalyze scan ./src --json --check

# Інкрементальне сканування (тільки змінені файли)
xanalyze scan ./src --incremental

# Стилізований звіт
xanalyze scan ./src --styled-report report.pdf --language uk
```

**Опції:**

| Опція | Опис |
|---|---|
| `paths` | Файли або директорії для сканування |
| `--ext ...` | Розширення (за замовчуванням: `.html .htm .xml .jsx .tsx .vue .svelte .js .ts .mjs .cjs`) |
| `--exclude PATTERN` | Додатковий gitignore-стиль патерн |
| `--no-default-excludes` | Не пропускати `node_modules/`, `dist/` тощо |
| `--max-files N` | Максимум файлів |
| `--detector DETECTOR` | Детектор контенту (див. [Детектори](#детектори)) |
| `--provider PROVIDER` | AI провайдер: `anthropic`, `xformat`, `claude-code` |
| `--no-unicode` | Пропустити перевірку символів без клавіатури |
| `--scope SCOPE` | `content` (користувацький контент), `technical` (коментарі), `both` |
| `--categories CATS` | Через кому: `invisible,space,homoglyph,styled,typography` |
| `--no-typography` | Не чіпати em dash та curly quotes |
| `--no-ignore` | Звітувати все, включаючи придушені знахідки |
| `--json` | JSON вивід |
| `--check` | Вихід 1 при знахідках (для hooks та CI) |
| `--incremental` | Тільки файли змінені з останнього сканування |
| `--styled-report PATH` | брендований PDF/HTML звіт |
| `--language LANG` | Мова звіту: `uk`, `it`, `en` |

---

### `audit` - Доступність, SEO, Продуктивність

Аудит URL, HTML файлу або репозиторію на доступність, SEO, продуктивність та найкращі практики.

```bash
# Аудит сайту
xanalyze audit https://example.com

# Аудит з браузерним рендерингом (для SPA/React/Vue сайтів)
xanalyze audit https://example.com --browser

# Аудит з responsive breakpoints
xanalyze audit https://example.com --browser --breakpoints all

# Тільки desktop
xanalyze audit https://example.com --browser --breakpoints desktop

# Аудит локального HTML файлу
xanalyze audit ./page.html --browser

# Аудит репозиторію (без браузера)
xanalyze audit ./src

# Тільки категорія доступності
xanalyze audit https://example.com --category accessibility

# Тільки SEO та продуктивність
xanalyze audit https://example.com --category seo performance

# З AI проходом (перевіряє alt text, link text, headings)
xanalyze audit https://example.com --ai

# Авто-виправлення відомих проблем
xanalyze audit ./src --fix

# JSON вивід
xanalyze audit https://example.com --json

# Брифінг для агента
xanalyze audit https://example.com --report briefing.md
```

**Опції:**

| Опція | Опис |
|---|---|
| `target` | URL, директорія або `.html` файл |
| `--url` | Трактувати target як URL навіть без схеми |
| `--depth N` | Глибина кравлінгу (за замовчуванням: 0) |
| `--max-pages N` | Максимум сторінок (за замовчуванням: 30) |
| `--max-files N` | Максимум файлів (за замовчуванням: 5000) |
| `--render MODE` | Браузерний рендеринг: `never`, `auto`, `always` |
| `--exclude ...` | Патерни виключення |
| `--no-default-excludes` | Не пропускати стандартні виключення |
| `--category CATS` | Фільтр категорій: `accessibility`, `performance`, `seo`, `best-practices` |
| `--language LANG` | Мова виводу: `uk`, `it`, `en` |
| `--no-ignore` | Звітувати все |
| `--json` | JSON вивід |
| `--check` | Вихід 1 при критичних/серйозних проблемах |
| `--ai` | Запустити AI прохід (коштує токенів) |
| `--provider PROVIDER` | Перевизначення AI провайдера |
| `--fix` | Записати виправлення у файли |
| `--report PATH` | Брифінг для агента (.md або .json) |
| `--browser` | Завантажити сторінки в реальному браузері |
| `--breakpoints NAMES` | Responsive ширини: `all`, `desktop`, `tablet`, `mobile` |
| `--styled-report PATH` | брендований PDF/HTML звіт |

---

### `fix` - Застосування виправлень

Перезаписує символи без клавіатури, зберігаючи `.bak` копії.

```bash
# Виправити всі файли в директорії
xanalyze fix ./src

# Виправити конкретні файли
xanalyze fix ./src/index.html ./src/about.html
```

---

### `undo` - Скасування виправлень

Повертає файли до стану перед `fix`.

```bash
# Скасувати виправлення в директорії
xanalyze undo ./src

# Скасувати конкретні файли
xanalyze undo ./src/index.html
```

---

### `cache` - Управління кешем

```bash
# Статистика кешу
xanalyze cache stats

# Очистити кеш
xanalyze cache clear

# Шлях до файлу кешу
xanalyze cache path
```

---

### `compare` - Порівняння детекторів

Запускає різні детектори на одних файлах та порівнює результати.

```bash
xanalyze compare ./src
```

---

### `ai` - AI операції

Управління AI акаунтом та AI-операції.

```bash
# Статус акаунту
xanalyze ai status

# Увійти в підписку xFormat
xanalyze ai login --email user@example.com

# Вийти
xanalyze ai logout

# Список підключених додатків
xanalyze ai apps

# Надати дозвіл додатку
xanalyze ai grant my-app

# Відкликати дозвіл
xanalyze ai revoke my-app

# Переписати текст
xanalyze ai rewrite "Текст для перепису" --language uk

# Переписати з stdin
echo "Деякий текст" | xanalyze ai rewrite
```

---

### `clean` - Фільтр тексту

Фільтрує текст з stdin до stdout, виправляючи символи без клавіатури.

```bash
# Пропустити текст через фільтр
echo "Текст з \u2018розумними лапками\u2019" | xanalyze clean

# З підказкою мови
cat article.txt | xanalyze clean --language uk
```

---

### `serve` - Локальний HTTP сервер

Запускає локальний HTTP сервер для режиму agent-as-judge.

```bash
# Запустити на стандартному порту (8765)
xanalyze serve

# Власний порт
xanalyze serve --port 9000

# Прив'язати до всіх інтерфейсів
xanalyze serve --host 0.0.0.0
```

---

---

## Методи детекції

### Виявлення AI-патернів

Поєднує кілька сигналів для виявлення AI-згенерованого тексту:

#### Статистичні сигнали

1. **Burstiness (Одноманітність)** — Людський текст варіює довжину речень; AI-текст tends to be uniform
   - Вимірюється як коефіцієнт варіації довжин речень
   - Оцінка: 0 (bursty/людський) до 1 (одноманітний/AI-подібний)
   - Вага: 40%

2. **Лексична різноманітність (Повторення)** — Низьке type-token ratio вказує на формулаїчну фразеологію
   - Вимірюється на пасажах від 20+ слів
   - Оцінка: 0 (різноманітний/людський) до 1 (повторюваний/AI-подібний)
   - Вага: 35%

3. **Щільність Em Dash** — Надмірне використання em/en dash як заміна ком/дужок
   - Нормально: ~0.3 dash/100 слів; Багато: >2/100 слів
   - Оцінка: 0 (нормально) до 1 (багато)
   - Вага: 25%

#### Кліше-фрази

Великі словники для кожної мови (100+ англійських, 80+ українських, 80+ італійських):
- Хеджування та вступи ("варто зазначити", "it's important to note")
- Часові вступи ("у сучасному світі", "in today's fast-paced world")
- Маркетингові buzzwords ("розкрийте потенціал", "unlock the potential")
- Продуктовий/інтерфейсний копірайт ("комплексне рішення", "comprehensive solution")
- Окремі слова-маркери ("delve", "underscore", "pivotal", "realm")

#### Структурні патерни

Regex-детекція AI-улюблених конструкцій:
- "Не просто X, а Y" / "Not just X, but Y"
- "Справа не в X, справа в Y" / "It's not about X, it's about Y"
- "Жодних X. Жодних Y. Лише Z." / "No X. No Y. Just Z."
- "Чи ви X, чи Y" / "Whether you're X or Y"
- "Виведіть X на новий рівень" / "Take your X to the next level"

#### Формула оцінки

```
base = зважене_середнє(uniformity, repetition, dashes)
remaining = 1 - base
for each кліше/структурний_патерн:
    remaining *= (1 - weight)
score = 1 - remaining
```

Статистичні сигнали без кліше/структурних патернів обмежені 0.32 для запобігання хибних спрацювань на технічному тексті.

---

### Символи без клавіатури

Детерміністична детекція символів, які не з клавіатури:

| Категорія | Приклади | Оцінка |
|---|---|---|
| `invisible` | Zero-width пробіли, joiners, soft hyphens | 0.9 |
| `space` | Non-breaking пробіли, en/em пробіли | 0.7 |
| `homoglyph` | Кирилична а (U+0430) замість латинської a | 0.8 |
| `styled` | Математичні bold/italic варіанти | 0.6 |
| `typography` | Curly quotes, em dash (опціонально) | 0.3 |

Кожна аномалія надає:
- Точні кодпоінти (напр., `U+200B`)
- Текст заміни
- Категорію та опис

---

### Аудит доступності

47 правил в 4 категоріях. Статичні правила працюють на розібраному HTML; браузерні — на рендереному DOM.

#### Правила доступності (25)

| Rule ID | Серйозність | WCAG | Опис |
|---|---|---|---|
| `image-alt` | Critical | 1.1.1 | Зображення повинні мати `alt` |
| `image-alt-filename` | Serious | 1.1.1 | `alt` не повинен бути назвою файлу |
| `control-name` | Critical | 4.1.2, 2.4.4 | Інтерактивні елементи потребують accessible names |
| `link-text-vague` | Moderate | 2.4.4 | Уникати "тут", "детальніше", "click here" |
| `html-lang` | Serious | 3.1.1 | `<html>` повинен мати `lang` |
| `document-title` | Serious | 2.4.2 | Сторінка повинна мати `<title>` |
| `heading-order` | Moderate | 1.3.1, 2.4.6 | Без пропуску рівнів заголовків |
| `page-has-h1` | Moderate | 1.3.1 | Рівно один `<h1>` |
| `tabindex-positive` | Serious | 2.4.3 | Без позитивного `tabindex` |
| `duplicate-id` | Moderate | 4.1.1 | Без дублікатів `id` |
| `aria-reference-broken` | Serious | 1.3.1, 4.1.2 | ARIA посилання повинні працювати |
| `button-type` | Minor | — | Кнопки у формах потребують `type` |
| `media-captions` | Serious | 1.2.2 | Відео/аудіо потребують субтитрів |
| `media-autoplay` | Serious | 1.4.2 | Без autoplay без controls |
| `table-headers` | Serious | 1.3.1 | Таблиці даних потребують `<th>` |
| `table-scope` | Moderate | 1.3.1 | `<th>` повинен мати `scope` |
| `viewport-zoom` | Serious | 1.4.4 | Не блокувати зум |
| `contrast-inline` | Serious | 1.4.3 | Контраст inline-стилів (потребує браузер) |
| `landmark-regions` | Moderate | 1.3.1, 2.4.1 | Сторінка потребує `<main>` landmark |
| `skip-link` | Moderate | 2.4.1 | Перший фокусований елемент повинен переходити до контенту |
| `form-error-message` | Serious | 3.3.1 | Невалідні поля потребують опису помилки |
| `hreflang-links` | Minor | 3.1.2 | Мультимовні сайти потребують hreflang |
| `breadcrumb-markup` | Minor | 1.3.1, 2.4.8 | Хлібні крихти повинні використовувати `<nav>` |
| `language-change` | Minor | 3.1.2 | Іншомовний inline текст потребує атрибут `lang` |
| `abbreviation-expansion` | Minor | 3.1.4 | Абревіатури повинні використовувати `<abbr>` з `title` |

#### Браузерні правила (states pass)

| Rule ID | Серйозність | Опис |
|---|---|---|
| `keyboard-trap` | Serious | Фокус не може покинути елемент |
| `focus-not-visible` | Serious | Індикатор фокусу невидимий |
| `focus-order-mismatch` | Moderate | Порядок табуляції не відповідає візуальному |
| `hover-only-content` | Moderate | Контент видимий тільки при наведенні |
| `no-skip-link` | Moderate | Немає посилання "перейти до контенту" |
| `focus-outside-viewport` | Moderate | Фокусований елемент за межами екрану |

---

### Аудит SEO

| Rule ID | Серйозність | Опис |
|---|---|---|
| `seo-title-length` | Moderate | Title 15-60 символів |
| `seo-meta-description` | Moderate | Meta description 70-160 символів |
| `seo-canonical` | Moderate | Рівно один canonical link |
| `seo-noindex` | Serious | Без випадкового noindex/nofollow |
| `seo-open-graph` | Minor | og:title, og:description, og:image |
| `seo-structured-data` | Minor | JSON-LD або microdata |
| `seo-image-dimensions` | Minor | Зображення потребують width/height |
| `seo-empty-link` | Moderate | Посилання потребують тексту |

---

### Аудит продуктивності

| Rule ID | Серйозність | Опис |
|---|---|---|
| `perf-render-blocking` | Serious | Макс 3 блокуючих ресурси в `<head>` |
| `perf-third-party-sync` | Serious | Без синхронних сторонніх скриптів |
| `perf-large-inline` | Moderate | Inline style/script < 20KB |
| `perf-image-loading` | Minor | Зображення після 3-го повинні бути lazy-loaded |
| `perf-font-display` | Moderate | Шрифти потребують `font-display: swap` |
| `perf-preconnect` | Minor | Preconnect до сторонніх origins |
| `perf-layout-shift` | Moderate | Lazy зображення потребують розмірів |
| `image-modern-format` | Minor | Віддавати перевагу WebP/AVIF над PNG/JPG |

---

### Найкращі практики

| Rule ID | Серйозність | Опис |
|---|---|---|
| `bp-mixed-content` | Serious | Без HTTP ресурсів на HTTPS сторінках |
| `bp-target-blank` | Moderate | `target="_blank"` потребує `rel="noopener"` |
| `bp-charset` | Moderate | Оголосити `charset="utf-8"` |
| `bp-doctype` | Moderate | Включити `<!DOCTYPE html>` |
| `bp-inline-handlers` | Minor | Без inline event handlers |
| `bp-password-field` | Moderate | Поля паролів потребують `autocomplete` |
| `bp-deprecated-html` | Minor | Без застарілих елементів (`<center>`, `<font>`) |
| `bp-ai-markup-artifact` | Minor | Без AI vendor класів (`claude-*`, `data-gpt-*`) |

---

### Браузерний прохід

Коли використовується `--browser` (автоматично для `fullscan` на URL):

1. **Завантаження сторінки** — Реальний Chromium через QtWebEngine
2. **Затримка settle** — 2500ms після load для SPA гідратації
3. **axe-core** — Галузевий стандарт accessibility engine (~27% покриття)
4. **HTML_CodeSniffer** — Додаткові accessibility перевірки (~20% покриття)
5. **State Pass** — Фокус, keyboard traps, hover-only контент
6. **Вимірювання** — FCP, час завантаження, розмір передачі, розмір DOM
7. **Дедуплікація** — Однакові знахідки від кількох engine згортаються в один рядок

**Responsive Breakpoints:**

| Назва | Ширина | Висота |
|---|---|---|
| `desktop` | 1440px | 900px |
| `tablet` | 834px | 1112px |
| `mobile` | 390px | 844px |

Знахідка, побачена на кількох ширин, стає одним рядком, що записує де її бачили. Знахідка на одній ширині каже "тільки на mobile" — корисно для responsive-специфічних проблем.

---

## Детектори

| Детектор | Тип | Вартість | Мови | Опис |
|---|---|---|---|---|
| `offline` | Евристичний | Безкоштовно | uk, it, en | Кліше + структурні патерни + символи без клавіатури |
| `embedding` | Семантичний | Безкоштовно | Будь-яка | Sentence-transformers similarity |
| `claude-llm-judge` | LLM | Платно | Будь-яка | Anthropic Claude API |
| `xformat-llm-judge` | LLM | Платно | Будь-яка | Підписка xFormat |
| `claude-code-llm-judge` | LLM | Платно | Будь-яка | Claude Code API |
| `hybrid` | Змішаний | Платно | uk, it, en | Спочатку offline, потім LLM розширює |
| `none` | — | Безкоштовно | — | Пропустити детекцію контенту |

---

## Звіти

### Стилізований звіт (PDF/HTML)

Брендований, друкований звіт для людей:
- Підсумок з підрахунком серйозності
- Знахідки згруповані за категоріями
- Фрагменти коду з виправленнями
- Індикатори responsive breakpoints

```bash
xanalyze fullscan https://example.com --styled-report report.pdf
```

### Брифінг для агента (Markdown/JSON)

Структурований брифінг для coding agents:
- Статистика та підрахунки
- Знахідки по файлах
- Пропозиції виправлень
- Відстеження змін

```bash
xanalyze fullscan https://example.com --report briefing.md
```

### JSON вивід

Машинозчитуваний вивід для CI/CD пайплайнів:

```bash
xanalyze fullscan https://example.com --json
```

Структура виводу:
```json
{
  "target": "https://example.com",
  "is_url": true,
  "language": "en",
  "scan": {
    "findings": [...],
    "counts": {"total": 5, "style": 3, "characters": 2}
  },
  "audit": {
    "counts": {"critical": 0, "serious": 2, "moderate": 5, "minor": 3},
    "issues": [...]
  },
  "summary": {
    "total_findings": 15,
    "ai_patterns": 3,
    "characters": 2,
    "accessibility": 5,
    "seo": 3,
    "performance": 1,
    "best_practices": 1
  }
}
```

---

## Для AI агентів

Цей розділ описує як використовувати xanalyze з AI агента (Claude, ChatGPT, Copilot тощо) для аналізу сайтів та кодових баз.

### Швидка довідка

```bash
# Повне сканування сайту (все автоматично)
xanalyze fullscan https://example.com

# Повне сканування репозиторію
xanalyze fullscan ./my-project

# Швидка перевірка доступності
xanalyze audit https://example.com --browser --json

# Сканування коду на AI-патерни
xanalyze scan ./src --json

# Виправлення символів без клавіатури
xanalyze fix ./src
```

### Типові задачі

#### 1. Аналіз сайту (повне сканування)

```bash
xanalyze fullscan https://example.com
```

**Що робить:**
- Кравлить сайт (з браузерним рендерингом для SPA)
- Запускає аудит доступності (49 правил)
- Запускає аудит SEO
- Запускає аудит продуктивності
- Перевіряє AI-згенеровані текстові патерни
- Перевіряє символи без клавіатури
- Генерує JSON вивід + PDF звіт + брифінг для агента

**Вивід:** JSON в stdout, звіти зберігаються в `~/Desktop`

#### 2. Аналіз кодової бази

```bash
xanalyze fullscan ./my-project
```

**Що робить:**
- Сканує всі markup файли (HTML, JSX, TSX, Vue, Svelte тощо)
- Сканує locale файли (JSON, YAML)
- Сканує backend файли (Python, PHP, Ruby, Go, Java, C#)
- Перевіряє AI-згенерований текст в копії та коментарях
- Перевіряє символи без клавіатури
- Запускає аудит доступності на HTML файлах

#### 3. Швидка перевірка доступності

```bash
xanalyze audit https://example.com --browser --json
```

**Що робить:**
- Завантажує сторінку в реальному браузері (обробляє SPA)
- Запускає axe-core + HTML_CodeSniffer
- Перевіряє клавіатурний фокус, контраст, ARIA
- Повертає JSON з усіма проблемами

#### 4. Перевірка конкретної категорії

```bash
# Тільки проблеми доступності
xanalyze audit https://example.com --category accessibility --json

# Тільки проблеми SEO
xanalyze audit https://example.com --category seo --json

# Тільки проблеми продуктивності
xanalyze audit https://example.com --category performance --json
```

#### 5. Сканування на AI-патерни

```bash
xanalyze scan ./src --json
```

**Що робить:**
- Сканує файли на кліше-фрази, структурні патерни
- Перевіряє символи без клавіатури (zero-width, homoglyphs)
- Повертає знахідки з оцінками та поясненнями

#### 6. Автоматичне виправлення

```bash
# Виправити символи без клавіатури
xanalyze fix ./src

# Авто-виправлення проблем доступності (де можливо)
xanalyze audit ./src --fix
```

#### 7. Порівняння детекторів

```bash
xanalyze compare ./src --json
```

**Що робить:**
- Запускає кілька детекторів на одних файлах
- Порівнює результати
- Показує який детектор що знаходить

### Режим агент-як-суддя

Коли сам агент повинен оцінювати текст (не потрібен API ключ):

```bash
# Запуск з агентом-як-суддею
xanalyze fullscan https://example.com --agent

# Власний порт
xanalyze fullscan https://example.com --agent --agent-port 9000
```

**Як це працює:**
1. `--agent` запускає локальний HTTP сервер на порту 8765
2. Агент надсилає текст на `POST /judge`
3. Сервер повертає оцінку (0-1) ймовірності AI
4. Сервер автоматично зупиняється після завершення сканування

**Endpoints:**
- `POST /judge` — Оцінити текст на AI-патерни
- `GET /health` — Перевірка здоров'я
- `GET /detectors` — Список доступних детекторів

**Приклад curl:**
```bash
curl -X POST http://localhost:8765/judge \
  -H 'Content-Type: application/json' \
  -d '{"text": "Варто зазначити, що це комплексне рішення..."}'
```

**Опції LLM Judge:**

| Детектор | Команда | API ключ |
|---|---|---|
| Агент (за замовчуванням) | `xanalyze fullscan URL --agent` | Не потрібен |
| Claude API | `xanalyze fullscan URL --detector claude-llm-judge` | `ANTHROPIC_API_KEY` |
| xFormat | `xanalyze fullscan URL --detector xformat-llm-judge` | xFormat login |
| Claude Code | `xanalyze fullscan URL --detector claude-code-llm-judge` | Claude Code сесія |
| Hybrid | `xanalyze fullscan URL --detector hybrid` | Опціонально |

### Приклади робочих процесів агента

#### Приклад 1: Аудит та виправлення сайту

```bash
# Крок 1: Повне сканування
xanalyze fullscan https://example.com --json > scan.json

# Крок 2: Переглянути знахідки
cat scan.json | jq '.audit.counts'

# Крок 3: Отримати детальні проблеми
cat scan.json | jq '.audit.issues[] | select(.severity == "critical" or .severity == "serious")'

# Крок 4: Згенерувати пропозиції виправлень
xanalyze audit https://example.com --browser --report fixes.md
```

#### Приклад 2: Сканування та очищення кодової бази

```bash
# Крок 1: Сканувати на проблеми
xanalyze scan ./src --json > scan.json

# Крок 2: Перевірити що знайдено
cat scan.json | jq '.counts'

# Крок 3: Виправити символи без клавіатури
xanalyze fix ./src

# Крок 4: Перевірити виправлення
xanalyze scan ./src --json | jq '.counts'
```

#### Приклад 3: CI/CD інтеграція

```bash
# В CI пайплайні — помилка при критичних проблемах
xanalyze fullscan https://staging.example.com --check --json

# Код виходу 0 = немає критичних/серйозних проблем
# Код виходу 1 = знайдено критичні/серйозні проблеми
```

### Структура JSON виводу

```json
{
  "target": "https://example.com",
  "is_url": true,
  "language": "en",
  "scan": {
    "findings": [
      {
        "source": "style",
        "score": 0.85,
        "confidence": "high",
        "explanation": "cliché: unlock the potential; style-uniformity=0.72",
        "details": {
          "signals": {"uniformity": 0.72, "repetition": 0.45, "dashes": 0.3},
          "cliches": ["unlock the potential"],
          "language": "en"
        }
      }
    ],
    "counts": {"total": 5, "style": 3, "characters": 2}
  },
  "audit": {
    "counts": {"critical": 0, "serious": 2, "moderate": 5, "minor": 3},
    "issues": [
      {
        "rule": "image-alt",
        "category": "accessibility",
        "severity": "critical",
        "selector": "html > body > main > img",
        "snippet": "<img src=\"hero.jpg\">",
        "fix_snippet": "<img src=\"hero.jpg\" alt=\"\">"
      }
    ]
  },
  "summary": {
    "total_findings": 15,
    "ai_patterns": 3,
    "characters": 2,
    "accessibility": 5,
    "seo": 3,
    "performance": 1,
    "best_practices": 1
  }
}
```

### Рівні серйозності

| Рівень | Значення | Дія |
|---|---|---|
| `critical` | Повністю блокує користувачів | Виправити негайно |
| `serious` | Контент втрачений або непридатний | Виправити скоро |
| `moderate` | Важче використовувати | Виправити коли можливо |
| `minor` | Запах, може бути навмисним | Розглянути виправлення |

### Коди виходу

| Код | Значення |
|---|---|
| 0 | Успіх, немає критичних/серйозних проблем (з `--check`) |
| 1 | Знайдено критичні/серйозні проблеми (з `--check`) |
| 2 | Помилка (неправильні аргументи, файл не знайдено тощо) |

### Поради для агентів

1. **Завжди використовуйте `--json`** для машинозчитуваного виводу
2. **Використовуйте `--check`** в CI/CD для помилки при критичних проблемах
3. **Використовуйте `fullscan`** для комплексного аналізу
4. **Використовуйте `audit --browser`** для SPA/React/Vue сайтів
5. **Використовуйте `scan`** для швидкої перевірки AI-патернів
6. **Використовуйте `fix`** для авто-виправлення символів без клавіатури
7. **Парсуйте `summary`** для швидкого огляду
8. **Парсуйте `audit.issues`** для детальних знахідок
9. **Перевіряйте `fix_snippet`** для запропонованих виправлень
10. **Використовуйте `--language`** для локалізованих звітів

---

## GUI

Десктопний додаток надає ту саму функціональність з візуальним інтерфейсом:

1. **Вибір джерела** — URL сайту, папка репозиторію або один HTML файл
2. **Вибір рідера** — Code (статичний) або Browser (рендерений)
3. **Вибір перевірок** — Доступність, AI-патерни або обидва
4. **Вибір методу** — Offline, AI або hybrid
5. **Прогрес в реальному часі** — Оновлення статусу
6. **Панель знахідок** — Клікабельний список з бейджами серйозності
7. **Панель деталей** — Повний опис, фрагмент коду, пропозиція виправлення
8. **Панель превью** — Превью сторінки з виділеними проблемами

---

## Конфігурація

### Файл налаштувань

Розташування: `~/.config/xanalyze/settings.json`

```json
{
  "ui_language": "uk",
  "llm_provider": "xformat",
  "max_pages": 30,
  "unicode_categories": ["invisible", "space", "homoglyph"],
  "unicode_check_enabled": true
}
```

### Файл ігнорування

Створіть `.xanalyze-ignore` в корені проєкту (gitignore синтаксис):

```
# Ігнорувати vendored код
vendor/
third_party/

# Ігнорувати згенеровані файли
*.min.js
*.min.css
```

### Придушення знахідок

Придушити конкретні знахідки через налаштування або `.xanalyze-ignore`:
- За CSS селектором (виключити регіони)
- За rule ID (вимкнути правила)

---

## Видалення

### CLI

```bash
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

---

## Вимоги

- Python 3.9+
- PySide6 (для GUI)
- sentence-transformers (для embedding детектора)
- QtWebEngine (для браузерного проходу)

---

## Ліцензія

MIT
