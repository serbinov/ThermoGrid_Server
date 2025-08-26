#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ThermoGrid - Обновление базы данных для AI подписки
=================================================
Добавляет таблицы для управления подпиской на ИИ функции
"""

import sqlite3
import logging
import time
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def update_database_for_ai_subscription(db_path="thermogrid.db"):
    """Обновляет БД для поддержки AI подписки"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Создаем таблицу subscriptions для отслеживания подписок
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT DEFAULT 'default_user',
                subscription_type TEXT DEFAULT 'ai_basic',
                status TEXT DEFAULT 'inactive',
                start_date INTEGER,
                end_date INTEGER,
                payment_method TEXT,
                amount REAL DEFAULT 9.99,
                created_at INTEGER DEFAULT (strftime('%s','now')),
                updated_at INTEGER DEFAULT (strftime('%s','now'))
            )
        """)
        
        # Добавляем настройки AI подписки в таблицу settings
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", 
                      ('ai_subscription_enabled', 'true'))
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", 
                      ('ai_features_active', 'false'))
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", 
                      ('ai_monthly_price', '9.99'))
        
        # Создаем индекс для оптимизации запросов подписок
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_subscriptions_user_status 
            ON subscriptions (user_id, status, end_date)
        """)
        
        conn.commit()
        logger.info("База данных успешно обновлена для поддержки AI подписки")
        
        # Проверяем, есть ли активная подписка, если нет - добавляем тестовую
        cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE status = 'active'")
        if cursor.fetchone()[0] == 0:
            # Создаем демо подписку на 30 дней
            start_time = int(time.time())
            end_time = start_time + (30 * 24 * 60 * 60)  # 30 дней
            
            cursor.execute("""
                INSERT INTO subscriptions 
                (user_id, subscription_type, status, start_date, end_date, payment_method, amount)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, ('demo_user', 'ai_basic', 'trial', start_time, end_time, 'demo', 0.00))
            
            conn.commit()
            logger.info("Создана демо подписка на AI функции (30 дней)")
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении базы данных: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def get_subscription_status(db_path="thermogrid.db", user_id="default_user"):
    """Получает статус подписки пользователя"""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        current_time = int(time.time())
        
        cursor.execute("""
            SELECT * FROM subscriptions 
            WHERE user_id = ? AND status IN ('active', 'trial') AND end_date > ?
            ORDER BY end_date DESC LIMIT 1
        """, (user_id, current_time))
        
        subscription = cursor.fetchone()
        if subscription:
            return dict(subscription)
        return None
        
    except Exception as e:
        logger.error(f"Ошибка при получении статуса подписки: {e}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    if update_database_for_ai_subscription():
        print("✅ База данных успешно обновлена для AI подписки")
        
        # Проверяем статус подписки
        status = get_subscription_status()
        if status:
            print(f"📊 Найдена подписка: {status['subscription_type']} ({status['status']})")
            end_date = datetime.fromtimestamp(status['end_date'])
            print(f"📅 Действует до: {end_date.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print("❌ Активная подписка не найдена")
    else:
        print("❌ Ошибка при обновлении базы данных")