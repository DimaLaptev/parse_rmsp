#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
РМСП парсер с Playwright (современная замена Selenium)
RMSP parser with Playwright (modern Selenium alternative)
"""

import sys
import re
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


def validate_inn(inn):
    """Валидация ИНН"""
    if not inn:
        return False
    inn = inn.replace(' ', '').replace('-', '')
    if not re.match(r'^\d{10}$|^\d{12}$', inn):
        return False
    return inn


async def search_rmsp_playwright(inn):
    """
    Поиск в РМСП используя Playwright
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
    print("Используем Playwright...")
    
    async with async_playwright() as p:
        try:
            # Запускаем браузер (автоматически скачается при первом запуске)
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # Устанавливаем User-Agent
            await page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            
            print("Загрузка страницы РМСП...")
            await page.goto('https://rmsp.nalog.ru/search.html#', wait_until='networkidle')
            
            # Ожидаем загрузки формы
            print("Ожидание загрузки формы...")
            await page.wait_for_timeout(3000)  # 3 секунды
            
            # Ищем поле ввода для ИНН
            search_selectors = [
                'input[placeholder*="ИНН"]',
                'input[name*="search"]',
                'input[id*="search"]',
                'input[type="text"]'
            ]
            
            search_input = None
            for selector in search_selectors:
                try:
                    search_input = await page.wait_for_selector(selector, timeout=5000)
                    if search_input:
                        print(f"Поле поиска найдено: {selector}")
                        break
                except:
                    continue
            
            if not search_input:
                await browser.close()
                return {
                    'found': False,
                    'category': '-',
                    'inclusion_date': '-',
                    'message': 'Не найдено поле для ввода ИНН'
                }
            
            # Вводим ИНН
            await search_input.click()
            await search_input.fill('')  # Очищаем поле
            await search_input.fill(validated_inn)
            print(f"ИНН {validated_inn} введен")
            
            # Ищем кнопку поиска
            search_buttons = [
                'button:has-text("Найти")',
                'button:has-text("НАЙТИ")',
                'button:has-text("Поиск")',
                'input[type="submit"]',
                'button[type="submit"]'
            ]
            
            search_clicked = False
            for button_selector in search_buttons:
                try:
                    button = await page.wait_for_selector(button_selector, timeout=3000)
                    if button:
                        await button.click()
                        search_clicked = True
                        print(f"Кнопка поиска нажата: {button_selector}")
                        break
                except:
                    continue
            
            if not search_clicked:
                # Пробуем нажать Enter
                await search_input.press('Enter')
                print("Отправлена форма через Enter")
            
            # Ожидаем результаты
            print("Ожидание результатов поиска...")
            await page.wait_for_timeout(5000)  # 5 секунд
            
            # Ожидаем появления таблицы или сообщения
            try:
                await page.wait_for_selector('table, div:has-text("Уважаемый пользователь")', timeout=10000)
            except:
                pass
            
            # Получаем HTML страницы
            html_content = await page.content()
            
            await browser.close()
            
            # Парсим результаты
            return parse_search_results(html_content, validated_inn)
            
        except Exception as e:
            print(f"Ошибка Playwright: {e}")
            try:
                await browser.close()
            except:
                pass
            
            return {
                'found': False,
                'category': '-',
                'inclusion_date': '-',
                'message': f'Ошибка Playwright: {str(e)}'
            }


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


def main():
    """Главная функция"""
    
    print("РМСП Парсер с Playwright")
    print("=" * 40)
    
    if len(sys.argv) < 2:
        inn = input("Введите ИНН: ")
    else:
        inn = sys.argv[1]
    
    if not inn:
        print("ИНН не введен")
        return
    
    try:
        # Запускаем асинхронный поиск
        result = asyncio.run(search_rmsp_playwright(inn))
        
        # Выводим результат
        print("\n" + "=" * 40)
        print("РЕЗУЛЬТАТ ПОИСКА")
        print("=" * 40)
        
        if result['found']:
            print("1. СТАТУС: ✅ НАЙДЕНА")
            print(f"2. КАТЕГОРИЯ: {result['category']}")
            print(f"3. ДАТА ВКЛЮЧЕНИЯ: {result['inclusion_date']}")
        else:
            print("1. СТАТУС: ❌ НЕ НАЙДЕНА")
            print("2. КАТЕГОРИЯ: -")
            print("3. ДАТА ВКЛЮЧЕНИЯ: -")
            
            if result['message']:
                print(f"\nДетали: {result['message']}")
        
        print("=" * 40)
        
    except ImportError:
        print("❌ Библиотека playwright не установлена")
        print("Установите: pip install playwright")
        print("И выполните: playwright install")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print("\n💡 Попробуйте основной парсер:")
        print(f"python rmsp_parser.py {inn}")


if __name__ == "__main__":
    main()
