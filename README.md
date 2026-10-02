# Агент на LangChain

Локальный учебный агент на LangChain. Он принимает вопрос в терминале и умеет умножать два целых числа через инструмент `multiply`. Модель — OpenAI, ключ и имя модели берутся из файла `.env`.

## Что нужно

- Python 3.12
- [uv](https://docs.astral.sh/uv/) или обычный `venv`
- ключ OpenAI

## Установка

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python langchain langchain-openai python-dotenv
```

## Настройка

Создайте в корне проекта файл `.env`. В репозиторий его класть не нужно.

```env
key_openai="ваш_ключ"
model_openai="gpt-4o-mini"
```

## Запуск

```bash
.venv/bin/python main.py
```

Примеры запросов:

- `Сколько будет 7 умножить на 8?`
- `Умножь 12 на 5`

Выход из диалога: `exit` или `quit`.

## Состав

- `main.py` — модель, инструмент умножения и диалог с агентом
- `.env` — ключ и название модели, только на вашей машине
