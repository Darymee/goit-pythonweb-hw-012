# goit-pythonweb-hw-10

REST API для контактів із JWT-авторизацією, верифікацією email, CORS, rate limit
для `/users/me` та оновленням аватара через Cloudinary.

## Запуск

1. Скопіюйте змінні середовища:

```bash
cp .env.example .env
```

2. Заповніть `.env`, особливо `SECRET_KEY`, SMTP та Cloudinary-змінні.

3. Запустіть сервіси:

```bash
docker compose up --build
```

Документація API: `http://localhost:8000/docs`.

## Аутентифікація

Після логіну ви отримуєте `access_token`.

Для доступу до захищених маршрутів додайте заголовок:

Authorization: Bearer <your_access_token>

## Email verification

Після реєстрації користувач повинен підтвердити email. Без підтвердження доступ
до контактів заборонений.

## Контакти

Користувач має доступ лише до власних контактів.

## Основні маршрути

- `POST /auth/register` — реєстрація користувача, повертає `201 Created`, пароль
  хешується.
- `POST /auth/login` — логін через OAuth2 form-data: `username=<email>`,
  `password=<password>`, повертає `access_token`.
- `GET /auth/verify/{token}` — підтвердження email.
- `POST /auth/request-email` — повторно надіслати лист підтвердження.
- `GET /users/me` — дані поточного користувача, обмежено 5 запитів на хвилину.
- `PATCH /users/avatar` — завантаження аватара у Cloudinary.
- `/contacts/` — CRUD контактів тільки для підтвердженого користувача.

Якщо SMTP не налаштовано, посилання для верифікації буде виведено в консоль
застосунку.
