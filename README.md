# ASCII Vision

Конвертация изображений в ASCII-арт для анализа языковыми моделями (LLM).

Преобразует схемы, диаграммы, скриншоты и фотографии в текстовый формат, пригодный для чтения LLM. Добавляет OCR-распознавание текста, цветовую карту и аннотации.

## Возможности

- **ASCII-арт** — изображение текстом: `--binary`, `--invert`, `--blocks`, `--levels N`
- **OCR** — распознавание текста на изображении: `--ocr`, `--annotate`, `--ocr-only`
- **Цветовая карта** — сетка усреднённых цветов: `--colors`, `--color-grid N`
- **Авто-бинаризация** — порог Otsu для схем/диаграмм: `--binary`, `--threshold N`
- **EXIF-метаданные** — извлечение технической информации: `--exif`, `--auto-orient`
- **Пакетная обработка** — glob-шаблоны: `--batch "*.png"`
- **stdin / PDF** — конвейерная обработка и документы PDF
- **Мульти-разрешение** — общая форма + детали в одном выводе: `--multi 80 150`
- **Таймстемпы** — каждое сохранение с меткой времени, `--overwrite` для перезаписи

## Установка

```bash
pip install -e .
# с OCR и PDF:
pip install -e ".[ocr,pdf]"
```

Системные зависимости:

```bash
# Ubuntu / Debian
sudo apt install tesseract-ocr tesseract-ocr-rus poppler-utils
```

```bash
# Fedora / RHEL / CentOS
sudo dnf install tesseract tesseract-langpack-rus poppler-utils
```

```powershell
# Windows — установить Tesseract вручную:
#   https://github.com/UB-Mannheim/tesseract/wiki
#   (добавить русский язык при установке)
#
# PDF: poppler (через chocolatey или вручную)
#   choco install poppler
#
# Или через Windows Subsystem for Linux (WSL) — см. Ubuntu выше
```

## Интеграция с opencode

Навык для [opencode](https://github.com/anomalyco/opencode) — LLM сможет «видеть» изображения через ASCII-арт.

```bash
# 1. Скопировать файлы навыка
cp skill/SKILL.md skill/LLM_PROMPT.md skill/USAGE.md \
   ~/.config/opencode/skills/ascii_vision/

# 2. Установить пакет (после pip install -e .)
python -m ascii_vision.cli --help

# 3. В сессии opencode попросить:
#    «Проанализируй схему diagram.png»
```

После этого навык `ascii_vision` появится в списке доступных — LLM будет автоматически вызывать его при запросах анализа изображений.

## Использование

```bash
ascii-vision image.png [флаги]
# или:
python -m ascii_vision.cli image.png [флаги]
```

### Пресеты

```bash
# Схема / диаграмма
ascii-vision diagram.png --binary --invert --multi 80 150 --colors --annotate

# Фотография
ascii-vision photo.jpg --invert -w 200 --colors

# Только текст (OCR)
ascii-vision scan.png --ocr-only

# Пакетная обработка
ascii-vision --batch "screenshots/*.png" --binary --invert
```

Все флаги: `ascii-vision --help`

## ⚠️ Код написан LLM

**Весь код этого проекта полностью сгенерирован языковой моделью (LLM) в рамках диалогового взаимодействия с человеком.** Ни одна строка не написана вручную — включая архитектуру, алгоритмы, документацию и этот README.