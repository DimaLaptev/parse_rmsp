#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер для поиска информации на сайте РМСП (Реестр МСП) по ИНН
RMSP Parser for searching information by INN (tax identification number)
"""

import sys
import re
import time
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException


class RMSPParser:
    """Класс для парсинга данных с сайта РМСП"""
    
    def __init__(self, chromedriver_port=64095):
        self.base_url = "https://rmsp.nalog.ru/search.html#"
        self.chromedriver_port = chromedriver_port
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def validate_inn(self, inn):
        """
        Валидация ИНН (INN validation)
        
        Args:
            inn (str): ИНН для проверки
            
        Returns:
            str or False: Очищенный ИНН или False если невалидный
        """
        if not inn:
            return False
            
        # Убираем пробелы и дефисы
        inn = inn.replace(' ', '').replace('-', '')
        
        # Проверяем формат (10 или 12 цифр)
        if not re.match(r'^\d{10}$|^\d{12}$', inn):
            return False
            
        return inn
    
    def setup_chrome_driver(self):
        """
        Подключение к уже запущенному ChromeDriver
        
        Returns:
            webdriver: Настроенный драйвер
        """
        try:
            print(f"Подключение к ChromeDriver на порту {self.chromedriver_port}...")
            
            # Проверяем доступность ChromeDriver
            test_response = requests.get(f"http://127.0.0.1:{self.chromedriver_port}/status", timeout=3)
            if test_response.status_code != 200:
                print(f"❌ ChromeDriver не отвечает на порту {self.chromedriver_port}")
                return None
            
            # Настройки для подключения к удаленному ChromeDriver
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            
            # Подключаемся к запущенному ChromeDriver
            driver = webdriver.Remote(
                command_executor=f'http://127.0.0.1:{self.chromedriver_port}',
                options=chrome_options
            )
            
            driver.implicitly_wait(10)
            print("✅ Подключение к ChromeDriver успешно")
            return driver
            
        except requests.exceptions.ConnectionError:
            print(f"❌ ChromeDriver недоступен на порту {self.chromedriver_port}")
            print("Убедитесь, что ChromeDriver запущен:")
            print(f"   chromedriver --port={self.chromedriver_port}")
            return None
        except Exception as e:
            print(f"❌ Ошибка подключения к ChromeDriver: {e}")
            return None
    
    def search_with_selenium(self, inn):
        """
        Поиск с использованием Selenium для обхода JavaScript
        
        Args:
            inn (str): ИНН для поиска
            
        Returns:
            list: Список результатов поиска
        """
        driver = self.setup_chrome_driver()
        if not driver:
            return None
        
        try:
            print("Загрузка страницы РМСП...")
            driver.get(self.base_url)
            
            # Ожидание загрузки формы поиска
            try:
                # Ищем поле ввода для ИНН
                search_input = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='ИНН'], input[name*='search'], input[id*='search']"))
                )
                print("Форма поиска найдена")
            except TimeoutException:
                # Альтернативный поиск поля ввода
                search_inputs = driver.find_elements(By.TAG_NAME, "input")
                search_input = None
                for inp in search_inputs:
                    if inp.get_attribute("type") in ["text", "search"] or "поиск" in inp.get_attribute("placeholder", "").lower():
                        search_input = inp
                        break
                
                if not search_input:
                    print("Не удалось найти поле поиска")
                    return None
            
            # Очищаем поле и вводим ИНН
            search_input.clear()
            search_input.send_keys(inn)
            print(f"ИНН {inn} введен в поле поиска")
            
            # Поиск кнопки "Найти" или "Поиск"
            try:
                search_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Найти') or contains(text(), 'НАЙТИ') or contains(text(), 'Поиск')]"))
                )
            except TimeoutException:
                # Альтернативный поиск кнопки
                buttons = driver.find_elements(By.TAG_NAME, "button")
                search_button = None
                for btn in buttons:
                    if any(word in btn.text.lower() for word in ['найти', 'поиск', 'search']):
                        search_button = btn
                        break
                
                if not search_button:
                    # Пробуем найти submit кнопку
                    search_button = driver.find_element(By.CSS_SELECTOR, "input[type='submit'], button[type='submit']")
            
            if search_button:
                search_button.click()
                print("Кнопка поиска нажата")
            else:
                # Пробуем нажать Enter
                from selenium.webdriver.common.keys import Keys
                search_input.send_keys(Keys.RETURN)
                print("Отправлена форма через Enter")
            
            # Ожидание результатов
            print("Ожидание результатов поиска...")
            time.sleep(5)
            
            # Дополнительное ожидание загрузки таблицы
            try:
                WebDriverWait(driver, 10).until(
                    EC.any_of(
                        EC.presence_of_element_located((By.TAG_NAME, "table")),
                        EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Уважаемый пользователь')]"))
                    )
                )
                print("Результаты загружены")
            except TimeoutException:
                print("Таймаут ожидания результатов, продолжаем парсинг...")
            
            # Сохраняем HTML для отладки (можно отключить)
            # with open('debug_page.html', 'w', encoding='utf-8') as f:
            #     f.write(driver.page_source)
            #     print("HTML страницы сохранен в debug_page.html")
            
            # Парсинг результатов
            results = self.parse_results(driver.page_source)
            
            return results
            
        except Exception as e:
            print(f"Ошибка при поиске: {e}")
            return None
        finally:
            # НЕ закрываем драйвер, так как он запущен внешне
            # Только закрываем текущую сессию
            try:
                driver.close()
            except:
                pass
    
    def parse_results(self, html_content):
        """
        Парсинг результатов поиска из HTML с извлечением конкретных данных
        
        Args:
            html_content (str): HTML контент страницы
            
        Returns:
            dict: Результат поиска с статусом и данными
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        result = {
            'found': False,
            'organization_name': '',
            'category': '',
            'inclusion_date': '',
            'region': '',
            'inn': '',
            'ogrn': '',
            'message': ''
        }
        
        # Проверяем наличие предупреждения "не найдено"
        warning_block = soup.find('div', class_=re.compile(r'alert|warning', re.I))
        if warning_block:
            warning_text = warning_block.get_text(strip=True)
            if any(word in warning_text.lower() for word in ['не найдено', 'не найден', 'отсутствует']):
                result['found'] = False
                result['message'] = warning_text
                return result
        
        # Ищем сообщение "Уважаемый пользователь!" которое указывает на отсутствие результатов
        user_message = soup.find(string=re.compile(r'Уважаемый пользователь'))
        if user_message:
            parent = user_message.parent
            if parent:
                message_text = parent.get_text(strip=True)
                if 'не найдено сведений' in message_text.lower():
                    result['found'] = False
                    result['message'] = message_text
                    return result
        
        # Проверяем наличие результатов через счетчик "Найдено записей"
        found_count = soup.find(string=re.compile(r'Найдено записей:\s*(\d+)'))
        if found_count:
            count_match = re.search(r'Найдено записей:\s*(\d+)', found_count)
            if count_match and int(count_match.group(1)) == 0:
                result['found'] = False
                result['message'] = 'Записи не найдены'
                return result
        
        # Ищем таблицу с результатами
        table = soup.find('table')
        if table:
            rows = table.find_all('tr')
            if len(rows) > 1:  # Есть данные кроме заголовка
                # Находим строку с данными организации
                data_row = None
                for row in rows[1:]:  # Пропускаем заголовок
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 4:  # Должно быть достаточно колонок
                        data_row = row
                        break
                
                if data_row:
                    cells = data_row.find_all(['td', 'th'])
                    result['found'] = True
                    
                    # Извлекаем данные из колонок таблицы
                    if len(cells) > 0:
                        # Первая колонка - название организации (может содержать ссылку)
                        name_cell = cells[0]
                        link = name_cell.find('a')
                        if link:
                            result['organization_name'] = link.get_text(strip=True)
                        else:
                            result['organization_name'] = name_cell.get_text(strip=True)
                    
                    if len(cells) > 1:
                        # Вторая колонка - категория
                        result['category'] = cells[1].get_text(strip=True)
                    
                    if len(cells) > 2:
                        # Третья колонка - регион
                        result['region'] = cells[2].get_text(strip=True)
                    
                    if len(cells) > 3:
                        # Четвертая колонка - дата включения
                        result['inclusion_date'] = cells[3].get_text(strip=True)
                    
                    # Ищем ИНН и ОГРН в полном тексте строки
                    full_row_text = data_row.get_text()
                    
                    inn_match = re.search(r'ИНН[:\s]*(\d{10,12})', full_row_text)
                    if inn_match:
                        result['inn'] = inn_match.group(1)
                    
                    ogrn_match = re.search(r'ОГРН[:\s]*(\d{13,15})', full_row_text)
                    if ogrn_match:
                        result['ogrn'] = ogrn_match.group(1)
        
        # Дополнительный поиск ИНН и ОГРН в детальной информации
        if result['found']:
            # Ищем блок с детальной информацией
            detail_blocks = soup.find_all('div', string=re.compile(r'ИНН|ОГРН'))
            for block in detail_blocks:
                text = block.get_text()
                
                if 'ИНН:' in text and not result['inn']:
                    inn_match = re.search(r'ИНН:\s*(\d{10,12})', text)
                    if inn_match:
                        result['inn'] = inn_match.group(1)
                
                if 'ОГРН:' in text and not result['ogrn']:
                    ogrn_match = re.search(r'ОГРН:\s*(\d{13,15})', text)
                    if ogrn_match:
                        result['ogrn'] = ogrn_match.group(1)
        
        # Улучшенный поиск данных если таблица не найдена
        if not result['found']:
            # Ищем конкретные селекторы для данных РМСП
            
            # Поиск по классам и ID элементов
            name_selectors = [
                'a[href*="view"]',  # Ссылки на детали организации
                '.organization-name',
                '.company-name',
                'td:first-child a',  # Первая колонка таблицы со ссылкой
            ]
            
            for selector in name_selectors:
                name_element = soup.select_one(selector)
                if name_element:
                    result['found'] = True
                    result['organization_name'] = name_element.get_text(strip=True)
                    
                    # Ищем родительскую строку таблицы
                    row = name_element.find_parent('tr')
                    if row:
                        cells = row.find_all('td')
                        if len(cells) >= 4:
                            result['category'] = cells[1].get_text(strip=True) if len(cells) > 1 else ''
                            result['region'] = cells[2].get_text(strip=True) if len(cells) > 2 else ''
                            result['inclusion_date'] = cells[3].get_text(strip=True) if len(cells) > 3 else ''
                    break
            
            # Если все еще не найдено, ищем через JavaScript переменные
            if not result['found']:
                page_text = soup.get_text()
                if 'RSMP_CATEGORY' in page_text and any(word in page_text for word in ['Микропредприятие', 'Малое предприятие', 'Среднее предприятие']):
                    result['found'] = True
                    result['organization_name'] = 'Организация найдена (требуется уточнение названия)'
                    
                    # Извлекаем категорию из JavaScript
                    if 'Микропредприятие' in page_text:
                        result['category'] = 'Микропредприятие'
                    elif 'Малое предприятие' in page_text:
                        result['category'] = 'Малое предприятие'
                    elif 'Среднее предприятие' in page_text:
                        result['category'] = 'Среднее предприятие'
        
        return result
    
    def search_by_inn(self, inn):
        """
        Основная функция поиска по ИНН
        
        Args:
            inn (str): ИНН для поиска
            
        Returns:
            dict: Результат поиска
        """
        validated_inn = self.validate_inn(inn)
        if not validated_inn:
            print("Ошибка: Некорректный формат ИНН")
            print("ИНН должен содержать 10 или 12 цифр")
            return None
        
        print(f"Поиск информации для ИНН: {validated_inn}")
        print("-" * 50)
        
        # Поиск с помощью Selenium
        result = self.search_with_selenium(validated_inn)
        
        if result:
            self.display_results(result)
        else:
            print("Информация не найдена или произошла ошибка")
            print("Возможные причины:")
            print("- Организация не зарегистрирована в РМСП")
            print("- Временные проблемы с сайтом")
            print("- Необходимо обновить ChromeDriver")
        
        return result
    
    def display_results(self, result):
        """
        Отображение результатов поиска - только 3 главных параметра
        
        Args:
            result (dict): Результат поиска для отображения
        """
        if not result:
            print("Результаты не найдены")
            return
        
        print("\n" + "=" * 50)
        print("РЕЗУЛЬТАТ ПОИСКА В РМСП")
        print("=" * 50)
        
        # 1. СТАТУС: Найдена или не найдена
        if not result.get('found', False):
            print("1. СТАТУС: ❌ НЕ НАЙДЕНА")
            print("2. КАТЕГОРИЯ: -")
            print("3. ДАТА ВКЛЮЧЕНИЯ: -")
            
            if result.get('message'):
                print(f"\nДетали: {result['message']}")
        else:
            print("1. СТАТУС: ✅ НАЙДЕНА")
            
            # 2. КАТЕГОРИЯ
            category = result.get('category', 'Не указана')
            print(f"2. КАТЕГОРИЯ: {category}")
            
            # 3. ДАТА ВКЛЮЧЕНИЯ В РЕЕСТР
            inclusion_date = result.get('inclusion_date', 'Не указана')
            print(f"3. ДАТА ВКЛЮЧЕНИЯ: {inclusion_date}")
            
            # Дополнительная информация (если нужна)
            if result.get('organization_name') and 'JavaScript' not in result.get('organization_name', ''):
                print(f"\nНазвание: {result['organization_name']}")
        
        print("=" * 50)


def main():
    """Основная функция программы"""
    print("РМСП Парсер - Подключение к запущенному ChromeDriver")
    print("=" * 55)
    
    # Получаем порт ChromeDriver из аргументов или используем по умолчанию
    chromedriver_port = 64095
    inn = None
    
    if len(sys.argv) > 1:
        # Если передан только ИНН
        if sys.argv[1].isdigit() and len(sys.argv[1]) in [10, 12]:
            inn = sys.argv[1]
        else:
            # Если передан порт и ИНН
            try:
                chromedriver_port = int(sys.argv[1])
                if len(sys.argv) > 2:
                    inn = sys.argv[2]
            except ValueError:
                inn = sys.argv[1]  # Если первый аргумент не число, считаем его ИНН
    
    print(f"Используется ChromeDriver на порту: {chromedriver_port}")
    
    parser = RMSPParser(chromedriver_port)
    
    # Получение ИНН
    if not inn:
        inn = input("Введите ИНН для поиска: ")
    else:
        print(f"ИНН: {inn}")
    
    if inn:
        parser.search_by_inn(inn)
    else:
        print("ИНН не введен")
        sys.exit(1)


if __name__ == "__main__":
    main()

