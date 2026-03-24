import sqlite3
import streamlit as st

from static_data import fish_data, crops_data, store_data

DB_NAME = "duduta_experiment.db"

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

@st.cache_resource
def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fertilizer BOOLEAN,
            crop_type TEXT,
            water_stars INTEGER,
            weed_bitmap TEXT,
            weed_removed BOOLEAN,
            unattended_time INTEGER,
            planted_count INTEGER,
            star_1 INTEGER,
            star_2 INTEGER,
            star_3 INTEGER,
            star_4 INTEGER,
            star_5 INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    c.execute("PRAGMA table_info(experiments)")
    columns = [info[1] for info in c.fetchall()]
    if "weed_removed_after" not in columns:
        c.execute(
            "ALTER TABLE experiments ADD COLUMN weed_removed_after BOOLEAN DEFAULT 0"
        )

    c.execute("PRAGMA table_info(experiments)")
    columns = [info[1] for info in c.fetchall()]
    if "weed_location_map" in columns:
        try:
            c.execute("ALTER TABLE experiments DROP COLUMN weed_location_map")
        except sqlite3.OperationalError:
            pass

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS cooking_experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_name TEXT,
            cook_count INTEGER,
            star_1 INTEGER,
            star_2 INTEGER,
            star_3 INTEGER,
            star_4 INTEGER,
            star_5 INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS foraging_experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rainbow_buff BOOLEAN,
            duration_minutes FLOAT,
            apples_count INTEGER,
            blueberries_count INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS mushroom_experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mushroom_type TEXT,
            rainbow_buff BOOLEAN,
            duration_minutes FLOAT,
            gathered_count INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS raspberry_experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rainbow_buff BOOLEAN,
            duration_minutes FLOAT,
            gathered_count INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS fishing_experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT,
            weather TEXT,
            time_period TEXT,
            rainbow_buff BOOLEAN,
            duration_minutes FLOAT,
            catches_json TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    c.execute("DROP TABLE IF EXISTS fish_reference")
    c.execute(
        """
        CREATE TABLE fish_reference (
            fish_name TEXT PRIMARY KEY,
            location_category TEXT,
            weather_req TEXT,
            time_req TEXT,
            shadow_size TEXT,
            star_1 INTEGER,
            star_2 INTEGER,
            star_3 INTEGER,
            star_4 INTEGER,
            star_5 INTEGER
        )
    """
    )

    c.executemany(
        """
        INSERT OR REPLACE INTO fish_reference 
        (fish_name, location_category, weather_req, time_req, shadow_size, star_1, star_2, star_3, star_4, star_5)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        fish_data,
    )

    c.execute("DROP TABLE IF EXISTS crop_reference")
    c.execute(
        """
        CREATE TABLE crop_reference (
            crop_name TEXT PRIMARY KEY,
            growth_time TEXT,
            seed_cost INTEGER,
            star_1_price INTEGER,
            star_2_price INTEGER,
            star_3_price INTEGER,
            star_4_price INTEGER,
            star_5_price INTEGER
        )
    """
    )

    c.executemany(
        """
        INSERT OR REPLACE INTO crop_reference 
        (crop_name, growth_time, seed_cost, star_1_price, star_2_price, star_3_price, star_4_price, star_5_price)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        crops_data,
    )

    c.execute("DROP TABLE IF EXISTS store_reference")
    c.execute(
        """
        CREATE TABLE store_reference (
            ingredient_name TEXT PRIMARY KEY,
            discounted_price INTEGER,
            base_price INTEGER
        )
    """
    )

    c.executemany(
        """
        INSERT OR REPLACE INTO store_reference 
        (ingredient_name, discounted_price, base_price)
        VALUES (?, ?, ?)
    """,
        store_data,
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS store_discounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_date TEXT,
            ingredient_name TEXT,
            is_discounted BOOLEAN,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(record_date, ingredient_name)
        )
    """
    )

    # (기존 코드) store_discounts 테이블 생성 코드 아래에 추가
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS custom_recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_name TEXT,
            ingredients TEXT,
            s1_price INTEGER,
            s2_price INTEGER,
            s3_price INTEGER,
            s4_price INTEGER,
            s5_price INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    conn.commit()
    conn.close()
