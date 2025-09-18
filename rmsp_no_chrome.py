#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
РМСП парсер без ChromeDriver - использует requests-html
RMSP parser without ChromeDriver - uses requests-html
"""

import sys
import re
import time
from requests_html import HTMLSession
from bs4 import BeautifulSoup


def validate_inn(inn):
    """Валидация ИНН"""
    if not inn:
        return False
    inn = inn.replace(' ', '').replace('-', '')
    if not re.match(r'^\d{10}$|^\d{12}$', inn):
        return False
    return inn


def search_rmsp_requests(inn):
    """
    Поиск в РМСП используя requests-html (без ChromeDriver)
    """
    
    validated_inn = validate_inn(inn)
    if not validated_inn:
        return {
            'found': False,
            'category': '-',
            'inclusion_date': '-',
            'message': f'Некорректный ИНН: {inn}'
        }
    
    print(f"Поиск для ИНН: {validated_inn}")
    print("Используем requests-html (без ChromeDriver)...")
    
    session = HTMLSession()
    
    # Настройка User-Agent
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    })
    
    try:
        # Загружаем главную страницу
        print("Загрузка страницы РМСП...")
        url = "https://rmsp.nalog.ru/search.html"
        
        response = session.get(url)
        response.raise_for_status()
        
        print("Страница загружена, выполняем JavaScript...")
        
        # Выполняем JavaScript для загрузки динамического контента
        response.html.render(timeout=20)
        
        # Ищем форму поиска
        search_forms = response.html.find('input')
        search_input = None
        
        for input_elem in search_forms:
            placeholder = input_elem.attrs.get('placeholder', '').lower()
            name = input_elem.attrs.get('name', '').lower()
            if 'инн' in placeholder or 'search' in name:
                search_input = input_elem
                break
        
        if not search_input:
            print("Не найдено поле ввода для ИНН")
            return {
                'found': False,
                'category': '-',
                'inclusion_date': '-',
                'message': 'Не найдено поле поиска на сайте'
            }
        
        print("Поле поиска найдено")
        
        # Пытаемся выполнить поиск через POST запрос
        search_url = "https://rmsp.nalog.ru/api/search"  # Примерный API endpoint
        
        # Попробуем разные варианты параметров
        search_params = [
            {'query': validated_inn, 'inn': validated_inn},
            {'search': validated_inn},
            {'q': validated_inn},
            {'text': validated_inn}
        ]
        
        for params in search_params:
            try:
                print(f"Пробуем поиск с параметрами: {params}")
                
                search_response = session.post(search_url, data=params)
                if search_response.status_code == 200:
                    return parse_search_results(search_response.text, validated_inn)
                    
            except Exception as e:
                print(f"Ошибка поиска с {params}: {e}")
                continue
        
        # Если API не сработал, пробуем через GET с параметрами
        get_params = [
            {'query': validated_inn},
            {'search': validated_inn},
            {'q': validated_inn}
        ]
        
        for params in get_params:
            try:
                print(f"Пробуем GET поиск с параметрами: {params}")
                
                get_response = session.get(url, params=params)
                if get_response.status_code == 200:
                    get_response.html.render(timeout=15)
                    return parse_search_results(get_response.html.html, validated_inn)
                    
            except Exception as e:
                print(f"Ошибка GET поиска с {params}: {e}")
                continue
        
        return {
            'found': False,
            'category': '-',
            'inclusion_date': '-',
            'message': 'Не удалось выполнить поиск через API'
        }
        
    except Exception as e:
        print(f"Общая ошибка: {e}")
        return {
            'found': False,
            'category': '-',
            'inclusion_date': '-',
            'message': f'Ошибка подключения: {str(e)}'
        }
    
    finally:
        session.close()


def parse_search_results(html_content, inn):
    """Парсинг результатов поиска"""
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    result = {
        'found': False,
        'category': '-',
        'inclusion_date': '-',
        'message': ''
    }
    
    # Проверяем сообщение "не найдено"
    user_message = soup.find(string=re.compile(r'Уважаемый пользователь'))
    if user_message:
        parent = user_message.parent
        if parent and 'не найдено сведений' in parent.get_text().lower():
            result['message'] = 'Организация не найдена в реестре'
            return result
    
    # Ищем таблицу с результатами
    table = soup.find('table')
    if table:
        rows = table.find_all('tr')
        if len(rows) > 1:
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 4:
                    result['found'] = True
                    result['category'] = cells[1].get_text(strip=True) if len(cells) > 1 else '-'
                    result['inclusion_date'] = cells[3].get_text(strip=True) if len(cells) > 3 else '-'
                    break
    
    # Альтернативный поиск
    if not result['found']:
        page_text = soup.get_text().lower()
        
        # Поиск категории
        if 'микропредприятие' in page_text:
            result['found'] = True
            result['category'] = 'Микропредприятие'
        elif 'малое предприятие' in page_text:
            result['found'] = True
            result['category'] = 'Малое предприятие'
        elif 'среднее предприятие' in page_text:
            result['found'] = True
            result['category'] = 'Среднее предприятие'
        
        # Поиск даты
        if result['found']:
            date_pattern = r'\d{2}\.\d{2}\.\d{4}'
            dates = re.findall(date_pattern, soup.get_text())
            if dates:
                result['inclusion_date'] = dates[0]
    
    return result


def search_rmsp_simple(inn):
    """
    Простой поиск через requests (без JavaScript)
    """
    
    validated_inn = validate_inn(inn)
    if not validated_inn:
        return {
            'found': False,
            'category': '-',
            'inclusion_date': '-',
            'message': f'Некорректный ИНН: {inn}'
        }
    
    print(f"Поиск для ИНН: {validated_inn}")
    print("Используем простые HTTP запросы...")
    
    import requests
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5',
    })
    
    try:
        # Пробуем разные URL для поиска
        search_urls = [
            f"https://rmsp.nalog.ru/search.html?query={validated_inn}",
            f"https://rmsp.nalog.ru/search.html?search={validated_inn}",
            f"https://rmsp.nalog.ru/search.html?q={validated_inn}",
            f"https://rmsp.nalog.ru/api/search?inn={validated_inn}",
        ]
        
        for url in search_urls:
            try:
                print(f"Пробуем URL: {url}")
                response = session.get(url, timeout=10)
                
                if response.status_code == 200:
                    return parse_search_results(response.text, validated_inn)
                    
            except Exception as e:
                print(f"Ошибка с {url}: {e}")
                continue
        
        return {
            'found': False,
            'category': '-',
            'inclusion_date': '-',
            'message': 'Сайт требует JavaScript. Установите ChromeDriver или используйте основной парсер.'
        }
        
    except Exception as e:
        return {
            'found': False,
            'category': '-',
            'inclusion_date': '-',
            'message': f'Ошибка подключения: {str(e)}'
        }


def main():
    """Главная функция"""
    
    print("РМСП Парсер БЕЗ ChromeDriver")
    print("=" * 40)
    
    if len(sys.argv) < 2:
        inn = input("Введите ИНН: ")
    else:
        inn = sys.argv[1]
    
    if not inn:
        print("ИНН не введен")
        return
    
    # Пробуем разные методы
    methods = [
        ("requests-html", search_rmsp_requests),
        ("простые запросы", search_rmsp_simple)
    ]
    
    for method_name, method_func in methods:
        print(f"\n🔍 Пробуем метод: {method_name}")
        print("-" * 30)
        
        try:
            result = method_func(inn)
            
            # Выводим результат
            print("\n" + "=" * 40)
            print("РЕЗУЛЬТАТ ПОИСКА")
            print("=" * 40)
            
            if result['found']:
                print("1. СТАТУС: ✅ НАЙДЕНА")
                print(f"2. КАТЕГОРИЯ: {result['category']}")
                print(f"3. ДАТА ВКЛЮЧЕНИЯ: {result['inclusion_date']}")
                print("=" * 40)
                return  # Успех - выходим
            else:
                print("1. СТАТУС: ❌ НЕ НАЙДЕНА")
                print("2. КАТЕГОРИЯ: -")
                print("3. ДАТА ВКЛЮЧЕНИЯ: -")
                
                if result['message']:
                    print(f"\nДетали: {result['message']}")
                
                # Если это не последний метод, пробуем следующий
                if method_name != methods[-1][0]:
                    print(f"\n⚠️  Метод '{method_name}' не сработал, пробуем следующий...")
                    continue
                else:
                    print("=" * 40)
                    break
                    
        except ImportError as e:
            if 'requests_html' in str(e):
                print(f"❌ Библиотека requests-html не установлена")
                print("Установите: pip install requests-html")
                if method_name != methods[-1][0]:
                    continue
            else:
                print(f"❌ Ошибка импорта: {e}")
                break
        except Exception as e:
            print(f"❌ Ошибка метода '{method_name}': {e}")
            if method_name != methods[-1][0]:
                continue
            else:
                break
    
    print("\n💡 РЕКОМЕНДАЦИЯ:")
    print("Для стабильной работы используйте основной парсер с ChromeDriver:")
    print("python rmsp_parser.py " + inn)


if __name__ == "__main__":
    main()
