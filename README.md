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
# OCR (pytesseract)
sudo apt install tesseract-ocr tesseract-ocr-rus

# PDF (pdf2image)
sudo apt install poppler-utils
```

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