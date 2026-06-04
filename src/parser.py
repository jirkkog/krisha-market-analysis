import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random

# ============================================================
# ЗАГОЛОВКИ ЗАПРОСА
# Сайт может блокировать запросы без User-Agent
# Мы притворяемся обычным браузером
# ============================================================
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ru-RU,ru;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

# ============================================================
# РАЙОНЫ АЛМАТЫ
# Каждый район — отдельный URL-slug на сайте
# ============================================================
DISTRICTS = {
    'Бостандыкский':  'almaty-bostandykskij',
    'Ауэзовский':     'almaty-aujezovskij',
    'Алмалинский':    'almaty-almalinskij',
    'Алатауский':     'almaty-alatauskij',
    'Медеуский':      'almaty-medeuskie',
    'Наурызбайский':  'almaty-nauryzbajskij',
    'Жетысуский':     'almaty-zhetysuskie',
    'Турксибский':    'almaty-turksibskij',
}


def get_page(url):
    """
    Делает GET-запрос к странице и возвращает HTML.
    time.sleep нужен чтобы не спамить сервер запросами —
    это вежливый парсинг и защита от бана.
    """
    try:
        # Случайная пауза от 1 до 3 секунд между запросами
        time.sleep(random.uniform(1, 3))
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()  # бросает ошибку если статус не 200
        return response.text
    except requests.RequestException as e:
        print(f"Ошибка при запросе {url}: {e}")
        return None


def parse_listing(card):
    import re
    data = {}

    try:
        # ЦЕНА
        price_tag = card.select_one('.a-card__price')
        if price_tag:
            price_text = price_tag.get_text(strip=True)
            price_clean = ''.join(filter(str.isdigit, price_text))
            data['price'] = int(price_clean) if price_clean else None
        else:
            data['price'] = None

        # TITLE
        title_tag = card.select_one('.a-card__title')
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            data['title'] = title_text

            # Комнаты
            if 'студия' in title_text.lower():
                data['rooms'] = 0
            else:
                rooms_match = re.search(r'(\d+)-комнатн', title_text)
                data['rooms'] = int(rooms_match.group(1)) if rooms_match else None

            # Площадь
            area_match = re.search(r'(\d+(?:\.\d+)?)\s*м²', title_text)
            data['area_m2'] = float(area_match.group(1)) if area_match else None

            # Этаж — ищем "5/9 этаж" в title
            floor_match = re.search(r'(\d+)/(\d+)\s*этаж', title_text)
            if floor_match:
                data['floor'] = int(floor_match.group(1))
                data['total_floors'] = int(floor_match.group(2))
            else:
                data['floor'] = None
                data['total_floors'] = None
        else:
            data['title'] = None
            data['rooms'] = None
            data['area_m2'] = None
            data['floor'] = None
            data['total_floors'] = None

        # URL и listing_id
        link_tag = card.select_one('a.a-card__title')
        if link_tag:
            href = link_tag.get('href', '')
            data['url'] = 'https://krisha.kz' + href
            id_match = re.search(r'/show/(\d+)', href)
            data['listing_id'] = id_match.group(1) if id_match else None
        else:
            data['url'] = None
            data['listing_id'] = None

        # floor_info для дебага
        subtitle_tag = card.select_one('.a-card__subtitle')
        data['floor_info'] = subtitle_tag.get_text(strip=True) if subtitle_tag else None

    except Exception as e:
        print(f"Ошибка парсинга карточки: {e}")

    return data


def parse_district_page(district_name, district_slug, max_pages=5):
    """
    Парсит несколько страниц для одного района.
    max_pages=5 даёт примерно 100-150 объявлений на район.
    Для начала этого достаточно.
    """
    listings = []

    for page_num in range(1, max_pages + 1):
        if page_num == 1:
            url = f'https://krisha.kz/prodazha/kvartiry/{district_slug}/'
        else:
            url = f'https://krisha.kz/prodazha/kvartiry/{district_slug}/?page={page_num}'

        print(f"  Парсим: {district_name}, страница {page_num}...")

        html = get_page(url)
        if not html:
            print(f"  Не удалось получить страницу {page_num}, пропускаем")
            break

        soup = BeautifulSoup(html, 'lxml')

        # Находим все карточки объявлений на странице
        # Селектор нужно уточнить после проверки реального HTML
        cards = soup.select('.a-card')

        if not cards:
            print(f"  Карточки не найдены на странице {page_num}, возможно конец")
            break

        for card in cards:
            listing = parse_listing(card)
            if listing:
                listing['district'] = district_name
                listing['city'] = 'Алматы'
                listings.append(listing)

        print(f"  Собрано объявлений: {len(listings)}")

    return listings


def run_parser(max_pages_per_district=5):
    """
    Главная функция — запускает парсинг по всем районам
    и сохраняет результат в CSV.
    """
    all_listings = []

    for district_name, district_slug in DISTRICTS.items():
        print(f"\nРайон: {district_name}")
        district_listings = parse_district_page(
            district_name,
            district_slug,
            max_pages=max_pages_per_district
        )
        all_listings.extend(district_listings)
        print(f"Итого по {district_name}: {len(district_listings)} объявлений")

        # Дополнительная пауза между районами
        time.sleep(random.uniform(2, 4))

    # Сохраняем в CSV
    df = pd.DataFrame(all_listings)
    df.to_csv('data/listings_raw.csv', index=False, encoding='utf-8-sig')
    print(f"\nГотово. Всего собрано: {len(all_listings)} объявлений")
    print(f"Сохранено в data/listings_raw.csv")

    return df


if __name__ == '__main__':
    import os
    os.makedirs('data', exist_ok=True)
    df = run_parser(max_pages_per_district=5)
    print(df.head())
    print(df.info())

# Проверяем что починилось
print("Цена заполнена:", df['price'].notna().sum(), "из", len(df))
print("ID заполнен:", df['listing_id'].notna().sum(), "из", len(df))
print("Этаж заполнен:", df['floor'].notna().sum(), "из", len(df))
print()
print(df.columns.tolist())
print(df[['price','rooms','area_m2','floor','total_floors','listing_id']].head(5))
print(df[['price','rooms','area_m2','floor','total_floors','listing_id']].notna().sum())