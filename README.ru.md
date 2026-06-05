# Etsy Account Creator

Автоматическая регистрация аккаунтов Etsy с подтверждением почты, прокси-ротацией, эмуляцией отпечатка браузера и решением капчи.

[English version](README.md)

## Возможности

- Многопоточная регистрация с настраиваемым количеством потоков
- Поддержка HTTP-прокси с автоматической ротацией и отбраковкой нерабочих
- Заказ и подтверждение email через API Anymessage
- Решение reCAPTCHA Enterprise через 2Captcha
- Полная эмуляция браузерного фингерпринта (WebGL, canvas, шрифты и др.)
- Обход DataDome через внешний Go TLS-клиент (tls_client_app.exe)
- Сохранение сессий: куки и заголовки для каждого аккаунта
- Подробное логирование в консоль и файл

## Структура проекта

```
├── main.py               # Точка входа, настройка окружения, управление процессами
├── manager.py            # Оркестрация регистраций, работа с почтой и прокси
├── worker.py             # Низкоуровневое взаимодействие с Etsy, управление сессиями
├── fingerprint.py        # Генератор браузерного отпечатка
├── functions.py          # Утилиты (генерация пароля, работа с путями)
├── headers.py            # Шаблоны HTTP-заголовков
├── names.py              # Список имён для регистрации
├── tls_client_app.exe    # Внешний Go-бинарник
├── config/
│   ├── settings.env      # API-ключи и настройки (игнорируется git)
│   ├── proxies.txt       # Список HTTP-прокси (игнорируется git)
│   └── recaptcha_tokens.json
├── output/               # Созданные аккаунты в JSON
├── output_json/          # Куки в формате JSON (совместимо с Playwright)
└── requirements.txt      # Зависимости Python
```

## Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/yourusername/etsy-reger.git
cd etsy-reger
```

2. Создайте виртуальное окружение и установите зависимости:
```bash
python -m venv venv
source venv/bin/activate   # или venv\Scripts\activate на Windows
pip install -r requirements.txt
```

3. Создайте конфигурационные файлы:
   - config/settings.env с API-ключами
   - config/proxies.txt с HTTP-прокси по одному на строку (ip:port или user:pass@ip:port)

## Использование

Запустите основной скрипт:

```bash
python main.py
```

Нажмите Ctrl+C для корректного завершения всех потоков и остановки Go-сервера.

## Конфигурация

Создайте файл config/settings.env со следующими ключами:

- ANYMESSAGE=your_anymessage_token
- RUCAPTCHA=your_2captcha_key
- THREADS_NUM=10

## Примечания

- Go TLS-клиент подменяет TLS-отпечаток (JA3/JA4) на Chrome для обхода проверок Etsy.
- Все созданные аккаунты сохраняются в output/ с полным набором кук и заголовков.

## Лицензия

Проект предназначен исключительно для образовательных целей.
