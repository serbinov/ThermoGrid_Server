#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Скрипт для проверки структуры базы данных ThermoGrid
"""

import sqlite3
import sys

def check_db_structure(db_path="thermogrid.db"):
    """Проверяет структуру таблиц в базе данных"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print(f"Проверка структуры базы данных: {db_path}")
        print("-" * 50)
        
        # Получаем список всех таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"Найдено таблиц: {len(tables)}")
        
        # Для каждой таблицы выводим структуру
        for table in tables:
            table_name = table[0]
            print(f"\nТаблица: {table_name}")
            
            # Получаем информацию о столбцах
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            print("Колонки:")
            for col in columns:
                col_id, name, type_, notnull, default_val, pk = col
                print(f"  - {name} ({type_})" + (" PRIMARY KEY" if pk else ""))
            
            # Получаем первые 3 строки для примера данных
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
            rows = cursor.fetchall()
            
            if rows:
                print(f"\nПример данных ({min(3, len(rows))} записей):")
                for row in rows:
                    print(f"  {row}")
            else:
                print("\nТаблица пуста")
        
        return True
    except Exception as e:
        print(f"Ошибка при проверке базы данных: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    db_path = "thermogrid.db"
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    check_db_structure(db_path)