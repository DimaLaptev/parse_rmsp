#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для массовой обработки ИНН из Excel файла через РМСП парсер
Excel RMSP Processor for bulk INN processing through RMSP parser

Использование:
    python excel_rmsp_processor.py input_file.xlsx [output_file.xlsx] [chromedriver_port]

Пример:
    python excel_rmsp_processor.py companies.xlsx processed_companies.xlsx 64095
"""

import pandas as pd
from datetime import datetime, date
import sys
import os
import time
from pathlib import Path

# Импорт нашего парсера РМСП
try:
    from rmsp_parser import RMSPParser
except ImportError as e:
    print(f"❌ Ошибка импорта rmsp_parser: {e}")
    print("Убедитесь, что файл rmsp_parser.py находится в той же директории")
    sys.exit(1)


class ExcelRMSPProcessor:
    """Класс для обработки Excel файлов с ИНН через РМСП парсер"""
    
    def __init__(self, chromedriver_port=64095):
        """
        Инициализация процессора
        
        Args:
            chromedriver_port (int): Порт ChromeDriver (по умолчанию 64095)
        """
        self.chromedriver_port = chromedriver_port
        self.parser = None
        
        # Названия столбцов для поиска и создания
        self.input_columns = {
            'inn': 'ИНН',
            'contract_date': 'Дата заключения'
        }
        
        self.output_columns = {
            'smsp_robot': 'СМСП Робот',
            'category_robot': 'Категория Робот', 
            'inclusion_date_robot': 'Дата включения Робот',
            'exclusion_date_robot': 'Дата исключения Робот',
            'date_discrepancy_robot': 'Расхождения в датах Робот'
        }
    
    def init_parser(self):
        """Инициализация парсера РМСП"""
        if not self.parser:
            print(f"Инициализация РМСП парсера с портом {self.chromedriver_port}...")
            self.parser = RMSPParser(self.chromedriver_port)
            print("✅ Парсер инициализирован")
    
    def validate_excel_file(self, file_path):
        """
        Проверка существования и формата Excel файла
        
        Args:
            file_path (str): Путь к файлу
            
        Returns:
            bool: True если файл корректный
        """
        if not os.path.exists(file_path):
            print(f"❌ Файл не найден: {file_path}")
            return False
        
        if not file_path.lower().endswith(('.xlsx', '.xls')):
            print(f"❌ Неподдерживаемый формат файла: {file_path}")
            print("Поддерживаются только .xlsx и .xls файлы")
            return False
            
        return True
    
    def load_excel_file(self, file_path):
        """
        Загрузка Excel файла
        
        Args:
            file_path (str): Путь к файлу
            
        Returns:
            pandas.DataFrame or None: Загруженные данные
        """
        try:
            print(f"Загрузка Excel файла: {file_path}")
            df = pd.read_excel(file_path)
            print(f"✅ Файл загружен. Строк: {len(df)}, Столбцов: {len(df.columns)}")
            return df
        except Exception as e:
            print(f"❌ Ошибка загрузки файла: {e}")
            return None
    
    def validate_columns(self, df):
        """
        Проверка наличия необходимых столбцов
        
        Args:
            df (pandas.DataFrame): Данные Excel
            
        Returns:
            bool: True если все столбцы найдены
        """
        missing_columns = []
        
        # Проверяем обязательные столбцы
        if self.input_columns['inn'] not in df.columns:
            missing_columns.append(self.input_columns['inn'])
        
        if self.input_columns['contract_date'] not in df.columns:
            missing_columns.append(self.input_columns['contract_date'])
        
        if missing_columns:
            print(f"❌ Отсутствуют обязательные столбцы: {missing_columns}")
            print(f"Доступные столбцы: {list(df.columns)}")
            return False
        
        print("✅ Все необходимые столбцы найдены")
        return True
    
    def add_output_columns(self, df):
        """
        Добавление выходных столбцов если их нет
        
        Args:
            df (pandas.DataFrame): Данные Excel
            
        Returns:
            pandas.DataFrame: Обновленные данные
        """
        for col_name in self.output_columns.values():
            if col_name not in df.columns:
                df[col_name] = ''
                print(f"Добавлен столбец: {col_name}")
        
        return df
    
    def parse_date(self, date_value):
        """
        Парсинг даты из различных форматов
        
        Args:
            date_value: Значение даты (может быть строкой, datetime и т.д.)
            
        Returns:
            datetime.date or None: Распарсенная дата
        """
        if pd.isna(date_value) or date_value == '':
            return None
        
        # Если уже datetime
        if isinstance(date_value, (datetime, date)):
            return date_value.date() if isinstance(date_value, datetime) else date_value
        
        # Если строка
        if isinstance(date_value, str):
            date_formats = [
                '%d.%m.%Y',
                '%d/%m/%Y', 
                '%Y-%m-%d',
                '%d-%m-%Y',
                '%d.%m.%y',
                '%d/%m/%y'
            ]
            
            for fmt in date_formats:
                try:
                    return datetime.strptime(date_value.strip(), fmt).date()
                except ValueError:
                    continue
        
        return None
    
    def compare_dates(self, contract_date, inclusion_date):
        """
        Сравнение дат договора и включения в РМСП
        
        Args:
            contract_date: Дата договора
            inclusion_date: Дата включения в РМСП
            
        Returns:
            str: "да" если есть расхождение, "нет" если нет, "" если нет данных
        """
        contract_parsed = self.parse_date(contract_date)
        inclusion_parsed = self.parse_date(inclusion_date)
        
        if not contract_parsed or not inclusion_parsed:
            return ""  # Если одна из дат не распарсена
        
        # Если дата договора раньше даты включения в РМСП - есть расхождение
        if contract_parsed < inclusion_parsed:
            return "да"
        else:
            return "нет"
    
    def process_single_inn(self, inn_value, row_index):
        """
        Обработка одного ИНН
        
        Args:
            inn_value: Значение ИНН
            row_index: Индекс строки (для логов)
            
        Returns:
            dict: Результат обработки
        """
        result = {
            'smsp_robot': 'нет',
            'category_robot': '',
            'inclusion_date_robot': '',
            'exclusion_date_robot': '',
            'date_discrepancy_robot': ''
        }
        
        if pd.isna(inn_value) or str(inn_value).strip() == '':
            print(f"Строка {row_index + 1}: Пустой ИНН, пропускаем")
            return result
        
        inn_str = str(inn_value).strip()
        print(f"Строка {row_index + 1}: Обработка ИНН {inn_str}")
        
        try:
            # Поиск в РМСП через парсер
            search_result = self.parser.search_by_inn(inn_str)
            
            if search_result and search_result.get('found', False):
                print(f"  ✅ Найдена информация для ИНН {inn_str}")
                
                result['smsp_robot'] = 'да'
                result['category_robot'] = search_result.get('category', '')
                result['inclusion_date_robot'] = search_result.get('inclusion_date', '')
                result['exclusion_date_robot'] = search_result.get('exclusion_date', '')
                
                print(f"  Категория: {result['category_robot']}")
                print(f"  Дата включения: {result['inclusion_date_robot']}")
                
                # Показываем дату исключения только для категории "Не является субъектом МСП"
                if result['category_robot'] == 'Не является субъектом МСП' and result['exclusion_date_robot']:
                    print(f"  Дата исключения: {result['exclusion_date_robot']}")
                
            else:
                print(f"  ❌ Информация не найдена для ИНН {inn_str}")
                
        except Exception as e:
            print(f"  ❌ Ошибка при поиске ИНН {inn_str}: {e}")
        
        return result
    
    def process_excel_file(self, input_file, output_file=None):
        """
        Основная функция обработки Excel файла
        
        Args:
            input_file (str): Путь к входному файлу
            output_file (str, optional): Путь к выходному файлу
            
        Returns:
            bool: True если обработка прошла успешно
        """
        # Валидация входного файла
        if not self.validate_excel_file(input_file):
            return False
        
        # Загрузка файла
        df = self.load_excel_file(input_file)
        if df is None:
            return False
        
        # Проверка столбцов
        if not self.validate_columns(df):
            return False
        
        # Добавление выходных столбцов
        df = self.add_output_columns(df)
        
        # Инициализация парсера
        self.init_parser()
        
        # Обработка каждой строки
        print(f"\nНачинаем обработку {len(df)} строк...")
        print("=" * 60)
        
        processed_count = 0
        found_count = 0
        
        for index, row in df.iterrows():
            inn_value = row[self.input_columns['inn']]
            contract_date = row[self.input_columns['contract_date']]
            
            # Обработка ИНН
            process_result = self.process_single_inn(inn_value, index)
            
            # Заполнение столбцов результатами
            df.at[index, self.output_columns['smsp_robot']] = process_result['smsp_robot']
            df.at[index, self.output_columns['category_robot']] = process_result['category_robot']
            df.at[index, self.output_columns['inclusion_date_robot']] = process_result['inclusion_date_robot']
            
            # Для даты исключения - только если есть реальная дата, иначе пустая ячейка
            exclusion_date = process_result['exclusion_date_robot']
            if exclusion_date and exclusion_date.strip() and exclusion_date.lower() not in ['не указана', 'не найдена', '(пусто)', 'пусто']:
                df.at[index, self.output_columns['exclusion_date_robot']] = exclusion_date
            else:
                df.at[index, self.output_columns['exclusion_date_robot']] = ''
            
            # Сравнение дат если организация найдена
            if process_result['smsp_robot'] == 'да':
                found_count += 1
                date_discrepancy = self.compare_dates(
                    contract_date, 
                    process_result['inclusion_date_robot']
                )
                df.at[index, self.output_columns['date_discrepancy_robot']] = date_discrepancy
                
                if date_discrepancy == 'да':
                    print(f"  ⚠️ Обнаружено расхождение в датах")
            
            processed_count += 1
            
            # Небольшая пауза между запросами
            time.sleep(1)
        
        print("=" * 60)
        print(f"Обработка завершена!")
        print(f"Всего обработано: {processed_count}")
        print(f"Найдено в РМСП: {found_count}")
        print(f"Не найдено: {processed_count - found_count}")
        
        # Сохранение результата
        if output_file is None:
            # Генерируем имя выходного файла
            input_path = Path(input_file)
            output_file = str(input_path.parent / f"{input_path.stem}_processed{input_path.suffix}")
        
        try:
            df.to_excel(output_file, index=False)
            print(f"✅ Результат сохранен в файл: {output_file}")
            return True
        except Exception as e:
            print(f"❌ Ошибка сохранения файла: {e}")
            return False


def main():
    """Основная функция программы"""
    print("Excel РМСП Процессор")
    print("=" * 50)
    
    # Обработка аргументов командной строки
    if len(sys.argv) < 2:
        print("Использование: python excel_rmsp_processor.py input_file.xlsx [output_file.xlsx] [chromedriver_port]")
        print("\nПример:")
        print("  python excel_rmsp_processor.py companies.xlsx")
        print("  python excel_rmsp_processor.py companies.xlsx processed.xlsx")
        print("  python excel_rmsp_processor.py companies.xlsx processed.xlsx 64095")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].isdigit() else None
    
    # Определение порта ChromeDriver
    chromedriver_port = 64095
    if len(sys.argv) > 2:
        # Если второй аргумент - число, то это порт
        if sys.argv[2].isdigit():
            chromedriver_port = int(sys.argv[2])
        # Если третий аргумент - число, то это порт
        elif len(sys.argv) > 3 and sys.argv[3].isdigit():
            chromedriver_port = int(sys.argv[3])
    
    print(f"Входной файл: {input_file}")
    print(f"Выходной файл: {output_file or 'автогенерация'}")
    print(f"Порт ChromeDriver: {chromedriver_port}")
    print()
    
    # Создание и запуск процессора
    processor = ExcelRMSPProcessor(chromedriver_port)
    success = processor.process_excel_file(input_file, output_file)
    
    if success:
        print("\n🎉 Обработка завершена успешно!")
    else:
        print("\n❌ Обработка завершена с ошибками")
        sys.exit(1)


if __name__ == "__main__":
    main()
