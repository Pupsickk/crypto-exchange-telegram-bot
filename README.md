# Crypto Exchange Telegram Bot

![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![Aiogram](https://img.shields.io/badge/Aiogram-3-26A5E4?logo=telegram&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)

**Telegram-бот для приёма заявок на обмен с калькулятором, историей заявок и ручной обработкой администратором.**

Пользователь проходит пошаговую форму внутри Telegram; оператор получает заявку и подтверждение оплаты, затем подтверждает обмен или указывает причину отказа.

## Возможности

- Направления обмена между USDT, BTC, ETH и RUB, заданные в коде.
- FSM-сценарий: направление → сумма → реквизиты → подтверждение → скриншот оплаты.
- Калькулятор суммы по курсам из SQLite.
- История заявок пользователя и статусы обработки.
- Подтверждение или отклонение заявки администратором.
- Хранение заявок в `exchange_bot.db`.

## Запуск

Нужен Python 3.10+.

```bash
git clone https://github.com/Pupsickk/crypto-exchange-telegram-bot.git
cd crypto-exchange-telegram-bot
python -m venv .venv
```

Активируйте окружение: Windows PowerShell — `.venv\Scripts\Activate.ps1`, Linux/macOS — `source .venv/bin/activate`.

```bash
python -m pip install -r requirements.txt
```

Скопируйте `.env.example` в `.env` и заполните настройки. Затем:

```bash
python bot.py
```

| Настройка | Значение |
| --- | --- |
| `BOT_TOKEN` | Токен своего бота из BotFather |
| `ADMIN_ID` | Числовой Telegram ID оператора |

Перед первым запуском оператору нужно открыть бота и отправить `/start`.

## Как устроен проект

| Компонент | Реализация |
| --- | --- |
| Telegram API | Асинхронный aiogram 3 |
| Диалог | FSM, `MemoryStorage` |
| Данные | SQLite, таблицы курсов и заявок |
| Точка входа | [bot.py](bot.py) |

## Особенности текущей версии

Курсы и лимиты заданы в `init_db()`; таблица курсов пересоздаётся при запуске. Это не подключение к биржевым котировкам. Скриншот проверяет оператор, автоматической проверки блокчейн-платежей нет. Незавершённые диалоги хранятся в памяти и сбрасываются при перезапуске. Перед использованием на реальных заявках необходимо проверить тарифы, реквизиты и весь сценарий обработки.


## Скриншоты

<img src="https://github.com/user-attachments/assets/bb008e5c-413d-4fe9-aed5-56d6ba58ece9" alt="Экран приложения 1" width="300" />

<img src="https://github.com/user-attachments/assets/2c131cdf-0c6f-4e01-bd58-99876033bbe3" alt="Экран приложения 2" width="300" />

<img src="https://github.com/user-attachments/assets/d2ee8594-4a54-4c84-816c-e0db0665aa74" alt="Экран приложения 3" width="300" />

<img src="https://github.com/user-attachments/assets/82c2b09f-72cf-4ae4-b523-e9fdbfc7ee35" alt="Экран приложения 4" width="300" />

<img src="https://github.com/user-attachments/assets/c395224e-e898-4ae7-8352-ebe61d9ae0cd" alt="Экран приложения 5" width="300" />

<img src="https://github.com/user-attachments/assets/ac1e961f-86a1-41bd-a67d-24c39f0134af" alt="Экран приложения 6" width="300" />

<img src="https://github.com/user-attachments/assets/0c3a1d6e-abb6-4f04-988b-33054a90ce69" alt="Экран приложения 7" width="300" />
