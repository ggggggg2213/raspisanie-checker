
import os
import re
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

TEACHERS = {
    "Мызин А.А.": "https://raspisanie-ktmu.ru/teacher/xlnvjw5o",
    "Голубева С.А.": "https://raspisanie-ktmu.ru/teacher/a1y9hhg7",
}

MONTHS = {
    "января": 1, "февраля": 2, "марта": 3,
    "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9,
    "октября": 10, "ноября": 11, "декабря": 12
}

WEEKDAYS = (
    "понедельник|вторник|среда|четверг|"
    "пятница|суббота|воскресенье"
)

def check_teacher(page, name, url, target):
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)

    text = page.locator("body").inner_text()

    # Находим заголовок нужного дня
    pattern = (
        rf"(?:{WEEKDAYS}),?\s+"
        rf"{target.day}\s+"
        rf"{list(MONTHS.keys())[target.month - 1]}"
    )

    match = re.search(pattern, text, re.IGNORECASE)

    if not match:
        raise RuntimeError(f"Не найдено расписание на {target:%d.%m.%Y}")

    # Берём текст только нужного дня
    section = text[match.end():]

    next_day = re.search(
        rf"(?:{WEEKDAYS}),?\s+\d{{1,2}}\s+"
        rf"(?:{'|'.join(MONTHS.keys())})",
        section,
        re.IGNORECASE
    )

    if next_day:
        section = section[:next_day.start()]

    # Разделяем занятия по времени
    lessons = re.split(
        r"(?=\b\d{1,2}:\d{2}\s*[–-]\s*\d{1,2}:\d{2}\b)",
        section
    )

    for lesson in lessons:
        low = lesson.lower()

        if "физическая культура" not in low:
            continue

        if "отменено" in low:
            continue

        if "выдача задания" in low or "дистанционно" in low:
            continue

        if re.search(r"спортивный зал", low):
            print(f"{name}: найдена очная физкультура!")
            return True

    print(f"{name}: очной физкультуры нет.")
    return False


def send_telegram(message):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": message},
        timeout=30
    )
    response.raise_for_status()


def main():
    now = datetime.now(ZoneInfo("Europe/Moscow"))
    target = now.date() + timedelta(days=1)

    results = []
    errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(locale="ru-RU")

        for name, url in TEACHERS.items():
            try:
                result = check_teacher(page, name, url, target)
                results.append(result)
            except Exception as e:
                errors.append(f"{name}: {e}")

        browser.close()

    if any(results):
        send_telegram("ЗАВТРА ЕСТЬ ФИЗРА 🏃")
    elif errors:
        send_telegram(
            "⚠️ Не удалось полностью проверить расписание:\n"
            + "\n".join(errors)
        )
    elif len(results) == 2:
        send_telegram("ЗАВТРА ФИЗРЫ НЕТ 😴")


if __name__ == "__main__":
    main()
