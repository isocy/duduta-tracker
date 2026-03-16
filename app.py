import streamlit as st
import sqlite3
import pandas as pd
import math
import json
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ==========================================
# [LLM SYSTEM MEMO / AI 참조용 메모]
# 1. 요리 단가 및 효율 계산 시, 과일 채집 탭에서 측정된 '사과(Apple)'의 분당 획득 효율을
#    '귤(Mandarin)'의 채집 효율과 완전히 동일하게 취급하여 계산할 것.
# ==========================================


# --- 한국 시간(KST) 계산 함수 ---
def get_kst_now():
    # 서버 환경(UTC)을 고려해 명시적으로 +9시간을 더해 문자열로 반환
    return (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")


def get_kst_date():
    return (datetime.utcnow() + timedelta(hours=9)).date()


# --- 데이터베이스 초기화 및 연결 ---
DB_NAME = "duduta_experiment.db"


def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


def init_db():
    conn = get_connection()
    c = conn.cursor()

    # 원예 실험 테이블
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
    if "weed_location_map" in columns:
        try:
            c.execute("ALTER TABLE experiments DROP COLUMN weed_location_map")
        except sqlite3.OperationalError:
            pass

    # 요리 실험 테이블
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

    # 과일 채집 실험 테이블
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

    # 버섯 채집 실험 테이블
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

    # 라즈베리 채집 실험 테이블
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

    # 낚시 실험 테이블 (새로 추가)
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

    # 낚시 메타데이터 (Star Ratings, Weather, Time, Shadow Size 추가)
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

    fish_data = [
        # Sea Fishing
        (
            "Striped Red Mullet",
            "Sea Fishing",
            "☀️🌧️❄️🌈",
            "All day",
            "Golden",
            320,
            480,
            640,
            1280,
            2560,
        ),
        (
            "Common Octopus",
            "Sea Fishing",
            "☀️🌧️❄️🌈",
            "All day",
            "Med, Golden",
            320,
            480,
            640,
            1280,
            2560,
        ),
        (
            "Anglerfish",
            "Sea Fishing",
            "☀️🌧️❄️🌈",
            "All day",
            "Golden",
            320,
            480,
            640,
            1280,
            2560,
        ),
        (
            "Turbot",
            "Sea Fishing",
            "☀️🌧️❄️🌈",
            "All day",
            "Medium",
            320,
            480,
            640,
            1280,
            2560,
        ),
        (
            "European Flying Squid",
            "Sea Fishing",
            "☀️🌧️❄️🌈",
            "All day",
            "Golden",
            320,
            480,
            640,
            1280,
            2560,
        ),
        (
            "Nursehound",
            "Sea Fishing",
            "☀️🌧️❄️🌈",
            "All day",
            "Lrg, Golden",
            535,
            802,
            1070,
            2140,
            4280,
        ),
        (
            "Giant Oarfish",
            "Sea Fishing",
            "☀️🌧️❄️🌈",
            "7AM-7PM",
            "Golden",
            535,
            802,
            1070,
            2140,
            4280,
        ),
        (
            "Golden King Crab",
            "Sea Fishing",
            "🌈",
            "All day",
            "Golden",
            850,
            1275,
            1700,
            3400,
            None,
        ),
        (
            "Moonfish",
            "Sea Fishing",
            "☀️🌧️❄️🌈",
            "7PM-7AM",
            "Golden",
            850,
            1275,
            1700,
            3400,
            None,
        ),
        (
            "Shortfin Mako Shark",
            "Sea Fishing",
            "🌈",
            "7AM-7PM",
            "Golden",
            850,
            1275,
            1700,
            3400,
            None,
        ),
        # Ocean
        ("Sardine", "Ocean", "☀️🌧️❄️🌈", "All day", "Small", 50, 75, 100, 200, 400),
        ("Sea Bass", "Ocean", "☀️🌧️❄️🌈", "All day", "Medium", 75, 112, 150, 300, 600),
        (
            "Skipjack Tuna",
            "Ocean",
            "☀️🌧️❄️🌈",
            "All day",
            "Large",
            210,
            315,
            420,
            840,
            1680,
        ),
        (
            "Rabbit Fish",
            "Ocean",
            "☀️🌧️❄️🌈",
            "All day",
            "Med, Blue",
            320,
            480,
            640,
            1280,
            2560,
        ),
        # Zephyr Sea
        (
            "Beltfish",
            "Zephyr Sea",
            "☀️🌧️❄️🌈",
            "All day",
            "Large",
            105,
            157,
            210,
            420,
            840,
        ),
        (
            "Atlantic Pygmy Octopus",
            "Zephyr Sea",
            "☀️🌧️❄️🌈",
            "All day",
            "Small",
            150,
            225,
            300,
            600,
            1200,
        ),
        (
            "False Scad",
            "Zephyr Sea",
            "☀️🌧️❄️🌈",
            "All day",
            "Medium",
            155,
            232,
            310,
            620,
            1240,
        ),
        (
            "European Lobster",
            "Zephyr Sea",
            "☀️🌧️❄️🌈",
            "7PM-7AM",
            "Medium",
            230,
            345,
            460,
            920,
            1840,
        ),
        (
            "Blackspot Seabream",
            "Zephyr Sea",
            "🌧️❄️🌈",
            "7PM-7AM",
            "Medium",
            230,
            345,
            460,
            920,
            1840,
        ),
        (
            "Bluefin Tuna",
            "Zephyr Sea",
            "🌈",
            "7AM-7PM",
            "Large",
            850,
            1275,
            1700,
            3400,
            None,
        ),
        # East Sea
        (
            "Common Prawn",
            "East Sea",
            "☀️🌧️❄️🌈",
            "All day",
            "Small",
            50,
            75,
            100,
            200,
            400,
        ),
        (
            "Hermit Crab",
            "East Sea",
            "☀️🌧️❄️🌈",
            "All day",
            "Small",
            100,
            150,
            200,
            400,
            800,
        ),
        ("Goby", "East Sea", "☀️🌧️❄️🌈", "7AM-7PM", "Small", 150, 225, 300, 600, 1200),
        (
            "Tub Gurnard",
            "East Sea",
            "🌈",
            "All day",
            "Medium",
            380,
            570,
            760,
            1520,
            None,
        ),
        ("Haddock", "East Sea", "☀️🌈", "1PM-7AM", "Medium", 230, 345, 460, None, None),
        (
            "Ocean Sunfish",
            "East Sea",
            "☀️🌧️❄️🌈",
            "1AM-1PM",
            "Large",
            850,
            1275,
            1700,
            3400,
            None,
        ),
        # Whale Sea
        ("Scad", "Whale Sea", "☀️🌧️❄️🌈", "All day", "Small", 50, 75, 100, 200, 400),
        ("Seahorse", "Whale Sea", "☀️🌧️❄️🌈", "1AM-7PM", "Small", 100, 150, 200, 400, 800),
        (
            "Atlantic Salmon",
            "Whale Sea",
            "☀️🌧️❄️🌈",
            "1PM-7AM",
            "Medium",
            155,
            232,
            310,
            620,
            1240,
        ),
        (
            "Atlantic Mackerel",
            "Whale Sea",
            "☀️🌈",
            "1PM-1AM",
            "Small",
            150,
            225,
            300,
            600,
            1200,
        ),
        (
            "King Crab",
            "Whale Sea",
            "🌈",
            "7AM-1AM",
            "Large",
            535,
            802,
            1070,
            2140,
            4280,
        ),
        (
            "Swordfish",
            "Whale Sea",
            "🌈",
            "7AM-7PM",
            "Large",
            850,
            1275,
            1700,
            3400,
            None,
        ),
        # Old Sea
        (
            "Sea Stickleback",
            "Old Sea",
            "☀️🌧️❄️🌈",
            "All day",
            "Small",
            50,
            75,
            100,
            200,
            400,
        ),
        ("Clownfish", "Old Sea", "☀️🌧️❄️🌈", "All day", "Small", 100, 150, 200, 400, 800),
        (
            "European Plaice",
            "Old Sea",
            "☀️🌧️❄️🌈",
            "7PM-7AM",
            "Medium",
            230,
            345,
            460,
            920,
            1840,
        ),
        (
            "Pufferfish",
            "Old Sea",
            "☀️🌧️❄️🌈",
            "1PM-1AM",
            "Medium",
            230,
            345,
            460,
            920,
            1840,
        ),
        (
            "European Eel",
            "Old Sea",
            "🌈",
            "7AM-1AM",
            "Medium",
            380,
            570,
            760,
            1520,
            None,
        ),
        (
            "Smooth Hammerhead",
            "Old Sea",
            "🌈",
            "6PM-6AM",
            "Large",
            None,
            None,
            None,
            None,
            None,
        ),
        # Lake
        ("Common Bleak", "Lake", "☀️🌧️❄️🌈", "All day", "Small", 50, 75, 100, 200, 400),
        ("Common Chub", "Lake", "☀️🌧️❄️🌈", "All day", "Medium", 75, 112, 150, 300, 600),
        ("Edible Frog", "Lake", "☀️🌧️❄️🌈", "All day", "Blue", 320, 480, 640, 1280, None),
        # Forest Lake
        ("Tench", "Forest Lake", "☀️🌧️❄️🌈", "All day", "Small", 50, 75, 100, 200, 400),
        (
            "Largemouth Bass",
            "Forest Lake",
            "☀️🌈",
            "All day",
            "Medium",
            230,
            345,
            460,
            920,
            1840,
        ),
        (
            "Mud Sunfish",
            "Forest Lake",
            "☀️🌧️❄️🌈",
            "7AM-2AM",
            "Small",
            100,
            150,
            200,
            400,
            800,
        ),
        (
            "European Crayfish",
            "Forest Lake",
            "☀️🌧️❄️🌈",
            "7PM-1PM",
            "Small",
            100,
            150,
            200,
            400,
            800,
        ),
        (
            "Large Pearl Mussel",
            "Forest Lake",
            "🌈",
            "All day",
            "Medium",
            380,
            570,
            760,
            1520,
            None,
        ),
        (
            "Blue European Crayfish",
            "Forest Lake",
            "☀️🌧️❄️🌈",
            "7PM-7AM",
            "Small",
            250,
            375,
            500,
            1000,
            None,
        ),
        (
            "Arctic Char",
            "Forest Lake",
            "🌧️❄️🌈",
            "1PM-1AM",
            "Medium",
            610,
            915,
            1220,
            2440,
            None,
        ),
        # Meadow Lake
        (
            "European Smelt",
            "Meadow Lake",
            "☀️🌧️❄️🌈",
            "All day",
            "Medium",
            100,
            150,
            200,
            400,
            800,
        ),
        ("Trout", "Meadow Lake", "☀️🌈", "7PM-7AM", "Medium", 230, 345, 460, 920, 1840),
        (
            "Butterfly Koi",
            "Meadow Lake",
            "🌧️❄️🌈",
            "All day",
            "Large",
            320,
            480,
            640,
            1280,
            2560,
        ),
        (
            "Goldfish",
            "Meadow Lake",
            "🌧️❄️🌈",
            "7AM-1AM",
            "Small",
            250,
            375,
            500,
            1000,
            None,
        ),
        (
            "Wels Catfish",
            "Meadow Lake",
            "☀️🌈",
            "7PM-7AM",
            "Medium",
            610,
            915,
            1220,
            2440,
            None,
        ),
        # Suburban Lake
        (
            "Crucian Carp",
            "Suburban Lake",
            "☀️🌧️❄️🌈",
            "All day",
            "Medium",
            75,
            112,
            150,
            300,
            600,
        ),
        (
            "Schneider",
            "Suburban Lake",
            "☀️🌧️❄️🌈",
            "All day",
            "Small",
            50,
            75,
            100,
            200,
            400,
        ),
        (
            "Stone Loach",
            "Suburban Lake",
            "☀️🌧️❄️🌈",
            "All day",
            "Small",
            100,
            150,
            200,
            400,
            800,
        ),
        (
            "Mussel",
            "Suburban Lake",
            "🌧️❄️🌈",
            "All day",
            "Small",
            100,
            150,
            200,
            400,
            800,
        ),
        (
            "River Crab",
            "Suburban Lake",
            "☀️🌧️❄️🌈",
            "All day",
            "Small",
            100,
            150,
            200,
            400,
            800,
        ),
        (
            "Common Rudd",
            "Suburban Lake",
            "☀️🌧️❄️🌈",
            "All day",
            "Small",
            150,
            225,
            300,
            600,
            1200,
        ),
        (
            "Grayling",
            "Suburban Lake",
            "☀️🌧️❄️🌈",
            "All day",
            "Medium",
            230,
            345,
            460,
            920,
            1840,
        ),
        (
            "Mediterranean Killifish",
            "Suburban Lake",
            "☀️🌈",
            "1PM-7AM",
            "Small",
            150,
            225,
            300,
            600,
            1200,
        ),
        (
            "European Mudminnow",
            "Suburban Lake",
            "☀️🌈",
            "1AM-1PM",
            "Small",
            250,
            375,
            500,
            1000,
            None,
        ),
        (
            "Northern Pike",
            "Suburban Lake",
            "🌧️❄️🌈",
            "7PM-7AM",
            "Medium",
            610,
            915,
            1220,
            2440,
            None,
        ),
        # Onsen Mountain Lake
        (
            "Common Whitefish",
            "Onsen Mountain Lake",
            "☀️🌧️❄️🌈",
            "All day",
            "Medium",
            105,
            157,
            210,
            420,
            840,
        ),
        (
            "Ruffe",
            "Onsen Mountain Lake",
            "☀️🌧️❄️🌈",
            "1PM-1AM",
            "Small",
            100,
            150,
            200,
            400,
            800,
        ),
        (
            "Tadpole",
            "Onsen Mountain Lake",
            "🌧️❄️🌈",
            "All day",
            "Small",
            100,
            150,
            200,
            400,
            800,
        ),
        (
            "Mottled Sculpin",
            "Onsen Mountain Lake",
            "🌧️❄️🌈",
            "7AM-1AM",
            "Small",
            150,
            225,
            300,
            600,
            1200,
        ),
        (
            "Pumpkinseed",
            "Onsen Mountain Lake",
            "☀️🌈",
            "7AM-1AM",
            "Small",
            250,
            375,
            500,
            1000,
            None,
        ),
        (
            "Bluegill",
            "Onsen Mountain Lake",
            "☀️🌈",
            "7PM-7AM",
            "Small",
            395,
            None,
            790,
            None,
            None,
        ),
        # Rivers
        (
            "European Perch",
            "Rivers",
            "☀️🌧️❄️🌈",
            "All day",
            "Medium",
            75,
            112,
            150,
            300,
            600,
        ),
        (
            "Oriental Shrimp",
            "Rivers",
            "☀️🌧️❄️🌈",
            "All day",
            "Small",
            50,
            75,
            100,
            200,
            400,
        ),
        (
            "Tilapia",
            "Rivers",
            "☀️🌧️❄️🌈",
            "All day",
            "Med, Blue",
            320,
            480,
            640,
            1280,
            2560,
        ),
        # Shallow River
        (
            "Barbel",
            "Shallow River",
            "☀️🌧️❄️🌈",
            "All day",
            "Medium",
            75,
            112,
            150,
            300,
            600,
        ),
        (
            "Three-Spined Stickleback",
            "Shallow River",
            "🌧️❄️🌈",
            "All day",
            "Small",
            150,
            225,
            300,
            600,
            1200,
        ),
        # Tranquil River
        (
            "Minnow",
            "Tranquil River",
            "☀️🌧️❄️🌈",
            "All day",
            "Small",
            50,
            75,
            100,
            200,
            400,
        ),
        (
            "Burbot",
            "Tranquil River",
            "☀️🌧️❄️🌈",
            "1PM-1AM",
            "Large",
            230,
            345,
            460,
            920,
            1840,
        ),
        (
            "Chum Salmon",
            "Tranquil River",
            "🌈",
            "All day",
            "Small",
            150,
            225,
            300,
            600,
            1200,
        ),
        # Giantwood River
        (
            "Spined Loach",
            "Giantwood River",
            "☀️🌧️❄️🌈",
            "All day",
            "Small",
            50,
            75,
            100,
            200,
            400,
        ),
        (
            "Zander",
            "Giantwood River",
            "☀️🌈",
            "All day",
            "Medium",
            230,
            345,
            460,
            920,
            1840,
        ),
        (
            "Red-Bellied Piranha",
            "Giantwood River",
            "☀️🌧️❄️🌈",
            "All day",
            "Medium",
            230,
            345,
            460,
            920,
            1840,
        ),
        (
            "Huchen",
            "Giantwood River",
            "🌈",
            "1PM-7AM",
            "Medium",
            380,
            570,
            760,
            1520,
            None,
        ),
        # Rosy River
        ("Streber", "Rosy River", "☀️🌧️❄️🌈", "All day", "Small", 50, 75, 100, 200, 400),
        (
            "Common Carp",
            "Rosy River",
            "☀️🌈",
            "1PM-1AM",
            "Medium",
            50,
            75,
            100,
            200,
            400,
        ),
        (
            "Freshwater Blenny",
            "Rosy River",
            "☀️🌧️❄️🌈",
            "All day",
            "Small",
            150,
            225,
            300,
            600,
            1200,
        ),
    ]

    c.executemany(
        """
        INSERT OR REPLACE INTO fish_reference 
        (fish_name, location_category, weather_req, time_req, shadow_size, star_1, star_2, star_3, star_4, star_5)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        fish_data,
    )

    # 작물 메타데이터(시간, 원가 및 성급별 가치) 테이블
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

    crops_data = [
        ("Tomato", "15m", 10, 30, 40, 50, 60, 70),
        ("Potato", "1h", 30, 90, 120, 150, 180, 210),
        ("Wheat", "4h", 95, 285, 381, 475, 570, 855),
        ("Lettuce", "8h", 145, 435, 582, 726, 870, 1305),
        ("Pineapple", "30m", 15, 52, 69, 86, 104, None),
        ("Carrot", "2h", 50, 155, 207, 258, 310, None),
        ("Strawberry", "6h", 125, 375, 502, 626, 750, 1125),
        ("Corn", "12h", 170, 515, 690, 860, 1030, 1545),
        ("Grapes", "10h", 160, 480, 643, 801, 960, None),
        ("Eggplant", "7h", 135, 406, 544, 678, 812, 1218),
    ]

    c.executemany(
        """
        INSERT OR REPLACE INTO crop_reference 
        (crop_name, growth_time, seed_cost, star_1_price, star_2_price, star_3_price, star_4_price, star_5_price)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        crops_data,
    )

    # ----------------------------------------------------
    # 상점 식재료 메타데이터 및 할인 트래커 테이블
    # ----------------------------------------------------
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

    store_data = [
        # Massimo Store (40% discount possible)
        ("Meat", 120, 200),
        ("Egg", 60, 100),
        ("Milk", 30, 50),
        ("Cheese", 60, 100),
        ("Butter", 90, 150),
        ("Coffee Beans", 30, 50),
        ("Tea Leaves", 150, 250),
        ("Matcha Powder", 150, 250),
        ("Rice Flour", 30, 50),
        ("Red Bean", 30, 50),
        ("Cooking Oil", 60, 100),
        ("Pasturized Egg", 60, 100),
        # Doris Store (No discounts, fixed prices)
        ("Blue Sugar", 150, 150),
        ("Indigo Sugar", 150, 150),
        ("Violet Sugar", 150, 150),
        ("Red Sugar", 150, 150),
        ("Yellow Sugar", 150, 150),
        ("Orange Sugar", 200, 200),
        ("Green Sugar", 200, 200),
    ]

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

    conn.commit()
    conn.close()


init_db()


# 낚시 헬퍼 함수 (특정 지역 및 날씨에서 잡힐 수 있는 물고기 리스트 반환)
def get_fishes_for_location(location, weather_selection):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT fish_name, location_category, weather_req, time_req, shadow_size FROM fish_reference"
    )
    all_fish = c.fetchall()
    conn.close()

    # UI 선택값을 이모지로 매핑
    weather_emoji = ""
    if "맑음" in weather_selection:
        weather_emoji = "☀️"
    elif "비" in weather_selection:
        weather_emoji = "🌧️"
    elif "무지개" in weather_selection:
        weather_emoji = "🌈"

    available = []
    for f_name, loc_cat, w_req, t_req, s_size in all_fish:
        # DB의 weather_req에 해당 날씨 이모지가 없으면 건너뜀
        if weather_emoji not in w_req:
            continue

        if (
            loc_cat == location
            or (loc_cat == "Lake" and "Lake" in location and location != "Lake")
            or (loc_cat == "Rivers" and "River" in location and location != "Rivers")
            or (
                location == "Sea Fishing" and loc_cat == "Ocean"
            )  # Sea Fishing 선택 시 Ocean 물고기도 포함
        ):
            available.append((f_name, w_req, t_req, s_size))
    return available


# --- 윌슨 점수 신뢰구간(Wilson Score Interval) 계산 ---
def calculate_wilson_ci(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    denominator = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denominator
    spread = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denominator
    return p, max(0.0, center - spread), min(1.0, center + spread)


# --- UI 설정 ---
st.set_page_config(page_title="두두타 원예 & 요리 & 낚시 데이터베이스", layout="wide")

# 사이드바에서 모드 선택
app_mode = st.sidebar.radio(
    "📊 실험 트래커 선택",
    [
        "🌱 원예 (작물) 실험",
        "🍳 요리 실험",
        "🍎 과일 채집 실험",
        "🍓 라즈베리 채집 실험",
        "🍄 버섯 채집 실험",
        "🎣 낚시 실험",
        "🏪 상점 할인 트래커",
        "📈 요리 효율 계산",
    ],
)

if app_mode == "🌱 원예 (작물) 실험":
    st.title("🌱 두두타 원예 실험 트래커")
    tab1, tab2, tab3 = st.tabs(
        ["데이터 입력", "데이터 분석 및 필터링", "데이터 관리(삭제)"]
    )

    with tab1:
        st.header("새로운 원예 실험 결과 입력")

        if "show_success" in st.session_state:
            st.success(st.session_state["show_success"])
            del st.session_state["show_success"]

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("실험 조건")
            fertilizer = st.checkbox("비료 사용 여부", key="g_fert")
            crop_type = st.selectbox(
                "작물 종류",
                [
                    "Tomato",
                    "Potato",
                    "Wheat",
                    "Lettuce",
                    "Pineapple",
                    "Carrot",
                    "Strawberry",
                    "Corn",
                    "Grapes",
                    "Eggplant",
                    "Tea Tree",
                    "Cacao Tree",
                    "Avocado",
                ],
                key="g_crop",
            )
            water_stars = st.slider("물 별 개수", 1, 5, 1, key="g_water")

            st.write("잡초 생성 비트맵 (3-bit)")
            w_col1, w_col2, w_col3 = st.columns(3)
            with w_col1:
                w1 = st.checkbox("1단계 잡초", key="g_w1")
            with w_col2:
                w2 = st.checkbox("2단계 잡초", key="g_w2")
            with w_col3:
                w3 = st.checkbox("3단계 잡초", key="g_w3")
            weed_bitmap_val = f"{int(w1)}{int(w2)}{int(w3)}"

            weed_removed = st.checkbox("잡초 제거 여부", key="g_weed_rm")
            unattended_time = st.number_input(
                "성장 후 방치 시간 (30분 단위 정수)", min_value=0, step=1, key="g_time"
            )

        with col2:
            st.subheader("수확 결과")
            planted_count = st.number_input(
                "심은 작물 개수", min_value=1, step=1, key="g_planted"
            )

            st.write("수확한 아이템 성급별 개수")
            star_1 = st.number_input("1성 아이템 개수", min_value=0, step=1, key="g_s1")
            star_2 = st.number_input("2성 아이템 개수", min_value=0, step=1, key="g_s2")
            star_3 = st.number_input("3성 아이템 개수", min_value=0, step=1, key="g_s3")
            star_4 = st.number_input("4성 아이템 개수", min_value=0, step=1, key="g_s4")
            star_5 = st.number_input("5성 아이템 개수", min_value=0, step=1, key="g_s5")

        st.divider()
        st.subheader("🌿 잡초 위치 생성 지도")
        st.caption("체크된 지도를 바탕으로 하단에 비트맵 문자열이 자동 생성됩니다.")

        for i in range(3):
            for z in range(5):
                for r in range(3):
                    for c in range(3):
                        wkey = f"wmap_{i}_{z}_{r}_{c}"
                        if wkey not in st.session_state:
                            st.session_state[wkey] = False

        map_col1, map_col2 = st.columns(2)

        with map_col1:
            w_tabs = st.tabs(["1차 잡초", "2차 잡초", "3차 잡초"])
            for i in range(3):
                with w_tabs[i]:
                    st.caption(f"**{i+1}차에 '새롭게' 돋아난 잡초 위치만 체크하세요.**")
                    for z in range(5):
                        st.markdown(f"**[{z+1} 구역]**")
                        for r in range(3):
                            cell_cols = st.columns([0.5, 0.5, 0.5, 3])
                            for c in range(3):
                                is_center = r == 1 and c == 1
                                with cell_cols[c]:
                                    st.checkbox(
                                        label=f"{i}_{z}_{r}_{c}",
                                        key=f"wmap_{i}_{z}_{r}_{c}",
                                        disabled=is_center,
                                        label_visibility="collapsed",
                                    )
                        st.write("")

        with map_col2:
            st.markdown("👀 **누적 잡초 (자동반영)**")
            st.caption(
                "1차 ~ 3차에 걸쳐 생성된 **모든 잡초가 누적된 실제 밭의 모습**입니다."
            )
            for z in range(5):
                st.markdown(f"**[{z+1} 구역]**")
                for r in range(3):
                    cell_cols = st.columns([0.5, 0.5, 0.5, 3])
                    for c in range(3):
                        is_center = r == 1 and c == 1
                        is_weed_here = (
                            st.session_state.get(f"wmap_0_{z}_{r}_{c}", False)
                            or st.session_state.get(f"wmap_1_{z}_{r}_{c}", False)
                            or st.session_state.get(f"wmap_2_{z}_{r}_{c}", False)
                        )

                        st.session_state[f"cumul_dummy_{z}_{r}_{c}"] = is_weed_here

                        with cell_cols[c]:
                            st.checkbox(
                                label=f"cumul_{z}_{r}_{c}",
                                key=f"cumul_dummy_{z}_{r}_{c}",
                                disabled=True,
                                label_visibility="collapsed",
                            )
                st.write("")

        bitmaps = []
        for i in range(3):
            bmap = ""
            for r in range(3):
                for z in range(5):
                    for c in range(3):
                        if r == 1 and c == 1:
                            continue
                        val = st.session_state.get(f"wmap_{i}_{z}_{r}_{c}", False)
                        bmap += "1" if val else "0"
            bitmaps.append(bmap)
        final_weed_bitmap = "|".join(bitmaps)

        st.write("")
        st.text_input(
            "📋 생성된 잡초 비트맵 (복사 전용 / DB 저장 안 됨)",
            final_weed_bitmap,
            disabled=True,
        )

        st.write("")
        btn_col1, btn_col2 = st.columns(2)

        with btn_col1:
            if st.button(
                "🗑️ 잡초 지도 초기화", type="secondary", use_container_width=True
            ):
                keys_to_clear = [
                    k
                    for k in st.session_state.keys()
                    if k.startswith("wmap_") or k.startswith("cumul_dummy_")
                ]
                for k in keys_to_clear:
                    del st.session_state[k]
                st.rerun()

        with btn_col2:
            submit_button = st.button(
                "데이터 저장 (실험 결과만)", type="primary", use_container_width=True
            )

            if submit_button:
                conn = get_connection()
                c = conn.cursor()
                c.execute(
                    """
                    INSERT INTO experiments 
                    (fertilizer, crop_type, water_stars, weed_bitmap, weed_removed, unattended_time, 
                     planted_count, star_1, star_2, star_3, star_4, star_5, timestamp) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        fertilizer,
                        crop_type,
                        water_stars,
                        weed_bitmap_val,
                        weed_removed,
                        unattended_time,
                        planted_count,
                        star_1,
                        star_2,
                        star_3,
                        star_4,
                        star_5,
                        get_kst_now(),
                    ),
                )
                conn.commit()
                conn.close()

                keys_to_clear = [
                    k for k in st.session_state.keys() if k.startswith("g_")
                ]
                for k in keys_to_clear:
                    del st.session_state[k]

                st.session_state["show_success"] = (
                    "원예 데이터가 성공적으로 저장되었습니다! (지도는 초기화되지 않았습니다)"
                )
                st.rerun()

    with tab2:
        st.header("원예 실험 결과 분석")
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM experiments", conn)
        conn.close()

        if df.empty:
            st.info("아직 입력된 데이터가 없습니다.")
        else:
            st.sidebar.header("🌱 원예 조건 필터링")
            f_fert = st.sidebar.selectbox("비료 유무", ["전체", "사용(O)", "미사용(X)"])
            f_crop = st.sidebar.selectbox(
                "작물 종류", ["전체"] + list(df["crop_type"].unique())
            )
            f_water = st.sidebar.multiselect(
                "물 별 개수", options=[1, 2, 3, 4, 5], default=[1, 2, 3, 4, 5]
            )
            f_weed_map = st.sidebar.selectbox(
                "잡초 생성 비트맵 (3-bit)", ["전체"] + list(df["weed_bitmap"].unique())
            )
            f_weed_rm = st.sidebar.selectbox(
                "잡초 제거", ["전체", "제거함(O)", "방치함(X)"]
            )

            min_time, max_time = int(df["unattended_time"].min()), int(
                df["unattended_time"].max()
            )
            if min_time == max_time:
                f_time = st.sidebar.slider(
                    "방치 시간", min_time, max_time + 1, (min_time, max_time + 1)
                )
            else:
                f_time = st.sidebar.slider(
                    "방치 시간", min_time, max_time, (min_time, max_time)
                )

            filtered_df = df.copy()
            if f_fert != "전체":
                filtered_df = filtered_df[
                    filtered_df["fertilizer"] == (1 if f_fert == "사용(O)" else 0)
                ]
            if f_crop != "전체":
                filtered_df = filtered_df[filtered_df["crop_type"] == f_crop]
            filtered_df = filtered_df[filtered_df["water_stars"].isin(f_water)]
            if f_weed_map != "전체":
                filtered_df = filtered_df[filtered_df["weed_bitmap"] == f_weed_map]
            if f_weed_rm != "전체":
                filtered_df = filtered_df[
                    filtered_df["weed_removed"]
                    == (1 if f_weed_rm == "제거함(O)" else 0)
                ]
            filtered_df = filtered_df[
                (filtered_df["unattended_time"] >= f_time[0])
                & (filtered_df["unattended_time"] <= f_time[1])
            ]

            st.subheader(f"필터링된 실험 횟수: {len(filtered_df)}회")

            if not filtered_df.empty:
                total_planted = filtered_df["planted_count"].sum()
                total_stars = [
                    filtered_df["star_1"].sum(),
                    filtered_df["star_2"].sum(),
                    filtered_df["star_3"].sum(),
                    filtered_df["star_4"].sum(),
                    filtered_df["star_5"].sum(),
                ]
                total_items = sum(total_stars)

                col_k1, col_k2, col_k3 = st.columns(3)
                col_k1.metric("총 심은 작물 수", total_planted)
                col_k2.metric("총 획득 아이템 수", total_items)
                col_k3.metric(
                    "작물당 평균 드랍률",
                    (
                        f"{total_items / total_planted:.2f}개"
                        if total_planted > 0
                        else "0개"
                    ),
                )

                stats_data = []
                for i, count in enumerate(total_stars):
                    p, lower, upper = calculate_wilson_ci(count, total_items)
                    stats_data.append(
                        {
                            "성급": f"{i+1}성",
                            "획득 수": count,
                            "확률(%)": p * 100,
                            "신뢰구간 하한(%)": lower * 100,
                            "신뢰구간 상한(%)": upper * 100,
                            "오차 범위(±%)": (upper - p) * 100,
                        }
                    )

                stats_df = pd.DataFrame(stats_data)
                st.dataframe(
                    stats_df.style.format(
                        {
                            "확률(%)": "{:.2f}%",
                            "신뢰구간 하한(%)": "{:.2f}%",
                            "신뢰구간 상한(%)": "{:.2f}%",
                            "오차 범위(±%)": "{:.2f}%",
                        }
                    ),
                    use_container_width=True,
                )

                fig = go.Figure()
                fig.add_trace(
                    go.Bar(
                        x=stats_df["성급"],
                        y=stats_df["확률(%)"],
                        error_y=dict(
                            type="data", array=stats_df["오차 범위(±%)"], visible=True
                        ),
                        marker_color=[
                            "#B0C4DE",
                            "#8FBC8F",
                            "#4682B4",
                            "#DAA520",
                            "#FF8C00",
                        ],
                        text=[f"{v:.1f}%" for v in stats_df["확률(%)"]],
                        textposition="auto",
                    )
                )
                fig.update_layout(
                    title="조건별 작물 성급 드랍 확률 및 95% 신뢰구간",
                    xaxis_title="작물 성급",
                    yaxis_title="확률 (%)",
                    yaxis=dict(range=[0, 100]),
                )
                st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.header("저장된 원예 데이터 관리")
        conn = get_connection()
        df_all = pd.read_sql_query(
            "SELECT * FROM experiments ORDER BY id DESC",
            conn,
        )
        conn.close()

        if df_all.empty:
            st.write("삭제할 데이터가 없습니다.")
        else:
            st.dataframe(df_all, use_container_width=True)
            delete_id = st.number_input(
                "삭제할 원예 실험의 ID를 입력하세요",
                min_value=0,
                step=1,
                key="del_gardening",
            )
            if st.button("해당 ID 원예 데이터 삭제", type="primary"):
                conn = get_connection()
                c = conn.cursor()
                c.execute("DELETE FROM experiments WHERE id = ?", (delete_id,))
                conn.commit()
                conn.close()
                st.success(
                    f"ID {delete_id} 데이터가 삭제되었습니다. 새로고침을 해주세요."
                )
                st.rerun()

elif app_mode == "🍳 요리 실험":
    st.title("🍳 두두타 요리 실험 트래커")
    tab1, tab2, tab3 = st.tabs(
        ["요리 데이터 입력", "요리 데이터 분석 및 필터링", "요리 데이터 관리(삭제)"]
    )

    conn = get_connection()
    recipe_df = pd.read_sql_query(
        "SELECT DISTINCT recipe_name FROM cooking_experiments ORDER BY recipe_name",
        conn,
    )
    conn.close()
    existing_recipes = recipe_df["recipe_name"].tolist()

    with tab1:
        st.header("새로운 요리 실험 결과 입력")

        with st.form("cooking_input_form", clear_on_submit=True):
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("요리 조건")

                recipe_options = ["(새로운 레시피 직접 입력)"] + existing_recipes
                selected_recipe = st.selectbox("레시피 선택", recipe_options)

                new_recipe_name = st.text_input(
                    "새로운 레시피 이름 (위에서 '(새로운 레시피 직접 입력)' 선택 시 작성)"
                )

                cook_count = st.number_input("요리 시도 횟수", min_value=1, step=1)

            with col2:
                st.subheader("요리 결과 (성급별 개수)")
                st.write("완성된 요리의 성급별 개수를 입력하세요.")
                c_star_1 = st.number_input(
                    "1성 요리 개수", min_value=0, step=1, key="c_s1"
                )
                c_star_2 = st.number_input(
                    "2성 요리 개수", min_value=0, step=1, key="c_s2"
                )
                c_star_3 = st.number_input(
                    "3성 요리 개수", min_value=0, step=1, key="c_s3"
                )
                c_star_4 = st.number_input(
                    "4성 요리 개수", min_value=0, step=1, key="c_s4"
                )
                c_star_5 = st.number_input(
                    "5성 요리 개수", min_value=0, step=1, key="c_s5"
                )

            submit_button = st.form_submit_button(label="요리 데이터 저장")

            if submit_button:
                final_recipe_name = (
                    new_recipe_name.strip()
                    if selected_recipe == "(새로운 레시피 직접 입력)"
                    else selected_recipe
                )

                if not final_recipe_name:
                    st.error("레시피 이름을 입력하거나 선택해주세요!")
                else:
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute(
                        """
                        INSERT INTO cooking_experiments 
                        (recipe_name, cook_count, star_1, star_2, star_3, star_4, star_5, timestamp) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            final_recipe_name,
                            cook_count,
                            c_star_1,
                            c_star_2,
                            c_star_3,
                            c_star_4,
                            c_star_5,
                            get_kst_now(),
                        ),
                    )
                    conn.commit()
                    conn.close()
                    st.success(
                        f"[{final_recipe_name}] 요리 데이터가 성공적으로 저장되었습니다!"
                    )

    with tab2:
        st.header("요리 실험 결과 분석")
        conn = get_connection()
        df_cook = pd.read_sql_query("SELECT * FROM cooking_experiments", conn)
        conn.close()

        if df_cook.empty:
            st.info("아직 입력된 요리 데이터가 없습니다.")
        else:
            st.sidebar.header("🍳 요리 조건 필터링")
            f_recipe = st.sidebar.selectbox(
                "레시피 이름", ["전체"] + list(df_cook["recipe_name"].unique())
            )

            filtered_cook = df_cook.copy()
            if f_recipe != "전체":
                filtered_cook = filtered_cook[filtered_cook["recipe_name"] == f_recipe]

            st.subheader(f"필터링된 요리 실험 기록 수: {len(filtered_cook)}건")

            if not filtered_cook.empty:
                total_cooks = filtered_cook["cook_count"].sum()
                total_c_stars = [
                    filtered_cook["star_1"].sum(),
                    filtered_cook["star_2"].sum(),
                    filtered_cook["star_3"].sum(),
                    filtered_cook["star_4"].sum(),
                    filtered_cook["star_5"].sum(),
                ]
                total_c_items = sum(total_c_stars)

                col_c1, col_c2 = st.columns(2)
                col_c1.metric("총 요리 시도 횟수", total_cooks)
                col_c2.metric("총 획득 요리 개수", total_c_items)

                stats_data_c = []
                for i, count in enumerate(total_c_stars):
                    p, lower, upper = calculate_wilson_ci(count, total_c_items)
                    stats_data_c.append(
                        {
                            "성급": f"{i+1}성",
                            "획득 수": count,
                            "확률(%)": p * 100,
                            "신뢰구간 하한(%)": lower * 100,
                            "신뢰구간 상한(%)": upper * 100,
                            "오차 범위(±%)": (upper - p) * 100,
                        }
                    )

                stats_df_c = pd.DataFrame(stats_data_c)
                st.dataframe(
                    stats_df_c.style.format(
                        {
                            "확률(%)": "{:.2f}%",
                            "신뢰구간 하한(%)": "{:.2f}%",
                            "신뢰구간 상한(%)": "{:.2f}%",
                            "오차 범위(±%)": "{:.2f}%",
                        }
                    ),
                    use_container_width=True,
                )

                fig_c = go.Figure()
                fig_c.add_trace(
                    go.Bar(
                        x=stats_df_c["성급"],
                        y=stats_df_c["확률(%)"],
                        error_y=dict(
                            type="data", array=stats_df_c["오차 범위(±%)"], visible=True
                        ),
                        marker_color=[
                            "#D8BFD8",
                            "#DDA0DD",
                            "#BA55D3",
                            "#9932CC",
                            "#4B0082",
                        ],
                        text=[f"{v:.1f}%" for v in stats_df_c["확률(%)"]],
                        textposition="auto",
                    )
                )
                fig_c.update_layout(
                    title="요리 성급별 등장 확률 및 95% 신뢰구간",
                    xaxis_title="요리 성급",
                    yaxis_title="확률 (%)",
                    yaxis=dict(range=[0, 100]),
                )
                st.plotly_chart(fig_c, use_container_width=True)

    with tab3:
        st.header("저장된 요리 데이터 관리")
        conn = get_connection()
        df_cook_all = pd.read_sql_query(
            "SELECT * FROM cooking_experiments ORDER BY id DESC",
            conn,
        )
        conn.close()

        if df_cook_all.empty:
            st.write("삭제할 데이터가 없습니다.")
        else:
            st.dataframe(df_cook_all, use_container_width=True)
            delete_c_id = st.number_input(
                "삭제할 요리 실험의 ID를 입력하세요",
                min_value=0,
                step=1,
                key="del_cooking",
            )
            if st.button("해당 ID 요리 데이터 삭제", type="primary"):
                conn = get_connection()
                c = conn.cursor()
                c.execute(
                    "DELETE FROM cooking_experiments WHERE id = ?", (delete_c_id,)
                )
                conn.commit()
                conn.close()
                st.success(
                    f"ID {delete_c_id} 요리 데이터가 삭제되었습니다. 새로고침을 해주세요."
                )
                st.rerun()

elif app_mode == "🍎 과일 채집 실험":
    st.title("🍎 두두타 과일 채집 효율 트래커")

    st.info(
        "💡 **시스템 메모:** 추후 요리 효율 계산 시, 여기서 측정된 **사과(Apple) 채집 효율**은 **귤(Mandarin) 채집 효율**과 1:1로 동일하게 적용됩니다."
    )

    tab1, tab2, tab3 = st.tabs(
        ["채집 데이터 입력", "채집 효율 분석", "채집 데이터 관리(삭제)"]
    )

    def save_foraging_data():
        duration_m = st.session_state["f_min"]
        duration_s = st.session_state["f_sec"]
        duration = duration_m + (duration_s / 60.0)

        if duration <= 0:
            st.session_state["f_error"] = "소요 시간은 0초보다 길어야 합니다!"
            return

        conn = get_connection()
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO foraging_experiments 
            (rainbow_buff, duration_minutes, apples_count, blueberries_count, timestamp) 
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                st.session_state["f_rainbow"],
                duration,
                st.session_state["f_apples"],
                st.session_state["f_blue"],
                get_kst_now(),
            ),
        )
        conn.commit()
        conn.close()

        st.session_state["f_min"] = 0
        st.session_state["f_sec"] = 0
        st.session_state["f_apples"] = 0
        st.session_state["f_blue"] = 0

        st.session_state["f_success"] = (
            "채집 데이터가 성공적으로 저장되었습니다! (버프 상태는 유지됩니다)"
        )

    with tab1:
        st.header("새로운 채집 결과 입력")

        if "f_success" in st.session_state:
            st.success(st.session_state["f_success"])
            del st.session_state["f_success"]

        if "f_error" in st.session_state:
            st.error(st.session_state["f_error"])
            del st.session_state["f_error"]

        with st.form("foraging_input_form", clear_on_submit=False):
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("채집 조건")
                st.checkbox("🌈 무지개 버프 적용 여부", key="f_rainbow")

                st.write("⏱️ 채집 소요 시간")
                t_col1, t_col2 = st.columns(2)
                with t_col1:
                    st.number_input("분", min_value=0, step=1, key="f_min")
                with t_col2:
                    st.number_input(
                        "초", min_value=0, max_value=59, step=1, key="f_sec"
                    )

            with col2:
                st.subheader("획득 결과")
                st.number_input(
                    "🍎 사과 획득 개수", min_value=0, step=1, key="f_apples"
                )
                st.number_input(
                    "🫐 블루베리 획득 개수", min_value=0, step=1, key="f_blue"
                )

            submit_button = st.form_submit_button(
                label="채집 데이터 저장", on_click=save_foraging_data
            )

    with tab2:
        st.header("무지개 버프 효율 분석")
        conn = get_connection()
        df_foraging = pd.read_sql_query("SELECT * FROM foraging_experiments", conn)
        conn.close()

        if df_foraging.empty:
            st.info("아직 입력된 채집 데이터가 없습니다.")
        else:
            total_time = df_foraging["duration_minutes"].sum()
            total_m = int(total_time)
            total_s = int(round((total_time - total_m) * 60))

            total_apples = df_foraging["apples_count"].sum()
            total_blueberries = df_foraging["blueberries_count"].sum()

            c1, c2, c3 = st.columns(3)
            c1.metric("총 누적 채집 시간", f"{total_m}분 {total_s}초")
            c2.metric("총 획득 사과", f"{total_apples:,} 개")
            c3.metric("총 획득 블루베리", f"{total_blueberries:,} 개")

            st.divider()
            st.subheader("📊 버프 유무에 따른 분당 획득량 비교")

            grouped = (
                df_foraging.groupby("rainbow_buff")[
                    ["duration_minutes", "apples_count", "blueberries_count"]
                ]
                .sum()
                .reset_index()
            )

            grouped["apple_per_min"] = (
                grouped["apples_count"] / grouped["duration_minutes"]
            )
            grouped["blueberry_per_min"] = (
                grouped["blueberries_count"] / grouped["duration_minutes"]
            )
            grouped["total_per_min"] = (
                grouped["apples_count"] + grouped["blueberries_count"]
            ) / grouped["duration_minutes"]
            grouped["buff_status"] = grouped["rainbow_buff"].apply(
                lambda x: "버프 적용 (O)" if x == 1 else "버프 미적용 (X)"
            )

            def format_time(minutes_float):
                m = int(minutes_float)
                s = int(round((minutes_float - m) * 60))
                return f"{m}분 {s}초"

            grouped["formatted_time"] = grouped["duration_minutes"].apply(format_time)

            display_df = grouped[
                [
                    "buff_status",
                    "formatted_time",
                    "apples_count",
                    "blueberries_count",
                    "apple_per_min",
                    "blueberry_per_min",
                    "total_per_min",
                ]
            ].copy()

            display_df.rename(
                columns={
                    "buff_status": "무지개 버프",
                    "formatted_time": "총 소요 시간",
                    "apples_count": "총 사과(개)",
                    "blueberries_count": "총 블루베리(개)",
                    "apple_per_min": "사과 효율 (개/분)",
                    "blueberry_per_min": "블루베리 효율 (개/분)",
                    "total_per_min": "전체 효율 (개/분)",
                },
                inplace=True,
            )

            st.dataframe(
                display_df.style.format(
                    {
                        "사과 효율 (개/분)": "{:.2f}",
                        "블루베리 효율 (개/분)": "{:.2f}",
                        "전체 효율 (개/분)": "{:.2f}",
                    }
                ),
                use_container_width=True,
            )

            fig_f = go.Figure()
            fig_f.add_trace(
                go.Bar(
                    x=grouped["buff_status"],
                    y=grouped["apple_per_min"],
                    name="사과 (개/분)",
                    marker_color="#FF6347",
                    text=[f"{v:.2f}개/분" for v in grouped["apple_per_min"]],
                    textposition="auto",
                )
            )
            fig_f.add_trace(
                go.Bar(
                    x=grouped["buff_status"],
                    y=grouped["blueberry_per_min"],
                    name="블루베리 (개/분)",
                    marker_color="#4682B4",
                    text=[f"{v:.2f}개/분" for v in grouped["blueberry_per_min"]],
                    textposition="auto",
                )
            )
            fig_f.update_layout(
                title="무지개 버프 상태별 분당 채집 효율 비교",
                xaxis_title="버프 상태",
                yaxis_title="효율 (개/분)",
                barmode="group",
            )
            st.plotly_chart(fig_f, use_container_width=True)

    with tab3:
        st.header("저장된 채집 데이터 관리")
        conn = get_connection()
        df_foraging_all = pd.read_sql_query(
            "SELECT * FROM foraging_experiments ORDER BY id DESC", conn
        )
        conn.close()

        if df_foraging_all.empty:
            st.write("삭제할 데이터가 없습니다.")
        else:
            st.dataframe(df_foraging_all, use_container_width=True)
            delete_f_id = st.number_input(
                "삭제할 채집 실험의 ID를 입력하세요",
                min_value=0,
                step=1,
                key="del_foraging",
            )
            if st.button("해당 ID 채집 데이터 삭제", type="primary"):
                conn = get_connection()
                c = conn.cursor()
                c.execute(
                    "DELETE FROM foraging_experiments WHERE id = ?", (delete_f_id,)
                )
                conn.commit()
                conn.close()
                st.success(
                    f"ID {delete_f_id} 채집 데이터가 삭제되었습니다. 새로고침을 해주세요."
                )
                st.rerun()

elif app_mode == "🍓 라즈베리 채집 실험":
    st.title("🍓 두두타 라즈베리 채집 효율 트래커")
    tab1, tab2, tab3 = st.tabs(
        ["채집 데이터 입력", "채집 효율 분석", "채집 데이터 관리(삭제)"]
    )

    def save_raspberry_data():
        duration_m = st.session_state["r_min"]
        duration_s = st.session_state["r_sec"]
        duration = duration_m + (duration_s / 60.0)

        if duration <= 0:
            st.session_state["r_error"] = "소요 시간은 0초보다 길어야 합니다!"
            return

        conn = get_connection()
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO raspberry_experiments 
            (rainbow_buff, duration_minutes, gathered_count, timestamp) 
            VALUES (?, ?, ?, ?)
        """,
            (
                st.session_state["r_rainbow"],
                duration,
                st.session_state["r_count"],
                get_kst_now(),
            ),
        )
        conn.commit()
        conn.close()

        st.session_state["r_min"] = 0
        st.session_state["r_sec"] = 0
        st.session_state["r_count"] = 0

        st.session_state["r_success"] = (
            "라즈베리 채집 데이터가 성공적으로 저장되었습니다! (버프 상태는 유지됩니다)"
        )

    with tab1:
        st.header("새로운 라즈베리 채집 결과 입력")

        if "r_success" in st.session_state:
            st.success(st.session_state["r_success"])
            del st.session_state["r_success"]

        if "r_error" in st.session_state:
            st.error(st.session_state["r_error"])
            del st.session_state["r_error"]

        with st.form("raspberry_input_form", clear_on_submit=False):
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("채집 조건")
                st.checkbox("🌈 무지개 버프 적용 여부", key="r_rainbow")

                st.write("⏱️ 채집 소요 시간")
                t_col1, t_col2 = st.columns(2)
                with t_col1:
                    st.number_input("분", min_value=0, step=1, key="r_min")
                with t_col2:
                    st.number_input(
                        "초", min_value=0, max_value=59, step=1, key="r_sec"
                    )

            with col2:
                st.subheader("획득 결과")
                st.number_input(
                    "🍓 라즈베리 획득 개수", min_value=0, step=1, key="r_count"
                )

            submit_button = st.form_submit_button(
                label="채집 데이터 저장", on_click=save_raspberry_data
            )

    with tab2:
        st.header("무지개 버프 효율 분석")
        conn = get_connection()
        df_rasp = pd.read_sql_query("SELECT * FROM raspberry_experiments", conn)
        conn.close()

        if df_rasp.empty:
            st.info("아직 입력된 라즈베리 채집 데이터가 없습니다.")
        else:
            total_time = df_rasp["duration_minutes"].sum()
            total_m = int(total_time)
            total_s = int(round((total_time - total_m) * 60))
            total_count = df_rasp["gathered_count"].sum()

            c1, c2 = st.columns(2)
            c1.metric("총 누적 채집 시간", f"{total_m}분 {total_s}초")
            c2.metric("총 획득 라즈베리", f"{total_count:,} 개")

            st.divider()
            st.subheader("📊 버프 유무에 따른 분당 획득량 비교")

            grouped = (
                df_rasp.groupby("rainbow_buff")[["duration_minutes", "gathered_count"]]
                .sum()
                .reset_index()
            )

            grouped["per_min"] = grouped["gathered_count"] / grouped["duration_minutes"]
            grouped["buff_status"] = grouped["rainbow_buff"].apply(
                lambda x: "버프 적용 (O)" if x == 1 else "버프 미적용 (X)"
            )

            def format_time(minutes_float):
                m = int(minutes_float)
                s = int(round((minutes_float - m) * 60))
                return f"{m}분 {s}초"

            grouped["formatted_time"] = grouped["duration_minutes"].apply(format_time)

            display_df = grouped[
                [
                    "buff_status",
                    "formatted_time",
                    "gathered_count",
                    "per_min",
                ]
            ].copy()

            display_df.rename(
                columns={
                    "buff_status": "무지개 버프",
                    "formatted_time": "총 소요 시간",
                    "gathered_count": "총 라즈베리(개)",
                    "per_min": "라즈베리 효율 (개/분)",
                },
                inplace=True,
            )

            st.dataframe(
                display_df.style.format({"라즈베리 효율 (개/분)": "{:.2f}"}),
                use_container_width=True,
            )

            fig_r = go.Figure()
            fig_r.add_trace(
                go.Bar(
                    x=grouped["buff_status"],
                    y=grouped["per_min"],
                    name="라즈베리 (개/분)",
                    marker_color="#DC143C",
                    text=[f"{v:.2f}개/분" for v in grouped["per_min"]],
                    textposition="auto",
                )
            )
            fig_r.update_layout(
                title="무지개 버프 상태별 라즈베리 분당 채집 효율 비교",
                xaxis_title="버프 상태",
                yaxis_title="효율 (개/분)",
            )
            st.plotly_chart(fig_r, use_container_width=True)

    with tab3:
        st.header("저장된 라즈베리 데이터 관리")
        conn = get_connection()
        df_rasp_all = pd.read_sql_query(
            "SELECT * FROM raspberry_experiments ORDER BY id DESC", conn
        )
        conn.close()

        if df_rasp_all.empty:
            st.write("삭제할 데이터가 없습니다.")
        else:
            st.dataframe(df_rasp_all, use_container_width=True)
            delete_r_id = st.number_input(
                "삭제할 채집 실험의 ID를 입력하세요",
                min_value=0,
                step=1,
                key="del_raspberry",
            )
            if st.button("해당 ID 채집 데이터 삭제", type="primary"):
                conn = get_connection()
                c = conn.cursor()
                c.execute(
                    "DELETE FROM raspberry_experiments WHERE id = ?", (delete_r_id,)
                )
                conn.commit()
                conn.close()
                st.success(
                    f"ID {delete_r_id} 라즈베리 데이터가 삭제되었습니다. 새로고침을 해주세요."
                )
                st.rerun()

elif app_mode == "🍄 버섯 채집 실험":
    st.title("🍄 두두타 버섯 개별 채집 트래커")

    mushroom_names = {
        "Oyster": "느타리버섯",
        "Shiitake": "표고버섯",
        "Button": "양송이버섯",
        "Penny Bun": "그물버섯",
        "Truffle": "트러플 버섯",
    }

    tabs = st.tabs([f"{kor} ({eng})" for eng, kor in mushroom_names.items()])

    for idx, (m_eng, m_kor) in enumerate(mushroom_names.items()):
        with tabs[idx]:
            st.header(f"[{m_kor}] 채집 데이터 관리")

            st.subheader("1. 새로운 채집 결과 입력")
            with st.form(f"form_{m_eng}", clear_on_submit=True):
                col1, col2 = st.columns(2)

                with col1:
                    buff = st.checkbox("🌈 무지개 버프 적용", key=f"buff_{m_eng}")

                    if m_eng == "Truffle":
                        st.write("⏱️ 채집 소요 시간")
                        st.info(
                            "💡 트러플 버섯은 리젠 시간이 13분으로 고정되어 있어, 저장 시 자동으로 13분이 누적됩니다."
                        )
                        mins = 13
                        secs = 0
                    else:
                        st.write("⏱️ 채집 소요 시간")
                        t_col1, t_col2 = st.columns(2)
                        with t_col1:
                            mins = st.number_input(
                                "분", min_value=0, step=1, key=f"min_{m_eng}"
                            )
                        with t_col2:
                            secs = st.number_input(
                                "초",
                                min_value=0,
                                max_value=59,
                                step=1,
                                key=f"sec_{m_eng}",
                            )

                with col2:
                    st.write("🍄 획득 결과")
                    count = st.number_input(
                        f"{m_kor} 획득 개수", min_value=0, step=1, key=f"count_{m_eng}"
                    )

                submit = st.form_submit_button("데이터 저장")

                if submit:
                    duration = mins + (secs / 60.0)
                    if duration <= 0:
                        st.error("소요 시간은 0초보다 길어야 합니다!")
                    else:
                        conn = get_connection()
                        c = conn.cursor()
                        c.execute(
                            """
                            INSERT INTO mushroom_experiments 
                            (mushroom_type, rainbow_buff, duration_minutes, gathered_count, timestamp)
                            VALUES (?, ?, ?, ?, ?)
                        """,
                            (m_eng, buff, duration, count, get_kst_now()),
                        )
                        conn.commit()
                        conn.close()
                        st.success(
                            f"{m_kor} 채집 데이터가 저장되었습니다! (새로고침하여 통계 확인)"
                        )

            st.divider()

            st.subheader("2. 버프 효율 분석")
            conn = get_connection()
            df_m = pd.read_sql_query(
                "SELECT * FROM mushroom_experiments WHERE mushroom_type = ?",
                conn,
                params=(m_eng,),
            )
            conn.close()

            if df_m.empty:
                st.info("아직 입력된 데이터가 없습니다.")
            else:
                total_time = df_m["duration_minutes"].sum()
                total_m = int(total_time)
                total_s = int(round((total_time - total_m) * 60))
                total_count = df_m["gathered_count"].sum()

                c1, c2 = st.columns(2)
                c1.metric("총 누적 채집 시간", f"{total_m}분 {total_s}초")
                c2.metric(f"총 획득 {m_kor}", f"{total_count:,} 개")

                grouped = (
                    df_m.groupby("rainbow_buff")[["duration_minutes", "gathered_count"]]
                    .sum()
                    .reset_index()
                )
                grouped["per_min"] = (
                    grouped["gathered_count"] / grouped["duration_minutes"]
                )
                grouped["buff_status"] = grouped["rainbow_buff"].apply(
                    lambda x: "버프 적용 (O)" if x == 1 else "버프 미적용 (X)"
                )

                display_df = grouped[
                    ["buff_status", "duration_minutes", "gathered_count", "per_min"]
                ].copy()
                display_df.rename(
                    columns={
                        "buff_status": "무지개 버프",
                        "duration_minutes": "총 소요 시간(분)",
                        "gathered_count": "총 획득량(개)",
                        "per_min": "효율 (개/분)",
                    },
                    inplace=True,
                )

                st.dataframe(
                    display_df.style.format(
                        {"총 소요 시간(분)": "{:.2f}", "효율 (개/분)": "{:.2f}"}
                    ),
                    use_container_width=True,
                )

                fig = go.Figure()
                fig.add_trace(
                    go.Bar(
                        x=grouped["buff_status"],
                        y=grouped["per_min"],
                        text=[f"{v:.2f}개/분" for v in grouped["per_min"]],
                        textposition="auto",
                        marker_color="#8B4513",
                    )
                )
                fig.update_layout(
                    title=f"버프 상태별 {m_kor} 분당 효율",
                    xaxis_title="버프 상태",
                    yaxis_title="효율 (개/분)",
                )
                st.plotly_chart(fig, use_container_width=True)

            st.divider()

            with st.expander(f"🗑️ {m_kor} 데이터 관리(삭제)", expanded=False):
                if df_m.empty:
                    st.write("삭제할 데이터가 없습니다.")
                else:
                    st.dataframe(
                        df_m.sort_values("id", ascending=False),
                        use_container_width=True,
                    )
                    del_id = st.number_input(
                        "삭제할 ID 입력", min_value=0, step=1, key=f"del_{m_eng}"
                    )
                    if st.button(
                        "해당 ID 데이터 삭제", key=f"btn_del_{m_eng}", type="primary"
                    ):
                        conn = get_connection()
                        c = conn.cursor()
                        c.execute(
                            "DELETE FROM mushroom_experiments WHERE id = ?", (del_id,)
                        )
                        conn.commit()
                        conn.close()
                        st.rerun()

# ----------------------------------------------------
# 🎣 낚시 실험
# ----------------------------------------------------
elif app_mode == "🎣 낚시 실험":
    st.title("🎣 두두타 낚시 채집 트래커")
    tab1, tab2, tab3 = st.tabs(["데이터 입력", "효율 분석", "데이터 관리(삭제)"])

    locations = [
        "Sea Fishing",
        "Ocean",
        "Zephyr Sea",
        "East Sea",
        "Whale Sea",
        "Old Sea",
        "Forest Lake",
        "Meadow Lake",
        "Suburban Lake",
        "Onsen Mountain Lake",
        "Shallow River",
        "Tranquil River",
        "Giantwood River",
        "Rosy River",
    ]

    time_periods = [
        "2:00 AM ~ 6:00 AM",
        "6:00 AM ~ 7:00 AM",
        "7:00 AM ~ 1:00 PM",
        "1:00 PM ~ 6:00 PM",
        "6:00 PM ~ 7:00 PM",
        "7:00 PM ~ 1:00 AM",
        "1:00 AM ~ 2:00 AM",
    ]

    with tab1:
        st.header("새로운 낚시 결과 입력")

        col1, col2 = st.columns([1, 1.5])

        with col1:
            st.subheader("기본 조건")
            f_location = st.selectbox("📍 낚시터 선택", locations)
            f_weather = st.selectbox(
                "☁️ 날씨", ["맑음 (Clear)", "비 (Rain)", "무지개 (Rainbow)"]
            )
            f_time = st.selectbox("⏳ 시간대", time_periods)
            f_buff = st.checkbox("🌈 무지개 버프 (Rainbow Buff) 적용")

            st.write("⏱️ 낚시 진행 시간")
            tc1, tc2 = st.columns(2)
            with tc1:
                f_min = st.number_input("분", min_value=0, step=1, key="fish_min")
            with tc2:
                f_sec = st.number_input(
                    "초", min_value=0, max_value=59, step=1, key="fish_sec"
                )

        with col2:
            st.subheader("🐟 획득한 물고기 마릿수 (성급별)")
            # f_weather 파라미터를 추가하여 호출
            available_fishes = get_fishes_for_location(f_location, f_weather)

            fish_counts = {}
            for f_data in available_fishes:
                fish_name = f_data[0]
                # 물고기가 많을 수 있으므로 Expander를 사용해 깔끔하게 배치합니다.
                with st.expander(
                    f"**{fish_name}** | {f_data[1]} | {f_data[2]} | {f_data[3]}"
                ):
                    c1, c2, c3, c4, c5 = st.columns(5)
                    fish_counts[fish_name] = {}
                    with c1:
                        fish_counts[fish_name]["1"] = st.number_input(
                            "1⭐", min_value=0, step=1, key=f"f_{fish_name}_1"
                        )
                    with c2:
                        fish_counts[fish_name]["2"] = st.number_input(
                            "2⭐", min_value=0, step=1, key=f"f_{fish_name}_2"
                        )
                    with c3:
                        fish_counts[fish_name]["3"] = st.number_input(
                            "3⭐", min_value=0, step=1, key=f"f_{fish_name}_3"
                        )
                    with c4:
                        fish_counts[fish_name]["4"] = st.number_input(
                            "4⭐", min_value=0, step=1, key=f"f_{fish_name}_4"
                        )
                    with c5:
                        fish_counts[fish_name]["5"] = st.number_input(
                            "5⭐", min_value=0, step=1, key=f"f_{fish_name}_5"
                        )

        st.write("")
        if st.button("낚시 데이터 저장", type="primary", use_container_width=True):
            duration = f_min + (f_sec / 60.0)
            if duration <= 0:
                st.error("진행 시간은 0초보다 커야 합니다.")
            else:
                final_catches = {}
                total_caught = 0

                # 0마리인 데이터는 제외하고 JSON으로 저장
                for f_name, stars in fish_counts.items():
                    fish_total = sum(stars.values())
                    if fish_total > 0:
                        final_catches[f_name] = stars
                        total_caught += fish_total

                conn = get_connection()
                c = conn.cursor()
                c.execute(
                    """
                    INSERT INTO fishing_experiments 
                    (location, weather, time_period, rainbow_buff, duration_minutes, catches_json, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        f_location,
                        f_weather,
                        f_time,
                        f_buff,
                        duration,
                        json.dumps(final_catches),
                        get_kst_now(),
                    ),
                )
                conn.commit()
                conn.close()
                st.success(
                    f"데이터가 성공적으로 저장되었습니다! (총 {total_caught}마리 기록)"
                )

    with tab2:
        st.header("특정 물고기 포획 효율 분석")
        st.caption(
            "※ 평균 소요 시간 = (해당 물고기가 잡힌 모든 세션의 총 소요 시간) / (해당 물고기의 총 포획 수)"
        )

        conn = get_connection()
        df_fish = pd.read_sql_query("SELECT * FROM fishing_experiments", conn)
        conn.close()

        if df_fish.empty:
            st.info("아직 낚시 데이터가 없습니다.")
        else:
            records = []
            for _, row in df_fish.iterrows():
                try:
                    catches = json.loads(row["catches_json"])
                except:
                    continue

                for fish, count_data in catches.items():
                    # 호환성 처리: 예전 방식(정수)과 새로운 방식(딕셔너리) 모두 지원
                    if isinstance(count_data, int):
                        total_count = count_data
                    else:
                        total_count = sum(count_data.values())

                    if total_count > 0:
                        records.append(
                            {
                                "id": row["id"],
                                "location": row["location"],
                                "weather": row["weather"],
                                "time_period": row["time_period"],
                                "rainbow_buff": row["rainbow_buff"],
                                "duration_minutes": row["duration_minutes"],
                                "fish_name": fish,
                                "count": total_count,
                            }
                        )

            if records:
                df_expanded = pd.DataFrame(records)

                session_duration = df_expanded.drop_duplicates("id").set_index("id")[
                    "duration_minutes"
                ]

                stats = []
                for fish in df_expanded["fish_name"].unique():
                    fish_data = df_expanded[df_expanded["fish_name"] == fish]
                    total_caught = fish_data["count"].sum()

                    session_ids = fish_data["id"].unique()
                    total_time = session_duration[session_ids].sum()

                    avg_time_per_fish = (
                        total_time / total_caught if total_caught > 0 else 0
                    )

                    stats.append(
                        {
                            "물고기 이름": fish,
                            "총 포획 수(마리)": total_caught,
                            "관련 세션 총 시간(분)": round(total_time, 2),
                            "마리당 평균 소요시간(분)": round(avg_time_per_fish, 2),
                        }
                    )

                df_stats = pd.DataFrame(stats).sort_values(
                    "마리당 평균 소요시간(분)", ascending=True
                )

                st.dataframe(df_stats, use_container_width=True, hide_index=True)

                fig = go.Figure(
                    data=[
                        go.Bar(
                            x=df_stats["물고기 이름"],
                            y=df_stats["마리당 평균 소요시간(분)"],
                            text=[
                                f"{v}분" for v in df_stats["마리당 평균 소요시간(분)"]
                            ],
                            textposition="auto",
                            marker_color="dodgerblue",
                        )
                    ]
                )
                fig.update_layout(
                    title="물고기 종류별 마리당 평균 소요 시간 (낮을수록 잘 잡힘)",
                    xaxis_title="물고기 이름",
                    yaxis_title="평균 소요 시간(분)",
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("기록된 물고기 포획 데이터가 없습니다.")

    with tab3:
        st.header("저장된 낚시 데이터 관리")
        if df_fish.empty:
            st.write("삭제할 데이터가 없습니다.")
        else:
            st.dataframe(
                df_fish.sort_values("id", ascending=False), use_container_width=True
            )
            del_id = st.number_input(
                "삭제할 낚시 실험의 ID를 입력하세요",
                min_value=0,
                step=1,
                key="del_fish",
            )
            if st.button("해당 ID 데이터 삭제", type="primary"):
                conn = get_connection()
                c = conn.cursor()
                c.execute("DELETE FROM fishing_experiments WHERE id = ?", (del_id,))
                conn.commit()
                conn.close()
                st.success(f"ID {del_id} 데이터가 삭제되었습니다. 새로고침을 해주세요.")
                st.rerun()

elif app_mode == "🏪 상점 할인 트래커":
    st.title("🏪 마시모 상점(Massimo Store) 할인 트래커")
    tab1, tab2, tab3 = st.tabs(
        ["오늘의 할인 입력", "상점 단가표 및 할인 확률", "데이터 관리(삭제)"]
    )

    with tab1:
        st.header("오늘 할인 중인 품목 기록하기")
        st.caption(
            "※ 날짜별로 덮어쓰기가 가능하므로 잘못 입력했다면 다시 입력하시면 됩니다. 일일 구매 한도는 품목당 50개입니다."
        )

        conn = get_connection()
        df_store_ref = pd.read_sql_query(
            "SELECT ingredient_name FROM store_reference", conn
        )
        ingredients_list = df_store_ref["ingredient_name"].tolist()
        conn.close()

        record_date = st.date_input("기록 날짜 (KST 기준)", get_kst_date())

        massimo_items = [item for item in ingredients_list if "Sugar" not in item]

        discounted_items = st.multiselect(
            "오늘 40% 할인 중인 품목을 모두 선택하세요 (마시모 상점 전용):",
            options=massimo_items,
            placeholder="선택하지 않은 품목은 '기본가'로 저장됩니다.",
        )

        if st.button("할인 정보 저장", type="primary"):
            conn = get_connection()
            c = conn.cursor()

            for ing in ingredients_list:
                is_disc = ing in discounted_items

                c.execute(
                    """
                    INSERT INTO store_discounts (record_date, ingredient_name, is_discounted, timestamp)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(record_date, ingredient_name) DO UPDATE SET
                        is_discounted = excluded.is_discounted,
                        timestamp = excluded.timestamp
                    """,
                    (str(record_date), ing, is_disc, get_kst_now()),
                )
            conn.commit()
            conn.close()
            st.success(
                f"{record_date} 날짜의 마시모 상점 데이터가 성공적으로 저장되었습니다!"
            )

    with tab2:
        st.header("식재료 할인 빈도 및 평균 단가 분석")

        conn = get_connection()
        query = """
            SELECT 
                d.ingredient_name,
                COUNT(d.id) as total_days,
                SUM(CASE WHEN d.is_discounted THEN 1 ELSE 0 END) as discount_days,
                r.discounted_price,
                r.base_price
            FROM store_discounts d
            JOIN store_reference r ON d.ingredient_name = r.ingredient_name
            GROUP BY d.ingredient_name
        """
        df_analysis = pd.read_sql_query(query, conn)
        conn.close()

        if df_analysis.empty:
            st.info("아직 입력된 상점 할인 기록이 없습니다.")
        else:
            df_analysis["할인 확률(%)"] = (
                df_analysis["discount_days"] / df_analysis["total_days"]
            ) * 100

            df_analysis["평균 구매 단가(Gold)"] = (
                df_analysis["base_price"]
                * (1 - df_analysis["discount_days"] / df_analysis["total_days"])
            ) + (
                df_analysis["discounted_price"]
                * (df_analysis["discount_days"] / df_analysis["total_days"])
            )

            display_df = df_analysis.rename(
                columns={
                    "ingredient_name": "식재료명",
                    "total_days": "기록 일수",
                    "discount_days": "할인 일수",
                    "discounted_price": "할인가",
                    "base_price": "기본가",
                }
            )

            display_df = display_df[
                [
                    "식재료명",
                    "기본가",
                    "할인가",
                    "기록 일수",
                    "할인 일수",
                    "할인 확률(%)",
                    "평균 구매 단가(Gold)",
                ]
            ]

            st.dataframe(
                display_df.style.format(
                    {"할인 확률(%)": "{:.1f}%", "평균 구매 단가(Gold)": "{:.2f}"}
                ),
                use_container_width=True,
            )
            st.caption(
                "요리 효율을 계산할 때, 이 표의 **'평균 구매 단가'**를 식재료 원가로 사용하면 정확한 기댓값을 얻을 수 있습니다."
            )

            fig = go.Figure()
            fig.add_trace(
                go.Bar(
                    x=display_df["식재료명"],
                    y=display_df["할인 확률(%)"],
                    text=[f"{v:.1f}%" for v in display_df["할인 확률(%)"]],
                    textposition="auto",
                    marker_color="indianred",
                )
            )
            fig.update_layout(
                title="품목별 할인 빈도 (Discount Probability)",
                xaxis_title="식재료명",
                yaxis_title="할인 확률 (%)",
                yaxis=dict(range=[0, 100]),
            )
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.header("저장된 할인 데이터 관리")
        conn = get_connection()
        df_store_all = pd.read_sql_query(
            "SELECT * FROM store_discounts ORDER BY record_date DESC, id DESC", conn
        )
        conn.close()

        if df_store_all.empty:
            st.write("삭제할 데이터가 없습니다.")
        else:
            st.dataframe(df_store_all, use_container_width=True)
            delete_s_id = st.number_input(
                "삭제할 상점 기록의 ID를 입력하세요",
                min_value=0,
                step=1,
                key="del_store",
            )
            if st.button("해당 ID 데이터 삭제", type="primary"):
                conn = get_connection()
                c = conn.cursor()
                c.execute("DELETE FROM store_discounts WHERE id = ?", (delete_s_id,))
                conn.commit()
                conn.close()
                st.success(
                    f"ID {delete_s_id} 데이터가 삭제되었습니다. 새로고침을 해주세요."
                )
                st.rerun()

elif app_mode == "📈 요리 효율 계산":
    st.title("📈 두두타 요리 효율 계산기")
    st.info(
        "💡 제공된 스크린샷 기반의 모든 레시피 데이터가 성공적으로 내장되었습니다. 추후 이 데이터를 활용해 효율 계산 기능이 추가될 예정입니다."
    )

    recipe_raw_data = [
        # 샐러드 & 잼 (Salad & Jams)
        {
            "name": "House Salad",
            "s1": 90,
            "s2": 135,
            "s3": 180,
            "s4": 360,
            "s5": 720,
            "recipe": "2 Tomato",
        },
        {
            "name": "Blueberry Jam",
            "s1": 170,
            "s2": 255,
            "s3": 340,
            "s4": 680,
            "s5": 1360,
            "recipe": "4 Blueberry",
        },
        {
            "name": "Tomato Sauce",
            "s1": 180,
            "s2": 270,
            "s3": 360,
            "s4": 720,
            "s5": 1440,
            "recipe": "4 Tomato",
        },
        {
            "name": "Raspberry Jam",
            "s1": 250,
            "s2": 375,
            "s3": 500,
            "s4": 1000,
            "s5": 2000,
            "recipe": "4 Raspberry",
        },
        {
            "name": "Apple Jam",
            "s1": 270,
            "s2": 405,
            "s3": 540,
            "s4": 1080,
            "s5": 2160,
            "recipe": "4 Apple",
        },
        {
            "name": "Mandarin Jam",
            "s1": 270,
            "s2": 405,
            "s3": 540,
            "s4": 1080,
            "s5": 2160,
            "recipe": "4 Mandarin",
        },
        {
            "name": "Pineapple Jam",
            "s1": 280,
            "s2": 420,
            "s3": 560,
            "s4": 1120,
            "s5": 2240,
            "recipe": "4 Pineapple",
        },
        {
            "name": "Strawberry Jam",
            "s1": 1580,
            "s2": 2370,
            "s3": 3160,
            "s4": 6320,
            "s5": 12640,
            "recipe": "4 Strawberry",
        },
        {
            "name": "Grape Jam",
            "s1": 2020,
            "s2": 3030,
            "s3": 4040,
            "s4": 8080,
            "s5": 16160,
            "recipe": "4 Grapes",
        },
        # 구운 버섯 (Grilled Mushrooms)
        {
            "name": "Grilled Button Mushroom",
            "s1": 180,
            "s2": 270,
            "s3": 360,
            "s4": 720,
            "s5": 1440,
            "recipe": "4 Button",
        },
        {
            "name": "Grilled Oyster Mushroom",
            "s1": 180,
            "s2": 270,
            "s3": 360,
            "s4": 720,
            "s5": 1440,
            "recipe": "4 Oyster",
        },
        {
            "name": "Grilled Penny Bun",
            "s1": 180,
            "s2": 270,
            "s3": 360,
            "s4": 720,
            "s5": 1440,
            "recipe": "4 PennyBun",
        },
        {
            "name": "Grilled Shiitake Mushroom",
            "s1": 180,
            "s2": 270,
            "s3": 360,
            "s4": 720,
            "s5": 1440,
            "recipe": "4 Shiitake",
        },
        # 파이류 (Pies)
        {
            "name": "Button Mushroom Pie",
            "s1": 500,
            "s2": 750,
            "s3": 1000,
            "s4": 2000,
            "s5": 4000,
            "recipe": "2 Button, 1 Wheat, 1 Egg",
        },
        {
            "name": "Oyster Mushroom Pie",
            "s1": 500,
            "s2": 750,
            "s3": 1000,
            "s4": 2000,
            "s5": 4000,
            "recipe": "2 Oyster, 1 Wheat, 1 Egg",
        },
        {
            "name": "Penny Bun Pie",
            "s1": 500,
            "s2": 750,
            "s3": 1000,
            "s4": 2000,
            "s5": 4000,
            "recipe": "2 PennyBun, 1 Wheat, 1 Egg",
        },
        {
            "name": "Shiitake Pie",
            "s1": 500,
            "s2": 750,
            "s3": 1000,
            "s4": 2000,
            "s5": 4000,
            "recipe": "2 Shiitake, 1 Wheat, 1 Egg",
        },
        {
            "name": "Apple Pie",
            "s1": 730,
            "s2": 1095,
            "s3": 1460,
            "s4": 2920,
            "s5": 5840,
            "recipe": "1 Apple, 1 Wheat, 1 Egg, 1 Butter",
        },
        {
            "name": "Black Truffle Pie",
            "s1": 830,
            "s2": 1245,
            "s3": 1660,
            "s4": 3320,
            "s5": 6640,
            "recipe": "2 BlackTruffle, 1 Wheat, 1 Egg",
        },
        # 롤케이크 (Roll Cakes)
        {
            "name": "Original Roll Cake",
            "s1": 550,
            "s2": 825,
            "s3": 1100,
            "s4": 2200,
            "s5": 4400,
            "recipe": "1 Egg, 1 Milk, 2 Sugar",
        },
        {
            "name": "Blue Roll Cake",
            "s1": 570,
            "s2": 855,
            "s3": 1140,
            "s4": 2280,
            "s5": 4560,
            "recipe": "1 Egg, 1 Milk, 2 Blue Sugar",
        },
        {
            "name": "Indigo Roll Cake",
            "s1": 570,
            "s2": 855,
            "s3": 1140,
            "s4": 2280,
            "s5": 4560,
            "recipe": "1 Egg, 1 Milk, 2 Indigo Sugar",
        },
        {
            "name": "Violet Roll Cake",
            "s1": 570,
            "s2": 855,
            "s3": 1140,
            "s4": 2280,
            "s5": 4560,
            "recipe": "1 Egg, 1 Milk, 2 Violet Sugar",
        },
        {
            "name": "Red Roll Cake",
            "s1": 670,
            "s2": 1005,
            "s3": 1340,
            "s4": 2680,
            "s5": 5360,
            "recipe": "1 Egg, 1 Milk, 2 Red Sugar",
        },
        {
            "name": "Yellow Roll Cake",
            "s1": 670,
            "s2": 1005,
            "s3": 1340,
            "s4": 2680,
            "s5": 5360,
            "recipe": "1 Egg, 1 Milk, 2 Yellow Sugar",
        },
        {
            "name": "Orange Roll Cake",
            "s1": 670,
            "s2": 1005,
            "s3": 1340,
            "s4": 2680,
            "s5": 5360,
            "recipe": "1 Egg, 1 Milk, 2 Orange Sugar",
        },
        {
            "name": "Green Roll Cake",
            "s1": 670,
            "s2": 1005,
            "s3": 1340,
            "s4": 2680,
            "s5": 5360,
            "recipe": "1 Egg, 1 Milk, 2 Green Sugar",
        },
        # 커피류 (Coffee)
        {
            "name": "Coffee",
            "s1": 290,
            "s2": 435,
            "s3": 580,
            "s4": 1160,
            "s5": 2320,
            "recipe": "4 Coffee",
        },
        {
            "name": "Coffee Latte",
            "s1": 300,
            "s2": 450,
            "s3": 600,
            "s4": 1200,
            "s5": 2400,
            "recipe": "2 Coffee, 2 Milk",
        },
        # 요리류 (Main Dishes & Desserts)
        {
            "name": "Onsen Egg",
            "s1": 130,
            "s2": 195,
            "s3": 260,
            "s4": 520,
            "s5": 1040,
            "recipe": "1 Pasturized Egg",
        },
        {
            "name": "Cheese Cake",
            "s1": 480,
            "s2": 720,
            "s3": 960,
            "s4": 1920,
            "s5": 3840,
            "recipe": "1 Cheese, 1 Milk, 1 Wheat",
        },
        {
            "name": "Tiramisu",
            "s1": 530,
            "s2": 795,
            "s3": 1060,
            "s4": 2120,
            "s5": 4240,
            "recipe": "1 Coffee, 1 Egg, 1 Milk, 1 Butter",
        },
        {
            "name": "Rustic Ratatouille",
            "s1": 640,
            "s2": 960,
            "s3": 1280,
            "s4": 2560,
            "s5": 5120,
            "recipe": "1 Tomato, 1 Potato, 1 Lettuce",
        },
        {
            "name": "Meat Sauce Pasta",
            "s1": 670,
            "s2": 1005,
            "s3": 1340,
            "s4": 2680,
            "s5": 5360,
            "recipe": "1 Meat, 1 Tomato, 1 Wheat, 1 Cheese",
        },
        {
            "name": "Carrot Cake",
            "s1": 840,
            "s2": 1260,
            "s3": 1680,
            "s4": 3360,
            "s5": 6720,
            "recipe": "1 Egg, 1 Wheat, 2 Carrot",
        },
        {
            "name": "Black Truffle Cream Pasta",
            "s1": 900,
            "s2": 1350,
            "s3": 1980,
            "s4": 3600,
            "s5": 7200,
            "recipe": "1 BlackTruffle, 1 Milk, 2 Wheat",
        },
        {
            "name": "Corn Soup",
            "s1": 1340,
            "s2": 2010,
            "s3": 2680,
            "s4": 5360,
            "s5": 10720,
            "recipe": "1 Milk, 1 Butter, 2 Corn",
        },
        {
            "name": "Meat Burger",
            "s1": 1350,
            "s2": 2025,
            "s3": 2700,
            "s4": 5400,
            "s5": 10800,
            "recipe": "1 Wheat, 1 Lettuce, 1 Meat, 1 TomatoSauce",
        },
        {
            "name": "Baked Eggplant With Meat",
            "s1": 1230,
            "s2": 1845,
            "s3": 2460,
            "s4": 4920,
            "s5": 9840,
            "recipe": "1 Eggplant, 1 Meat, 1 CookingOil, 1 Jam",
        },
        # 해산물 요리 (Seafood)
        {
            "name": "Fish N Chips",
            "s1": 310,
            "s2": 465,
            "s3": 620,
            "s4": 1240,
            "s5": 2480,
            "recipe": "2 Fish, 2 Potato",
        },
        {
            "name": "Deluxe Seafood Platter",
            "s1": 410,
            "s2": 615,
            "s3": 820,
            "s4": 1640,
            "s5": 3280,
            "recipe": "2 Shellfish, 2 Fish",
        },
        {
            "name": "Seafood Risotto",
            "s1": 490,
            "s2": 735,
            "s3": 980,
            "s4": 1960,
            "s5": 3920,
            "recipe": "2 Fish, 1 Wheat, 1 Tomato",
        },
        {
            "name": "Smoked Fish Bagel",
            "s1": 520,
            "s2": 780,
            "s3": 1040,
            "s4": 2080,
            "s5": 4160,
            "recipe": "1 Fish, 1 Cheese, 1 Wheat, 1 Tomato",
        },
        {
            "name": "Seafood Pizza",
            "s1": 780,
            "s2": 1170,
            "s3": 1560,
            "s4": 3120,
            "s5": 6240,
            "recipe": "1 Cheese, 1 TomatoSauce, 1 Wheat, 1 Fish",
        },
        {
            "name": "Steamed King Crab",
            "s1": 1990,
            "s2": 2985,
            "s3": 3980,
            "s4": 7960,
            "s5": 15920,
            "recipe": "3 KingCrab, 1 Butter",
        },
        {
            "name": "Steamed Golden King Crab",
            "s1": 2980,
            "s2": None,
            "s3": None,
            "s4": None,
            "s5": None,
            "recipe": "3 GoldenKingCrab, 1 Butter",
        },
        # 세트 및 사시미 (Sets & Sashimi)
        {
            "name": "Afternoon Tea",
            "s1": 710,
            "s2": 1065,
            "s3": 1420,
            "s4": 2840,
            "s5": 5680,
            "recipe": "1 Tiramisu, 1 Blueberry",
        },
        {
            "name": "Picnic Set",
            "s1": 2260,
            "s2": 3390,
            "s3": 4520,
            "s4": 9040,
            "s5": 18080,
            "recipe": "1 Seafood Pizza, 1 Apple Pie, 1 Fish & Chips, 1 Any Beverage",
        },
        {
            "name": "Candlelight Dinner",
            "s1": 1760,
            "s2": 2640,
            "s3": 3520,
            "s4": 7040,
            "s5": 14080,
            "recipe": "1 House Salad, 1 Smoked Fish Bagel, 1 Seafood Risotto, 1 Tiramisu",
        },
        {
            "name": "Crayfish Sashimi",
            "s1": 850,
            "s2": 1275,
            "s3": 1700,
            "s4": 3400,
            "s5": 6800,
            "recipe": "3 Shellfish, 1 Lettuce",
        },
        {
            "name": "Blue European Crayfish Sashimi",
            "s1": None,
            "s2": 1965,
            "s3": None,
            "s4": None,
            "s5": None,
            "recipe": "3 Blue European Crayfish, 1 Lettuce",
        },
    ]

    df_recipes = pd.DataFrame(recipe_raw_data)

    st.subheader("📚 현재 등록된 요리 레시피 목록")

    display_df = df_recipes[["name", "recipe"]].copy()
    display_df.rename(
        columns={"name": "요리 이름", "recipe": "필요 식재료 (레시피)"}, inplace=True
    )

    st.dataframe(display_df, use_container_width=True, hide_index=True)
    st.divider()
    st.subheader("🌱 레시피별 필요 농작물 밭 점유 시간 (기댓값)")
    st.caption(
        "요리에 사용된 가장 낮은 성급의 재료(n)에 따라 요리 결과는 (n-1)성이 보장됩니다. 따라서 1성과 2성 재료는 요리 시 동일한 1성 결과를 내므로 묶어서 계산합니다."
    )

    # 1. 작물 목록 및 성장 시간(분 단위) 매핑
    crop_growth_mins = {
        "Tomato": 15,
        "Potato": 60,
        "Wheat": 240,
        "Lettuce": 480,
        "Pineapple": 30,
        "Carrot": 120,
        "Strawberry": 360,
        "Corn": 720,
        "Grapes": 600,
        "Eggplant": 420,
    }

    # 2. 원예 실험 데이터(experiments)에서 작물별/성급별 평균 수확량(드랍률) 계산
    conn = get_connection()
    df_exp = pd.read_sql_query(
        "SELECT crop_type, planted_count, star_1, star_2, star_3, star_4, star_5 FROM experiments",
        conn,
    )
    conn.close()

    yield_rates = {}
    if not df_exp.empty:
        grouped_exp = df_exp.groupby("crop_type").sum()
        for crop, row in grouped_exp.iterrows():
            if row["planted_count"] > 0:
                yield_rates[crop] = {
                    "1성": row["star_1"] / row["planted_count"],
                    "2성": row["star_2"] / row["planted_count"],
                    "3성": row["star_3"] / row["planted_count"],
                    "4성": row["star_4"] / row["planted_count"],
                    "5성": row["star_5"] / row["planted_count"],
                }

    # (수정) 분(Minute)을 "X분 Y초" 형태로 포맷팅하는 헬퍼 함수
    def format_real_time(mins):
        if pd.isna(mins) or mins == float("inf"):
            return "데이터 부족"

        # 전체 소요 시간을 초(Seconds)로 변환
        total_seconds = int(mins * 60)
        m = total_seconds // 60
        s = total_seconds % 60

        if m > 0:
            return f"{m}분 {s}초"
        return f"{s}초"

    # 3. 각 레시피별 필요 시간 계산 (40칸 일괄 재배 기준)
    field_time_data = []

    for _, row in df_recipes.iterrows():
        recipe_name = row["name"]
        recipe_str = row["recipe"]

        # 레시피 문자열 파싱 (예: "2 Tomato, 1 Wheat, 1 Egg")
        req_crops = {}
        for item_str in recipe_str.split(","):
            item_str = item_str.strip()
            if not item_str:
                continue

            parts = item_str.split(" ", 1)
            if len(parts) == 2 and parts[0].isdigit():
                qty = int(parts[0])
                item_name = parts[1]
                if item_name in crop_growth_mins:
                    req_crops[item_name] = qty

        if not req_crops:
            continue

        recipe_times = {"요리 이름": recipe_name}

        # 1성부터 5성까지 개별 타겟팅하여 실제 대기 시간(40칸 기준) 계산
        for tier in ["1성", "2성", "3성", "4성", "5성"]:
            total_real_mins_for_tier = 0
            is_calculable = True

            for crop_name, qty in req_crops.items():
                if crop_name not in yield_rates:
                    is_calculable = False
                    break

                # rate는 작물 1개 심었을 때 해당 성급이 나올 확률(드랍률)
                rate = yield_rates[crop_name][tier]
                if rate == 0:
                    is_calculable = False
                    break

                # 핵심: 40칸을 모두 해당 작물로 채웠을 때 1회 수확당 해당 성급의 기대량
                expected_per_40_fields = rate * 40

                # 필요 수량을 채우기 위해 40칸짜리 밭을 몇 번 수확해야 하는지(소수점 포함)
                harvests_needed = qty / expected_per_40_fields

                # 최종 실제 소요 시간 = 수확 필요 횟수 * 작물 1번 성장 시간
                total_real_mins_for_tier += (
                    harvests_needed * crop_growth_mins[crop_name]
                )

            recipe_times[f"{tier} 타겟 소요시간"] = (
                format_real_time(total_real_mins_for_tier)
                if is_calculable
                else "데이터 부족"
            )

        field_time_data.append(recipe_times)

    # 4. 결과 출력
    if field_time_data:
        df_field_time = pd.DataFrame(field_time_data)
        st.dataframe(df_field_time, use_container_width=True, hide_index=True)
    else:
        st.info("현재 농작물이 포함된 레시피 데이터나 작물 실험 데이터가 부족합니다.")
