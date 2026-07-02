# Установка навыка ASCII Vision

## 1. Скопировать файлы навыка

```bash
cp SKILL.md LLM_PROMPT.md USAGE.md ~/.config/opencode/skills/ascii_vision/
```

## 2. Установить Python-пакет

```bash
pip install -e /home/user/LLM/ASCII_vision
```

### Опциональные зависимости

```bash
# OCR (распознавание текста)
pip install pytesseract
# или:
pip install -e "/home/user/LLM/ASCII_vision[ocr]"

# Поддержка PDF
pip install pdf2image
# или:
pip install -e "/home/user/LLM/ASCII_vision[pdf]"

# Всё сразу:
pip install -e "/home/user/LLM/ASCII_vision[ocr,pdf]"
```

### Копирование проекта

```bash
cp -r /home/user/LLM/ASCII_vision /куда/нужно/
pip install -e /куда/нужно/ASCII_vision
```

## 3. Проверить

```bash
python -m ascii_vision.cli --help
# или:
ascii-vision --help
```

## 4. Системные зависимости (OCR)

Для работы OCR через pytesseract требуется установленный Tesseract:

```bash
# Ubuntu/Debian
sudo apt install tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng

# macOS
brew install tesseract tesseract-lang
```

## 5. Системные зависимости (PDF)

Для работы с PDF через pdf2image требуется poppler:

```bash
# Ubuntu/Debian
sudo apt install poppler-utils

# macOS
brew install poppler
```

Навык появится в списке доступных навыков opencode.