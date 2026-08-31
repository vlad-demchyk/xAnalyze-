# XAnalyze (українська)

Десктопний і headless-аналізатор патернів AI-тексту, не-клавіатурних символів та якості сайтів і репозиторіїв.

[English](README.md) | [Italiano](README_it.md)

## Зміст

- [Можливості](#можливості)
- [Швидкий старт](#швидкий-старт)
- [Використання](#використання)
- [Команди CLI](#команди-cli)
- [Шаблони, які він розуміє](#шаблони-які-він-розуміє)
- [Стеки, які він розпізнає](#стеки-які-він-розпізнає)
- [Аналіз](#аналіз)
- [Звіти й прогони](#звіти-й-прогони)
- [Інтерфейси](#інтерфейси)
- [Конфігурація](#конфігурація)
- [Обмеження](#обмеження)
- [Вимоги](#вимоги)
- [Ліцензія](#ліцензія)

## Можливості

XAnalyze сканує сайт, HTML-файл, репозиторій або каталог із кодом і показує точні місця проблем.

- **AI-патерни**: офлайн-, embedding-, гібридний або модельний детектор для користувацького тексту.
- **Символи**: zero-width, homoglyph, незвичайні пробіли, стилізовані літери та типографіка.
- **Аудит сайту**: доступність, SEO, продуктивність, безпека й best practices.
- **Браузерний аудит**: Chromium для клієнтських застосунків і responsive-перевірка на 1440, 834 і 390 px.
- **Факти репозиторія**: tracked або unignored `.env`, конфігурація й коміти, пов'язані з AI-асистентами, blame знахідок.
- **Походження медіа**: IPTC/XMP і необов'язкові C2PA-маніфести. Це факти файлу, не вердикт про пікселі.
- **Історія прогонів**: пауза, продовження, порівняння та документи кожного прогону.

`fullscan` об'єднує перевірки тексту, символів і сайту. Локальний репозиторій сканується статично, якщо не вказано `--devserver`.

Стек визначається за файлами-маркерами або віддамою розміткою. Обидва списки набір тестів звіряє з кодом, тож вони живуть у розділах [Шаблони, які він розуміє](#шаблони-які-він-розуміє) і [Стеки, які він розпізнає](#стеки-які-він-розпізнає), а не переказуються тут.

## Швидкий старт

### GUI для macOS

```bash
curl -L -o XAnalyze.app.zip https://github.com/vlad-demchyk/xAnalyze-/releases/latest/download/XAnalyze.app.zip
unzip XAnalyze.app.zip
mv XAnalyze.app /Applications/
```

### CLI для macOS/Linux

```bash
curl -L -o xanalyze-cli.tar.gz https://github.com/vlad-demchyk/xAnalyze-/releases/latest/download/xanalyze-cli-macos-arm64.tar.gz
tar -xzf xanalyze-cli.tar.gz
echo 'export PATH="$PWD/xanalyze:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### Із вихідного коду

```bash
git clone https://github.com/vlad-demchyk/xAnalyze-.git
cd xAnalyze-
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python main.py                         # GUI
python cli.py fullscan https://example.com
```

## Використання

```bash
xanalyze                                      # запустити TUI
xanalyze fullscan https://example.com         # повний аудит сайту
xanalyze scan ./src                           # AI-патерни й символи
xanalyze audit https://example.com --browser  # аудит сайту
xanalyze fix ./src                            # застосувати виправлення символів
xanalyze runs                                 # список і продовження прогонів
xanalyze update                               # перевірити оновлення
xanalyze --version
```

## Команди CLI

### `fullscan`

```bash
xanalyze fullscan https://xformat.net
xanalyze fullscan ./my-project
xanalyze fullscan https://example.com --depth 2 --max-pages 50
xanalyze fullscan https://example.com --breakpoints desktop,mobile
xanalyze fullscan https://example.com --detector hybrid --language uk
xanalyze fullscan https://example.com --styled-report ./reports/site.pdf --report ./reports/agent.md
```

Для URL і HTML браузерний рендеринг увімкнено автоматично, якщо не задано `--no-browser`. Для локального застосунку `--devserver` запускає Node, Django або Rails-сервер.

| Прапорець | Призначення |
|---|---|
| `target` | URL, каталог або HTML-файл |
| `--url` | Примусово трактувати ціль як URL |
| `--depth N` | Глибина обходу URL, за замовчуванням `0` |
| `--max-pages N` | Максимум сторінок, за замовчуванням `30` |
| `--max-files N` | Максимум локальних файлів, за замовчуванням `5000` |
| `--ext ...` | Розширення файлів |
| `--exclude PATTERN` | Додаткове gitignore-виключення |
| `--no-default-excludes` | Не застосовувати стандартні виключення |
| `--repo PATH` | Зв'язати findings рендера з файлами джерела |
| `--devserver` | Запустити dev-сервер репозиторію |
| `--start-command CMD` | Замінити команду запуску сервера |
| `--dev-server-port N` | Порт для Django або Rails |
| `--yes` | Встановлювати відсутні залежності без запиту |
| `--detector NAME` | `offline`, `embedding`, `hybrid`, `llm-judge` |
| `--model NAME` | Модель AI-проходу |
| `--effort LEVEL` | `low`, `medium`, `high` |
| `--no-judgment-cache` | Не використовувати кеш оцінок |
| `--scope NAME` | `content`, `technical`, `both` |
| `--no-typography` | Ігнорувати em dash і curly quotes |
| `--breakpoints NAMES` | `all`, `desktop`, `tablet`, `mobile`, `reflow` (320 px) або список. Без нього браузерний прохід іде на одній ширині, 1440x900 - тій самій, що `desktop` |
| `--styled-report PATH` | PDF або HTML-звіт |
| `--report PATH` | Markdown або JSON-брифінг |
| `--check` | Завершити зі статусом 1 за серйозних проблем |
| `--language LANG` | `uk`, `it`, `en` |
| `--agent` | Підготувати офлайн-кандидатів для агента |
| `--no-browser` | Вимкнути браузерний рендеринг |

### `scan`

```bash
xanalyze scan ./src
xanalyze scan ./src --detector offline --scope content
xanalyze scan ./src --json --check
xanalyze scan ./src --incremental
xanalyze scan ./src --styled-report report.pdf --language uk
```

Корисні опції: `--ext`, `--exclude`, `--max-files`, `--detector`, `--provider`, `--no-unicode`, `--scope`, `--categories`, `--no-typography`, `--no-ignore`, `--json`, `--check`, `--incremental`, `--styled-report`, `--language`. Категорії: `invisible`, `space`, `homoglyph`, `styled`, `typography`.

### `audit`

```bash
xanalyze audit https://example.com
xanalyze audit https://example.com --browser --breakpoints all
xanalyze audit ./page.html --browser
xanalyze audit ./src --category accessibility
xanalyze audit https://example.com --category seo performance
xanalyze audit ./src --fix
xanalyze audit https://example.com --json --report briefing.md
```

Опції охоплюють `--depth`, `--max-pages`, `--max-files`, `--render`, `--exclude`, `--category`, `--language`, `--no-ignore`, `--json`, `--check`, `--ai`, `--provider`, `--fix`, `--report`, `--browser`, `--breakpoints`, `--site-controls`, `--styled-report`. `--site-controls` окремо отримує robots.txt і оголошені в ньому sitemap того ж домену.

Пʼята картка екрана налаштування, **Що показувати**, тримає параметри прогону, які раніше були лише в CLI: шість категорій аудиту (разом із `geo`), поріг певності (`--confidence`) і `--site-controls`. Область (`--scope`) стоїть поруч із контролями репозиторію, а типографіка є категорією символів у Налаштуваннях.

Категорія і певність - це **вигляд над одним готовим проходом**, так само як `--category` і `--confidence`: правила дешеві й ділять один розбір, тому звуження перемальовує список і підсумок, нічого не переаудитуючи, а розширення повертає всі знахідки назад. Експортований звіт пишеться через той самий вигляд, тож екран і файл не можуть розійтися. Коли фільтр ховає все, порожній екран каже це прямо і показує кількість без фільтра, а не звітує сторінку як чисту. `--site-controls` інший за природою - він тягне robots.txt і оголошені в ньому sitemap - тому це вибір прогону, вимкнений за замовчуванням і видимий лише для сайту.

Екран Аудиту в TUI має ті самі три параметри, а списки ширин на екранах Аудиту й Повного сканування містять усі ширини, які знає аудит.

### `fix`, `undo`, `runs`, `resume`, `cache`, `compare`

```bash
xanalyze fix ./src
xanalyze undo ./src
xanalyze runs
xanalyze resume 2026-08-24-1331
xanalyze cache stats
xanalyze cache clear
xanalyze cache path
xanalyze compare ./src
```

`fix` створює `.bak`-копії, `undo` їх відновлює. Стан прогону зберігається для продовження.

### `logs`, `ai`, `clean`

```bash
xanalyze logs --level warning
xanalyze logs --json
xanalyze logs clean
xanalyze ai status
xanalyze ai login
xanalyze ai logout
echo "text" | xanalyze clean --language uk
```

Логи зберігаються у `$XDG_STATE_HOME/xanalyze/logs` або `~/.local/state/xanalyze/logs`. `XANALYZE_LOG_DIR` змінює шлях, `XANALYZE_LOG_LEVEL=debug` вмикає деталізацію.

### `agent-scan` і `agent-judge`

```bash
xanalyze agent-scan ./src --json > passages.json
xanalyze agent-judge ./src --judgments verdicts.json
```

Перша команда видає ID і текст кандидатів, друга застосовує оцінки агента та формує звіт.

Кожен уривок несе поле `language`, і воно дорівнює `null`, коли уривок закороткий, щоб його прочитати. Це відповідь, а не порожнє місце: кнопка з двох слів не стає англійською лише тому, що більше нічого не розпізналось, а агент, якому сказали інакше, судитиме її за чужими очікуваннями.

### `update` і `uninstall`

```bash
xanalyze update
xanalyze uninstall
```

Інтерактивне видалення показує список файлів, які буде прибрано. Неінтерактивний варіант застосовуй лише тоді, коли видалення справді потрібне.

## Шаблони, які він розуміє

Чотирнадцять шаблонних мов мають **пару** фікстур у `tests/fixtures/frameworks`:
той самий компонент, написаний так, як велить його фреймворк, і написаний
неправильно. Правильна половина мусить давати нуль знахідок, зламана - саме ті,
на які заслуговує. Тож це виміряне твердження, а не намір:

`alpine`, `angular`, `blade`, `django`, `erb`, `handlebars`, `liquid`, `php`, `razor`, `react`, `svelte`, `thymeleaf`, `twig`, `vue`

Це те, проти чого скан **перевірено**. Розмітку поза цим списком він усе одно
читає - парсер її не відкидає - але ніщо не довело, що коректний файл у ній
повернеться чистим, і хибну знахідку там набір тестів не спіймає.

## Стеки, які він розпізнає

Проєкт визначається за власними файлами-маркерами, і те, чим він виявився,
вирішує, що вважати чужим кодом, а не написаним тут:

`angular`, `astro`, `beehiiv`, `carrd`, `craft`, `django`, `docusaurus`, `dotnet`, `drupal`, `eleventy`, `ember`, `flutter`, `gatsby`, `ghost`, `hugo`, `jekyll`, `joomla`, `laravel`, `magento`, `nextjs`, `nuxt`, `qwik`, `rails`, `remix`, `shopify`, `silverstripe`, `spfx`, `spring`, `squarespace`, `statamic`, `storybook`, `sveltekit`, `symfony`, `typo3`, `vite`, `wagtail`, `webflow`, `wix`, `wordpress`

Сигнатури зважуються, а не рахуються: кожна має певність, і платформа
називається лише тоді, коли збіги дають 100, тож маркер, який міг потрапити туди
з іншої причини, мусить підтверджуватись.

## Аналіз

Офлайн-детектор поєднує статистичні сигнали, структуру, кліше й мовні правила. Embedding і модельні детектори додають незалежну оцінку. Кожна знахідка має місце, score, пояснення та рівень певності.

Аудит охоплює `accessibility` (29), `best-practices` (8), `geo` (2), `performance` (8), `security` (10), `seo` (8) - ці числа набір тестів звіряє з реєстром правил. GEO дає лише advisory-сигнали про тип статті, автора й дату, а не прогноз позицій у відповідях ШІ. Статичний режим читає файли; браузерний бачить DOM після рендерингу, клієнтський контент, responsive-стани й заголовки відповіді. `--repo` додає шлях до вихідного файлу для URL-аудиту.

**Становий прохід** іде в браузері й перевіряє сторінку в тому стані, в який її ставить людина: індикатор фокуса, клавіатурні пастки, порядок обходу, контент лише на наведення, відкрите модальне вікно з фокусом позаду нього - і подорож формою: поле без доступної назви після виконання скриптів, поле, назване лише placeholder-ом, значення, яке відхиляє сам браузер, і про це ніхто не каже, та текст помилки на екрані, на який не посилається жодне поле. Він читає і не діє: нічого не вписується, не натискається і не відправляється, бо на живому сайті кожна з цих дій запускає власні обробники сторінки. Тому заповнення поля заради перевірки реакції форми лишається поза межами, як і INP, який без справжнього вводу не міряється.

Знахідки мають рівень `exact`, `needs-browser` або `advisory`. `exact` означає, що розмітка відповідає на питання повністю, `advisory` - що не відповість ніщо і вирішує людина: це редакційне рішення, і саме такими є GEO-ознаки.

**Невизначене не показується.** `needs-browser` - це рушій, який каже, що не зміг визначити: «елемент лежить на фоновому зображенні», «абсолютно позиційований, колір тла не встановити». Заміряно на одній сторінці python.org у справжньому браузері: таких було **312 із 348** знахідок про контраст, а весь прогін після їх виходу дав **182** знахідки замість 497. Звіт, дві третини якого це «ми не знаємо», не є списком, з яким можна працювати, тож прогін називає кількість схованого, а `--unsettled` повертає його. `--confidence exact` - ще суворіший вигляд: він прибирає й редакційні.

Походження медіа читає IPTC/XMP і C2PA. Факти репозиторія охоплюють `.env`, AI-асистентські коміти, конфігурацію та blame. Це provenance, а не твердження, що використання асистента є дефектом.

## Звіти й прогони

За замовчуванням документи зберігаються в `~/Desktop/XAnalyze/`; `XANALYZE_REPORT_ROOT` змінює корінь.

```text
XAnalyze/example.com/2026-08-24-0930/
  report.md       згрупований брифінг агента
  report.pdf      звіт для людини
  timings.md      тривалість етапів
  changes.md      порівняння з попереднім прогоном
  state.md        стан для продовження
  state.json      стан для програм
```

```bash
xanalyze fullscan https://example.com --styled-report report.pdf
xanalyze fullscan https://example.com --report briefing.md
xanalyze fullscan https://example.com --json > run.json
```

Звіт групує однакові проблеми й перелічує всі місця. Динамічні ідентифікатори фреймворків нормалізуються лише в атрибутах ідентифікаторів. `changes.md` показує зміни між прогонами; менша кількість findings може означати менший обсяг обходу.

## Інтерфейси

GUI має налаштування цілі, типу аналізу, детектора, scope, глибини, breakpoint-ів, мови й акаунта. Результати містять список findings, preview, деталі, виправлення та експорт звіту. Механічні виправлення позначені за замовчуванням, модельні чернетки потребують перевірки.

Запуск `xanalyze` без аргументів відкриває TUI з режимами Scan, Audit, Full Scan, Reports, Settings, Update і Uninstall. Навігація: стрілки, цифрові клавіші, `Tab`, `Esc`, `q`.

## Конфігурація

Файл: `~/.config/xanalyze/settings.json`

```json
{
  "ui_language": "uk",
  "llm_provider": "xformat",
  "max_pages": 30,
  "unicode_categories": ["invisible", "space", "homoglyph"],
  "unicode_check_enabled": true
}
```

`.xanalyze-ignore` у корені проєкту використовує gitignore-синтаксис:

```text
vendor/
third_party/
*.min.js
*.min.css
```

Можна додавати секції `[rules]`, `[selectors]`, `[fingerprints]`, а також фрази й шляхи. Коментарі та порожні рядки зберігаються.

## Обмеження

- AI-детекція залежить від корпусу й не доводить авторство; модельні оцінки недетерміновані.
- **Офлайн-прохід по формулюваннях слабкий італійською, і інструмент тепер каже це під час прогону.** На відкладеній половині корпусу він знаходить 36% відомих AI-уривків італійською проти 55% англійською і 71% українською, тоді як embedding-детектор знаходить 100%, 85% і 86%. Прогін, чия сторінка читається як італійська, друкує попередження з назвою кращого детектора і повторює його в JSON як `scan.detector_note`. Прохід по формулюваннях лишається типовим, бо він миттєвий, не потребує `torch`, називає знайдену фразу і вміє замінити її офлайн, а ще ловить чотири відкладені уривки, які embedding пропускає.
- **Детекція тексту працює лише для української, італійської та англійської.** Уривок іншою мовою так і називається, а прохід по формулюваннях і embedding не кажуть про нього нічого, замість того щоб міряти його списками й референсом, які цієї мови не знають. Заміряно на 257 абзацах німецькою, французькою, іспанською, польською і російською: 249 читаються як непідтримувана мова. Перевірки символів, типографіки й аудиту не залежать від мови й працюють далі, а модельний суддя цим обмеженням не зв'язаний.
- Статичний скан не бачить контент, створений під час рендерингу. Використовуйте URL або `--devserver`.
- Один breakpoint не описує responsive-поведінку. Для повної картини використовуйте `--breakpoints all`.
- Типографічна перевірка може знаходити навмисну пунктуацію; її можна вимкнути.
- `--scope technical` міряє символи й технічні сигнали, а не маркетинговий стиль.
- C2PA потребує необов'язкових `c2pa-python` і `cryptography`.
- У 16-колірних терміналах частина кольорів критичності зливається, але текстові підписи лишаються.

## Вимоги

- Python 3.14+
- PySide6 для GUI
- sentence-transformers для embedding-детектора
- QtWebEngine для браузерного рендерингу
- `c2pa-python` і `cryptography` для C2PA

## Ліцензія

MIT
