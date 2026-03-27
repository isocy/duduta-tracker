import psycopg2
import streamlit as st
from static_data import fish_data, crops_data, store_data

def get_connection():
    # secrets.toml 또는 Streamlit Cloud 설정에서 주소를 가져옵니다.
    return psycopg2.connect(st.secrets["DATABASE_URL"])

@st.cache_resource
def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS experiments (
            id SERIAL PRIMARY KEY,
            fertilizer BOOLEAN,
            crop_type TEXT,
            water_stars INTEGER,
            weed_bitmap TEXT,
            weed_removed BOOLEAN,
            weed_removed_after BOOLEAN DEFAULT FALSE,
            unattended_time INTEGER,
            planted_count INTEGER,
            star_1 INTEGER,
            star_2 INTEGER,
            star_3 INTEGER,
            star_4 INTEGER,
            star_5 INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS cooking_experiments (
            id SERIAL PRIMARY KEY,
            recipe_name TEXT,
            cook_count INTEGER,
            star_1 INTEGER,
            star_2 INTEGER,
            star_3 INTEGER,
            star_4 INTEGER,
            star_5 INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS foraging_experiments (
            id SERIAL PRIMARY KEY,
            rainbow_buff BOOLEAN,
            duration_minutes FLOAT,
            apples_count INTEGER,
            blueberries_count INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS mushroom_experiments (
            id SERIAL PRIMARY KEY,
            mushroom_type TEXT,
            rainbow_buff BOOLEAN,
            duration_minutes FLOAT,
            gathered_count INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS raspberry_experiments (
            id SERIAL PRIMARY KEY,
            rainbow_buff BOOLEAN,
            duration_minutes FLOAT,
            gathered_count INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS fishing_experiments (
            id SERIAL PRIMARY KEY,
            location TEXT,
            weather TEXT,
            time_period TEXT,
            rainbow_buff BOOLEAN,
            duration_minutes FLOAT,
            catches_json TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS fish_reference (
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
        INSERT INTO fish_reference 
        (fish_name, location_category, weather_req, time_req, shadow_size, star_1, star_2, star_3, star_4, star_5)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (fish_name) DO UPDATE SET
            location_category = EXCLUDED.location_category,
            weather_req = EXCLUDED.weather_req,
            time_req = EXCLUDED.time_req,
            shadow_size = EXCLUDED.shadow_size,
            star_1 = EXCLUDED.star_1,
            star_2 = EXCLUDED.star_2,
            star_3 = EXCLUDED.star_3,
            star_4 = EXCLUDED.star_4,
            star_5 = EXCLUDED.star_5
    """,
        fish_data,
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS crop_reference (
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
        INSERT INTO crop_reference 
        (crop_name, growth_time, seed_cost, star_1_price, star_2_price, star_3_price, star_4_price, star_5_price)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (crop_name) DO UPDATE SET
            growth_time = EXCLUDED.growth_time,
            seed_cost = EXCLUDED.seed_cost,
            star_1_price = EXCLUDED.star_1_price,
            star_2_price = EXCLUDED.star_2_price,
            star_3_price = EXCLUDED.star_3_price,
            star_4_price = EXCLUDED.star_4_price,
            star_5_price = EXCLUDED.star_5_price
    """,
        crops_data,
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS store_reference (
            ingredient_name TEXT PRIMARY KEY,
            discounted_price INTEGER,
            base_price INTEGER
        )
    """
    )

    c.executemany(
        """
        INSERT INTO store_reference 
        (ingredient_name, discounted_price, base_price)
        VALUES (%s, %s, %s)
        ON CONFLICT (ingredient_name) DO UPDATE SET
            discounted_price = EXCLUDED.discounted_price,
            base_price = EXCLUDED.base_price
    """,
        store_data,
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS store_discounts (
            id SERIAL PRIMARY KEY,
            record_date TEXT,
            ingredient_name TEXT,
            is_discounted BOOLEAN,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(record_date, ingredient_name)
        )
    """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS custom_recipes (
            id SERIAL PRIMARY KEY,
            recipe_name TEXT,
            ingredients TEXT,
            s1_price INTEGER,
            s2_price INTEGER,
            s3_price INTEGER,
            s4_price INTEGER,
            s5_price INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS custom_ingredients (
            id SERIAL PRIMARY KEY,
            name TEXT,
            price INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS custom_crops (
            id SERIAL PRIMARY KEY,
            name TEXT,
            growth_time_mins INTEGER,
            s1_price INTEGER,
            s2_price INTEGER,
            s3_price INTEGER,
            s4_price INTEGER,
            s5_price INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    conn.commit()
    conn.close()
