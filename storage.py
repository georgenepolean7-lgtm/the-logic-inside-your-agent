"""
storage.py - SQLite Historical Tracker for Indian E-commerce Market Trends
Manages product information, daily snapshots, AI trend evaluations, and storefront export shortlists.
"""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "products_history.db")

__all__ = [
    "DB_FILE",
    "get_connection",
    "init_db",
    "upsert_product",
    "insert_daily_metric",
    "upsert_ai_analysis",
    "get_product_metrics_history",
    "calculate_7day_price_change",
    "calculate_review_velocity",
    "calculate_bsr_improvement",
    "get_all_products_with_latest_data",
    "add_to_shortlist",
    "remove_from_shortlist",
    "get_shortlist",
    "seed_demo_data",
    "log_agent_run",
    "get_agent_logs",
    "get_last_agent_run",
    "insert_social_metric",
    "get_social_metrics_history",
    "upsert_weekly_launch_verdict",
    "get_latest_weekly_verdicts",
    "get_product_weekly_verdict",
    "get_combined_7day_product_signals",
]


def get_connection(db_path: str = DB_FILE) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=60.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
    except Exception:
        pass
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_FILE) -> None:
    """Initialize database tables with complete schema."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        product_id TEXT PRIMARY KEY,
        platform TEXT NOT NULL,
        title TEXT NOT NULL,
        category TEXT,
        url TEXT,
        image_url TEXT,
        first_seen_date TEXT NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS daily_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id TEXT NOT NULL,
        date TEXT NOT NULL,
        price REAL NOT NULL,
        rating REAL,
        review_count INTEGER,
        bsr_rank INTEGER,
        recent_reviews_text TEXT,
        FOREIGN KEY (product_id) REFERENCES products(product_id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ai_analysis (
        product_id TEXT PRIMARY KEY,
        date TEXT NOT NULL,
        trend_status TEXT NOT NULL,
        sellability_score INTEGER NOT NULL,
        website_ready INTEGER NOT NULL,
        estimated_margin_pct REAL,
        recommended_selling_price REAL,
        estimated_sourcing_cost REAL,
        ai_reasoning TEXT,
        red_flags TEXT,
        customer_pain_points TEXT,
        marketing_angle_for_website TEXT,
        ai_summary_tamil_english TEXT,
        FOREIGN KEY (product_id) REFERENCES products(product_id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS storefront_shortlist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id TEXT UNIQUE NOT NULL,
        added_at TEXT NOT NULL,
        custom_selling_price REAL,
        notes TEXT,
        status TEXT DEFAULT 'Approved',
        FOREIGN KEY (product_id) REFERENCES products(product_id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agent_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        status TEXT NOT NULL,
        scraped_count INTEGER DEFAULT 0,
        analyzed_count INTEGER DEFAULT 0,
        auto_shortlisted_count INTEGER DEFAULT 0,
        summary TEXT,
        details TEXT
    );
    """)

    # Social Media & Google Trends History
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS social_metrics_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id TEXT NOT NULL,
        date TEXT NOT NULL,
        social_views_score INTEGER,
        buyer_intent_comments_score INTEGER,
        google_trend_score INTEGER,
        viral_velocity_7d REAL,
        trending_platform TEXT,
        FOREIGN KEY (product_id) REFERENCES products(product_id),
        UNIQUE(product_id, date) ON CONFLICT REPLACE
    );
    """)

    # 7-Day Master Verdict (99% Confidence Launch List)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS weekly_launch_verdict (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        week_start_date TEXT NOT NULL,
        week_end_date TEXT NOT NULL,
        product_id TEXT NOT NULL,
        confidence_score REAL,
        ecom_consistency_7d REAL,
        social_viral_score REAL,
        sourcing_cost_est REAL,
        target_selling_price REAL,
        net_profit_per_unit REAL,
        launch_blueprint_json TEXT,
        verdict_summary_tanglish TEXT,
        FOREIGN KEY (product_id) REFERENCES products(product_id),
        UNIQUE(week_start_date, product_id) ON CONFLICT REPLACE
    );
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_pid_date ON daily_metrics(product_id, date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_social_pid_date ON social_metrics_history(product_id, date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_verdict_week ON weekly_launch_verdict(week_start_date, confidence_score);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_logs_ts ON agent_logs(timestamp);")
    conn.commit()
    conn.close()


def upsert_product(
    product_id: str,
    platform: str,
    title: str,
    category: str = "General",
    url: str = "",
    image_url: str = "",
    first_seen_date: Optional[str] = None,
    db_path: str = DB_FILE
) -> None:
    if not first_seen_date:
        first_seen_date = datetime.now().strftime("%Y-%m-%d")
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO products (product_id, platform, title, category, url, image_url, first_seen_date)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(product_id) DO UPDATE SET
        platform=excluded.platform,
        title=excluded.title,
        category=excluded.category,
        url=excluded.url,
        image_url=excluded.image_url;
    """, (product_id, platform, title, category, url, image_url, first_seen_date))
    conn.commit()
    conn.close()


def insert_daily_metric(
    product_id: str,
    date_str: str,
    price: float,
    rating: float,
    review_count: int,
    bsr_rank: int,
    recent_reviews_text: str = "",
    db_path: str = DB_FILE
) -> None:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    # Replace existing metric for same day if exists
    cursor.execute("""
    DELETE FROM daily_metrics WHERE product_id = ? AND date = ?;
    """, (product_id, date_str))
    cursor.execute("""
    INSERT INTO daily_metrics (product_id, date, price, rating, review_count, bsr_rank, recent_reviews_text)
    VALUES (?, ?, ?, ?, ?, ?, ?);
    """, (product_id, date_str, price, rating, review_count, bsr_rank, recent_reviews_text))
    conn.commit()
    conn.close()


def upsert_ai_analysis(
    product_id: str,
    trend_status: str,
    sellability_score: int,
    website_ready: bool,
    estimated_margin_pct: float,
    recommended_selling_price: float,
    estimated_sourcing_cost: float,
    ai_reasoning: str,
    red_flags: str = "",
    customer_pain_points: str = "",
    marketing_angle_for_website: str = "",
    ai_summary_tamil_english: str = "",
    date_str: Optional[str] = None,
    db_path: str = DB_FILE
) -> None:
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO ai_analysis (
        product_id, date, trend_status, sellability_score, website_ready,
        estimated_margin_pct, recommended_selling_price, estimated_sourcing_cost,
        ai_reasoning, red_flags, customer_pain_points, marketing_angle_for_website,
        ai_summary_tamil_english
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(product_id) DO UPDATE SET
        date=excluded.date,
        trend_status=excluded.trend_status,
        sellability_score=excluded.sellability_score,
        website_ready=excluded.website_ready,
        estimated_margin_pct=excluded.estimated_margin_pct,
        recommended_selling_price=excluded.recommended_selling_price,
        estimated_sourcing_cost=excluded.estimated_sourcing_cost,
        ai_reasoning=excluded.ai_reasoning,
        red_flags=excluded.red_flags,
        customer_pain_points=excluded.customer_pain_points,
        marketing_angle_for_website=excluded.marketing_angle_for_website,
        ai_summary_tamil_english=excluded.ai_summary_tamil_english;
    """, (
        product_id, date_str, trend_status, sellability_score, int(website_ready),
        estimated_margin_pct, recommended_selling_price, estimated_sourcing_cost,
        ai_reasoning, red_flags, customer_pain_points, marketing_angle_for_website,
        ai_summary_tamil_english
    ))
    conn.commit()
    conn.close()


def get_product_metrics_history(product_id: str, days: int = 7, db_path: str = DB_FILE) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT date, price, rating, review_count, bsr_rank, recent_reviews_text
    FROM daily_metrics
    WHERE product_id = ?
    ORDER BY date ASC;
    """, (product_id,))
    rows = cursor.fetchall()
    conn.close()
    results = [dict(r) for r in rows]
    if len(results) > days:
        return results[-days:]
    return results


def calculate_7day_price_change(product_id: str, db_path: str = DB_FILE) -> float:
    """Calculate 7-day price change %. Negative means price is dropping."""
    history = get_product_metrics_history(product_id, days=7, db_path=db_path)
    if len(history) < 2:
        return 0.0
    first_price = history[0]["price"]
    latest_price = history[-1]["price"]
    if first_price == 0:
        return 0.0
    return round(((latest_price - first_price) / first_price) * 100, 2)


def calculate_review_velocity(product_id: str, days: int = 7, db_path: str = DB_FILE) -> int:
    """Calculate new reviews added over the last N days."""
    history = get_product_metrics_history(product_id, days=days, db_path=db_path)
    if len(history) < 2:
        return 0
    return max(0, history[-1]["review_count"] - history[0]["review_count"])


def calculate_bsr_improvement(product_id: str, days: int = 7, db_path: str = DB_FILE) -> float:
    """
    Calculate BSR rank improvement % over the last N days.
    In BSR, a lower number is better rank (e.g. from 500 to 100 is +80% improvement).
    Positive value indicates improvement in sales velocity rank.
    """
    history = get_product_metrics_history(product_id, days=days, db_path=db_path)
    if len(history) < 2:
        return 0.0
    first_bsr = history[0]["bsr_rank"]
    latest_bsr = history[-1]["bsr_rank"]
    if first_bsr <= 0 or latest_bsr <= 0:
        return 0.0
    # Formula: ((old_bsr - new_bsr) / old_bsr) * 100
    improvement = ((first_bsr - latest_bsr) / first_bsr) * 100.0
    return round(improvement, 2)


def get_all_products_with_latest_data(db_path: str = DB_FILE) -> List[Dict[str, Any]]:
    """Retrieve all products joined with their latest daily metric, AI evaluation, and shortlist status."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT 
        p.product_id,
        p.platform,
        p.title,
        p.category,
        p.url,
        p.image_url,
        p.first_seen_date,
        m.price,
        m.rating,
        m.review_count,
        m.bsr_rank,
        m.recent_reviews_text,
        m.date as last_metric_date,
        ai.trend_status,
        ai.sellability_score,
        ai.website_ready,
        ai.estimated_margin_pct,
        ai.recommended_selling_price,
        ai.estimated_sourcing_cost,
        ai.ai_reasoning,
        ai.red_flags,
        ai.customer_pain_points,
        ai.marketing_angle_for_website,
        ai.ai_summary_tamil_english,
        CASE WHEN sl.product_id IS NOT NULL THEN 1 ELSE 0 END as is_shortlisted,
        sl.custom_selling_price as shortlisted_price,
        sl.notes as shortlist_notes
    FROM products p
    LEFT JOIN (
        SELECT dm.*
        FROM daily_metrics dm
        INNER JOIN (
            SELECT product_id, MAX(date) as max_date
            FROM daily_metrics
            GROUP BY product_id
        ) latest ON dm.product_id = latest.product_id AND dm.date = latest.max_date
    ) m ON p.product_id = m.product_id
    LEFT JOIN ai_analysis ai ON p.product_id = ai.product_id
    LEFT JOIN storefront_shortlist sl ON p.product_id = sl.product_id
    ORDER BY p.product_id ASC;
    """)
    rows = cursor.fetchall()
    conn.close()

    enriched_products = []
    for r in rows:
        item = dict(r)
        pid = item["product_id"]
        item["price_change_7d"] = calculate_7day_price_change(pid, db_path)
        item["review_velocity_7d"] = calculate_review_velocity(pid, 7, db_path)
        item["bsr_improvement_7d"] = calculate_bsr_improvement(pid, 7, db_path)
        enriched_products.append(item)
    return enriched_products


def add_to_shortlist(product_id: str, custom_selling_price: Optional[float] = None, notes: str = "", db_path: str = DB_FILE) -> bool:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
    INSERT INTO storefront_shortlist (product_id, added_at, custom_selling_price, notes, status)
    VALUES (?, ?, ?, ?, 'Approved')
    ON CONFLICT(product_id) DO UPDATE SET
        added_at=excluded.added_at,
        custom_selling_price=COALESCE(excluded.custom_selling_price, storefront_shortlist.custom_selling_price),
        notes=excluded.notes;
    """, (product_id, now_str, custom_selling_price, notes))
    conn.commit()
    conn.close()
    return True


def remove_from_shortlist(product_id: str, db_path: str = DB_FILE) -> bool:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM storefront_shortlist WHERE product_id = ?;", (product_id,))
    conn.commit()
    conn.close()
    return True


def get_shortlist(db_path: str = DB_FILE) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT 
        sl.id,
        sl.product_id,
        sl.added_at,
        sl.custom_selling_price,
        sl.notes,
        sl.status,
        p.platform,
        p.title,
        p.category,
        p.url,
        p.image_url,
        m.price as current_market_price,
        m.rating,
        m.review_count,
        ai.sellability_score,
        ai.estimated_sourcing_cost,
        ai.recommended_selling_price,
        ai.estimated_margin_pct,
        ai.marketing_angle_for_website
    FROM storefront_shortlist sl
    JOIN products p ON sl.product_id = p.product_id
    LEFT JOIN (
        SELECT dm.*
        FROM daily_metrics dm
        INNER JOIN (
            SELECT product_id, MAX(date) as max_date
            FROM daily_metrics
            GROUP BY product_id
        ) latest ON dm.product_id = latest.product_id AND dm.date = latest.max_date
    ) m ON p.product_id = m.product_id
    LEFT JOIN ai_analysis ai ON p.product_id = ai.product_id
    ORDER BY sl.added_at DESC;
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def seed_demo_data(db_path: str = DB_FILE) -> None:
    """Populates 10 realistic Indian e-commerce products (between ₹100 and ₹1,000) with 7 days of historical metrics."""
    init_db(db_path)
    base_date = datetime.now()

    demo_products = [
        {
            "product_id": "AMZ_B09XYZLIGHT",
            "platform": "Amazon India",
            "title": "Magnetic LED Motion Sensor Night Light (USB Rechargeable, Warm White)",
            "category": "Home & Kitchen",
            "url": "https://www.amazon.in/dp/B09XYZLIGHT",
            "image_url": "https://images.unsplash.com/photo-1540932239986-30128078f3c5?w=500&q=80",
            # Rising product: price steady ₹289, rating 4.4, reviews 65 -> 145, BSR 480 -> 92
            "metrics_trend": [
                {"day_offset": -6, "price": 299, "rating": 4.3, "reviews": 65, "bsr": 480},
                {"day_offset": -5, "price": 299, "rating": 4.3, "reviews": 75, "bsr": 390},
                {"day_offset": -4, "price": 289, "rating": 4.4, "reviews": 92, "bsr": 280},
                {"day_offset": -3, "price": 289, "rating": 4.4, "reviews": 105, "bsr": 195},
                {"day_offset": -2, "price": 289, "rating": 4.4, "reviews": 118, "bsr": 135},
                {"day_offset": -1, "price": 289, "rating": 4.4, "reviews": 132, "bsr": 110},
                {"day_offset": 0, "price": 289, "rating": 4.4, "reviews": 148, "bsr": 88},
            ],
            "reviews_sample": "Super sensor response, battery lasts 2 weeks on single charge. Stick on wall easily without screws. Very neat gadget for dark cupboards and stairs.",
            "initial_ai": {
                "trend_status": "High Sale Rising",
                "sellability_score": 92,
                "website_ready": True,
                "estimated_margin_pct": 52.0,
                "recommended_selling_price": 549.0,
                "estimated_sourcing_cost": 140.0,
                "ai_reasoning": "High organic search momentum in India for energy-saving aesthetic lighting. Review count is 148 (low saturation), BSR improved by 81.6% in 7 days, and ₹289 market price leaves a 50%+ margin when white-labeled at ₹549.",
                "red_flags": "Check USB charging port build quality before bulk ordering from Surat/Delhi manufacturers.",
                "customer_pain_points": "Sensor sensitivity in broad daylight; some users expect type-C instead of micro-USB.",
                "marketing_angle_for_website": "Transform your dark wardrobe, stairs & kitchen cabinets into a luxury hotel look in 2 seconds — Zero drilling needed!",
                "ai_summary_tamil_english": "Indha product semma trending! 7 days-la BSR 480-la irundhu 88-ku jump aagi irukku. Website-la ₹549-ku sell pannina direct 50%+ profit kedaikkum."
            }
        },
        {
            "product_id": "MSH_FROTHER_88",
            "platform": "Meesho",
            "title": "Electric Handheld Milk Frother & Coffee Whisk (Stainless Steel Head)",
            "category": "Kitchen & Dining",
            "url": "https://www.meesho.com/p/milk-frother-whisker/189",
            "image_url": "https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?w=500&q=80",
            # Rising product: price ₹179, reviews 42 -> 118, BSR 310 -> 72
            "metrics_trend": [
                {"day_offset": -6, "price": 189, "rating": 4.2, "reviews": 42, "bsr": 310},
                {"day_offset": -5, "price": 185, "rating": 4.2, "reviews": 55, "bsr": 260},
                {"day_offset": -4, "price": 179, "rating": 4.2, "reviews": 70, "bsr": 195},
                {"day_offset": -3, "price": 179, "rating": 4.3, "reviews": 84, "bsr": 140},
                {"day_offset": -2, "price": 179, "rating": 4.3, "reviews": 98, "bsr": 105},
                {"day_offset": -1, "price": 179, "rating": 4.3, "reviews": 109, "bsr": 85},
                {"day_offset": 0, "price": 179, "rating": 4.3, "reviews": 122, "bsr": 68},
            ],
            "reviews_sample": "Cafe style thick cold coffee at home in 30 seconds! Works smoothly with 2 AA batteries. Compact and handy.",
            "initial_ai": {
                "trend_status": "High Sale Rising",
                "sellability_score": 88,
                "website_ready": True,
                "estimated_margin_pct": 58.0,
                "recommended_selling_price": 429.0,
                "estimated_sourcing_cost": 75.0,
                "ai_reasoning": "Classic viral reel item. Low wholesale procurement cost (under ₹80 in bulk), high review velocity (+80 in 7 days), excellent conversion potential under ₹499.",
                "red_flags": "Requires 2 AA batteries (not included); clearly mention this on product page to avoid 1-star reviews.",
                "customer_pain_points": "Battery cap can feel loose if dropped; motor slows down when batteries drain.",
                "marketing_angle_for_website": "Why pay ₹250 for Starbucks cold coffee? Whip thick creamy foam at home in 20 seconds!",
                "ai_summary_tamil_english": "Instagram reel viral item. Bulk sourcing ₹75 dhan, website-la bundle combo-la ₹449-ku easy-ah move aagum. Safe & high margin product."
            }
        },
        {
            "product_id": "AMZ_B0B_AIRFRYPOT",
            "platform": "Amazon India",
            "title": "Silicone Reusable Air Fryer Pot Liners (Pack of 2, Food Grade, Non-Stick)",
            "category": "Home & Kitchen",
            "url": "https://www.amazon.in/dp/B0BAIRFRYPOT",
            "image_url": "https://images.unsplash.com/photo-1584269600464-37b1b58a9fe7?w=500&q=80",
            # Rising product: price ₹349, reviews 95 -> 215, BSR 240 -> 45
            "metrics_trend": [
                {"day_offset": -6, "price": 369, "rating": 4.5, "reviews": 95, "bsr": 240},
                {"day_offset": -5, "price": 369, "rating": 4.5, "reviews": 112, "bsr": 180},
                {"day_offset": -4, "price": 349, "rating": 4.5, "reviews": 138, "bsr": 125},
                {"day_offset": -3, "price": 349, "rating": 4.5, "reviews": 162, "bsr": 85},
                {"day_offset": -2, "price": 349, "rating": 4.5, "reviews": 182, "bsr": 62},
                {"day_offset": -1, "price": 349, "rating": 4.5, "reviews": 199, "bsr": 50},
                {"day_offset": 0, "price": 349, "rating": 4.5, "reviews": 218, "bsr": 42},
            ],
            "reviews_sample": "Cleaning air fryer basket was a nightmare until I bought this. Dishwasher safe, fits 4L air fryer perfectly, no oil dripping.",
            "initial_ai": {
                "trend_status": "High Sale Rising",
                "sellability_score": 95,
                "website_ready": True,
                "estimated_margin_pct": 49.0,
                "recommended_selling_price": 599.0,
                "estimated_sourcing_cost": 160.0,
                "ai_reasoning": "Air fryer penetration in urban Indian households is surging. Solves a real daily pain point (tedious scrubbing). Low shipping weight (<200g) and unbreakable silicone.",
                "red_flags": "Offer multiple sizes (large 20cm vs medium 16cm) to prevent return rate.",
                "customer_pain_points": "Need heat-resistant gloves or tongs to pull out hot silicone pot after cooking.",
                "marketing_angle_for_website": "Hate scrubbing your greasy air fryer basket? Pop in this non-stick silicone pot & wipe clean in seconds!",
                "ai_summary_tamil_english": "Top winner product! Daily air fryer use pandravangalukku idhu periya relief. Sourcing ₹160-kku kedaikkum, pack of 2-ah ₹599-ku set panni sell pannalam."
            }
        },
        {
            "product_id": "AMZ_TECH_CLEAN_PEN",
            "platform": "Amazon India",
            "title": "Multifunction 5-in-1 Earphone & Keyboard Cleaning Pen Tool",
            "category": "Electronics Accessories",
            "url": "https://www.amazon.in/dp/B0CLEANPEN",
            "image_url": "https://images.unsplash.com/photo-1546868871-7041f2a55e12?w=500&q=80",
            # Rising product: price ₹199, reviews 110 -> 280, BSR 175 -> 38
            "metrics_trend": [
                {"day_offset": -6, "price": 229, "rating": 4.3, "reviews": 110, "bsr": 175},
                {"day_offset": -5, "price": 219, "rating": 4.3, "reviews": 135, "bsr": 140},
                {"day_offset": -4, "price": 199, "rating": 4.3, "reviews": 165, "bsr": 98},
                {"day_offset": -3, "price": 199, "rating": 4.4, "reviews": 195, "bsr": 72},
                {"day_offset": -2, "price": 199, "rating": 4.4, "reviews": 225, "bsr": 54},
                {"day_offset": -1, "price": 199, "rating": 4.4, "reviews": 252, "bsr": 42},
                {"day_offset": 0, "price": 199, "rating": 4.4, "reviews": 284, "bsr": 36},
            ],
            "reviews_sample": "Cleaned 2 years worth of earwax and dust from my AirPods case in 1 minute. Metal nib reaches tight speaker mesh safely.",
            "initial_ai": {
                "trend_status": "High Sale Rising",
                "sellability_score": 90,
                "website_ready": True,
                "estimated_margin_pct": 62.0,
                "recommended_selling_price": 399.0,
                "estimated_sourcing_cost": 48.0,
                "ai_reasoning": "Extremely lightweight impulse buy (<60 grams). Shipping is cheap throughout India. Review velocity is +174 in 7 days with massive organic demand.",
                "red_flags": "Metal tip should have safety cap so it doesn't pierce through packaging.",
                "customer_pain_points": "Flocking sponge needs occasional mild rinsing.",
                "marketing_angle_for_website": "Disgusted by dirty earwax on your earbuds? Restore crystal clear audio volume with this 5-in-1 tech pen.",
                "ai_summary_tamil_english": "Super impulse buy product! BSR 175-la irundhu 36-ku vandhuruchu. Sourcing just ₹48, ₹399-ku Free Delivery offer potu sell panna quick orders varum."
            }
        },
        {
            "product_id": "MSH_ACU_SLIPPERS",
            "platform": "Meesho",
            "title": "Acupressure Reflexology Foot Massage Slippers (Pain Relief Nodes)",
            "category": "Health & Personal Care",
            "url": "https://www.meesho.com/p/acupressure-foot-slippers/269",
            "image_url": "https://images.unsplash.com/photo-1560343090-f0409e92791a?w=500&q=80",
            # Rising/Stable sweet spot: price ₹269, reviews 78 -> 172, BSR 290 -> 95
            "metrics_trend": [
                {"day_offset": -6, "price": 279, "rating": 4.1, "reviews": 78, "bsr": 290},
                {"day_offset": -5, "price": 279, "rating": 4.1, "reviews": 92, "bsr": 240},
                {"day_offset": -4, "price": 269, "rating": 4.2, "reviews": 108, "bsr": 185},
                {"day_offset": -3, "price": 269, "rating": 4.2, "reviews": 126, "bsr": 150},
                {"day_offset": -2, "price": 269, "rating": 4.2, "reviews": 142, "bsr": 125},
                {"day_offset": -1, "price": 269, "rating": 4.2, "reviews": 159, "bsr": 105},
                {"day_offset": 0, "price": 269, "rating": 4.2, "reviews": 174, "bsr": 92},
            ],
            "reviews_sample": "Hurts slightly for first 3 days but heel pain and plantar fasciitis disappeared after 15 mins daily morning walk.",
            "initial_ai": {
                "trend_status": "High Sale Rising",
                "sellability_score": 84,
                "website_ready": True,
                "estimated_margin_pct": 46.0,
                "recommended_selling_price": 599.0,
                "estimated_sourcing_cost": 135.0,
                "ai_reasoning": "High demand among 35+ demographic in Tier 2/3 Indian cities for joint and heel pain. Health gadgets have high perceived value.",
                "red_flags": "Foot sizing charts must be very explicit (UK/India sizes 6-10) to prevent exchange requests.",
                "customer_pain_points": "Pressure nodes feel sharp for first-time users; advise wearing socks initially.",
                "marketing_angle_for_website": "Walk away tired heel and leg pain in just 15 minutes a day while drinking your morning chai.",
                "ai_summary_tamil_english": "Heel pain and blood circulation-ku nalla demand irukku. Meesho-la ₹135 bulk. Website-la 'Doctor Recommended' style angle-la ₹599-ku nalla sell aagum."
            }
        },
        {
            "product_id": "AMZ_B0_EARBUDS_FAKE",
            "platform": "Amazon India",
            "title": "Ultra-Cheap TWS Wireless Earbuds Pro (Generic Clone)",
            "category": "Electronics Accessories",
            "url": "https://www.amazon.in/dp/B0EARBUDSFAKE",
            "image_url": "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=500&q=80",
            # Dropping product: price war ₹599 -> ₹249, rating dropping to 3.2, bad reviews, BSR 45 -> 480
            "metrics_trend": [
                {"day_offset": -6, "price": 599, "rating": 3.7, "reviews": 840, "bsr": 45},
                {"day_offset": -5, "price": 499, "rating": 3.6, "reviews": 860, "bsr": 90},
                {"day_offset": -4, "price": 420, "rating": 3.5, "reviews": 890, "bsr": 160},
                {"day_offset": -3, "price": 349, "rating": 3.4, "reviews": 920, "bsr": 250},
                {"day_offset": -2, "price": 299, "rating": 3.3, "reviews": 950, "bsr": 340},
                {"day_offset": -1, "price": 269, "rating": 3.2, "reviews": 980, "bsr": 420},
                {"day_offset": 0, "price": 249, "rating": 3.2, "reviews": 1010, "bsr": 485},
            ],
            "reviews_sample": "cheap quality plastic, one earbud stopped working after 3 days. duplicate battery duplicate audio. complete waste of money, mic broken.",
            "initial_ai": {
                "trend_status": "Dropping",
                "sellability_score": 18,
                "website_ready": False,
                "estimated_margin_pct": 12.0,
                "recommended_selling_price": 299.0,
                "estimated_sourcing_cost": 160.0,
                "ai_reasoning": "Severe red alert! Continuous 58% price crash in 7 days indicating brutal price war between sellers dumping non-working stock. High return rate and terrible rating (3.2).",
                "red_flags": "Defective Bluetooth chips, high return rates (>25%), negative brand reputation risk.",
                "customer_pain_points": "Disconnects constantly; battery dies in 40 minutes; mic is unusable for calls.",
                "marketing_angle_for_website": "DO NOT SELL. Avoid dead stock.",
                "ai_summary_tamil_english": "Strict-ah avoid pannunga! Price war nadakkudhu (₹599-la irundhu ₹249-ku sarinjiruchu). Reviews full-ah 'waste of money' & 'not working'. Dead stock trap!"
            }
        },
        {
            "product_id": "MSH_SMART_WATCH_DEAD",
            "platform": "Meesho",
            "title": "Budget Bluetooth Calling Smart Watch with Silicone Strap",
            "category": "Wearables",
            "url": "https://www.meesho.com/p/smart-watch-budget/399",
            "image_url": "https://images.unsplash.com/photo-1508685096489-7aacd43bd3b1?w=500&q=80",
            # Dropping product: price ₹449 -> ₹289, rating 3.1, negative review keywords
            "metrics_trend": [
                {"day_offset": -6, "price": 449, "rating": 3.6, "reviews": 510, "bsr": 85},
                {"day_offset": -5, "price": 399, "rating": 3.5, "reviews": 530, "bsr": 130},
                {"day_offset": -4, "price": 369, "rating": 3.4, "reviews": 555, "bsr": 210},
                {"day_offset": -3, "price": 329, "rating": 3.3, "reviews": 580, "bsr": 310},
                {"day_offset": -2, "price": 310, "rating": 3.2, "reviews": 605, "bsr": 410},
                {"day_offset": -1, "price": 299, "rating": 3.1, "reviews": 630, "bsr": 520},
                {"day_offset": 0, "price": 289, "rating": 3.1, "reviews": 655, "bsr": 590},
            ],
            "reviews_sample": "Touch screen not working, duplicate software app crashes immediately, cheap quality plastic buckle broken within 2 days.",
            "initial_ai": {
                "trend_status": "Dropping",
                "sellability_score": 14,
                "website_ready": False,
                "estimated_margin_pct": 15.0,
                "recommended_selling_price": 349.0,
                "estimated_sourcing_cost": 210.0,
                "ai_reasoning": "Product facing heavy margin erosion and severe customer backlash. Rating down to 3.1. BSR dropped from 85 to 590 in 7 days.",
                "red_flags": "Faulty sensors, fake step counting, high RTO (Return to Origin) rate.",
                "customer_pain_points": "Screen unresponsive; battery drains in 4 hours; companion app filled with intrusive ads.",
                "marketing_angle_for_website": "DO NOT SELL. High return rate item.",
                "ai_summary_tamil_english": "Rombha bad product. Rating 3.1 ku vizhundhuduchu. Touch screen vela seiyyala nu returns adhigam varum. Delivery & RTO cost-la loss aagidum."
            }
        },
        {
            "product_id": "AMZ_B0_CAR_DUSTER",
            "platform": "Amazon India",
            "title": "Microfiber Car Cleaning Duster with Extendable Telescopic Handle",
            "category": "Automotive Accessories",
            "url": "https://www.amazon.in/dp/B0CARDUSTER",
            "image_url": "https://images.unsplash.com/photo-1520340356584-f9917d1eea6f?w=500&q=80",
            # Stable/Rising product: price ₹389, reviews 88 -> 165, BSR 190 -> 75
            "metrics_trend": [
                {"day_offset": -6, "price": 399, "rating": 4.4, "reviews": 88, "bsr": 190},
                {"day_offset": -5, "price": 399, "rating": 4.4, "reviews": 101, "bsr": 160},
                {"day_offset": -4, "price": 389, "rating": 4.4, "reviews": 115, "bsr": 130},
                {"day_offset": -3, "price": 389, "rating": 4.4, "reviews": 128, "bsr": 105},
                {"day_offset": -2, "price": 389, "rating": 4.5, "reviews": 140, "bsr": 92},
                {"day_offset": -1, "price": 389, "rating": 4.5, "reviews": 152, "bsr": 82},
                {"day_offset": 0, "price": 389, "rating": 4.5, "reviews": 165, "bsr": 74},
            ],
            "reviews_sample": "Wax treated microfiber traps heavy pollen and road dust effortlessly without scratching car paint. Extendable handle easily reaches car roof.",
            "initial_ai": {
                "trend_status": "High Sale Rising",
                "sellability_score": 89,
                "website_ready": True,
                "estimated_margin_pct": 47.0,
                "recommended_selling_price": 649.0,
                "estimated_sourcing_cost": 175.0,
                "ai_reasoning": "Indian car owners in metro and tier 2 cities face dust daily. High utility product with solid 4.5 rating and consistent weekly rank gains.",
                "red_flags": "Ensure the handle lock mechanism is sturdy during packing inspection.",
                "customer_pain_points": "Needs storage pouch; duster fibers require gentle hand washing.",
                "marketing_angle_for_website": "Clean entire SUV roof to tires in 3 minutes flat without a single drop of water or scratches!",
                "ai_summary_tamil_english": "Car owners-ku romba useful daily product. Water illama dust clean panradhukku super demand. ₹649-ku combo with micro-fiber cloth pottu website-la vikkalam."
            }
        },
        {
            "product_id": "MSH_SINK_SPLASH",
            "platform": "Meesho",
            "title": "Silicone Faucet Mat Sink Splash Guard & Draining Pad",
            "category": "Home & Kitchen",
            "url": "https://www.meesho.com/p/silicone-sink-guard/139",
            "image_url": "https://images.unsplash.com/photo-1584622650111-993a426fbf0a?w=500&q=80",
            # Sweet spot item: price ₹149, reviews 50 -> 112, BSR 410 -> 120
            "metrics_trend": [
                {"day_offset": -6, "price": 159, "rating": 4.2, "reviews": 50, "bsr": 410},
                {"day_offset": -5, "price": 159, "rating": 4.2, "reviews": 60, "bsr": 340},
                {"day_offset": -4, "price": 149, "rating": 4.2, "reviews": 72, "bsr": 270},
                {"day_offset": -3, "price": 149, "rating": 4.3, "reviews": 83, "bsr": 210},
                {"day_offset": -2, "price": 149, "rating": 4.3, "reviews": 94, "bsr": 165},
                {"day_offset": -1, "price": 149, "rating": 4.3, "reviews": 104, "bsr": 138},
                {"day_offset": 0, "price": 149, "rating": 4.3, "reviews": 115, "bsr": 118},
            ],
            "reviews_sample": "Slanted drainage design works smoothly. No more messy wet countertop around sink tap. Fits standard kitchen taps easily.",
            "initial_ai": {
                "trend_status": "High Sale Rising",
                "sellability_score": 86,
                "website_ready": True,
                "estimated_margin_pct": 55.0,
                "recommended_selling_price": 349.0,
                "estimated_sourcing_cost": 55.0,
                "ai_reasoning": "High-margin micro gadget. Sourcing cost in Surat/Delhi plastic hubs is ~₹50-55. Review velocity is up 130% in 7 days.",
                "red_flags": "Tap hole diameter is 6.5cm max; mention measurements clearly for odd sized taps.",
                "customer_pain_points": "Doesn't fit taps with curved base platforms.",
                "marketing_angle_for_website": "Say goodbye to stinky wet sink countertops! Automatic draining splash catcher keeps kitchen dry.",
                "ai_summary_tamil_english": "Kitchen sink area eppovum eerama irukkuradha thadukkum simple gadget. Bulk cost just ₹55, ₹349-ku 2 pieces combo kudutha easy conversions."
            }
        },
        {
            "product_id": "AMZ_B0_CABLE_ORGANIZER",
            "platform": "Amazon India",
            "title": "Minimalist Cable Management Box Organizer with Bamboo Wood Lid",
            "category": "Home Decor & Storage",
            "url": "https://www.amazon.in/dp/B0CABLEBOX",
            "image_url": "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=500&q=80",
            # Stable high margin: price ₹499, reviews 120 -> 185, BSR 220 -> 82
            "metrics_trend": [
                {"day_offset": -6, "price": 529, "rating": 4.6, "reviews": 120, "bsr": 220},
                {"day_offset": -5, "price": 529, "rating": 4.6, "reviews": 130, "bsr": 185},
                {"day_offset": -4, "price": 499, "rating": 4.6, "reviews": 142, "bsr": 150},
                {"day_offset": -3, "price": 499, "rating": 4.6, "reviews": 155, "bsr": 120},
                {"day_offset": -2, "price": 499, "rating": 4.6, "reviews": 166, "bsr": 102},
                {"day_offset": -1, "price": 499, "rating": 4.6, "reviews": 176, "bsr": 90},
                {"day_offset": 0, "price": 499, "rating": 4.6, "reviews": 188, "bsr": 80},
            ],
            "reviews_sample": "Hides dangerous extension cord and tangled mobile charger wires neatly under TV unit. Looks aesthetic with the bamboo finish.",
            "initial_ai": {
                "trend_status": "High Sale Rising",
                "sellability_score": 91,
                "website_ready": True,
                "estimated_margin_pct": 48.0,
                "recommended_selling_price": 799.0,
                "estimated_sourcing_cost": 210.0,
                "ai_reasoning": "Work-from-home and clean desk aesthetic trends remain strong in Bangalore, Hyderabad, Pune, Mumbai. High perceived aesthetic value.",
                "red_flags": "Requires sturdy outer carton to prevent plastic cracks during courier transit.",
                "customer_pain_points": "Large bulky laptop chargers might be tight if power strip is very tall.",
                "marketing_angle_for_website": "Hide ugly wire clutter and pet-proof your extension board with sleek Nordic aesthetic decor.",
                "ai_summary_tamil_english": "Clean desk and aesthetic home setup ku romba popular. Kids and pets wire touch pannama safe ah vekka mudiyum. ₹799-ku website-la premium feel-oda vikkalam."
            }
        }
    ]

    for p in demo_products:
        upsert_product(
            product_id=p["product_id"],
            platform=p["platform"],
            title=p["title"],
            category=p["category"],
            url=p["url"],
            image_url=p["image_url"],
            first_seen_date=(base_date - timedelta(days=6)).strftime("%Y-%m-%d"),
            db_path=db_path
        )

        for m in p["metrics_trend"]:
            dt_str = (base_date + timedelta(days=m["day_offset"])).strftime("%Y-%m-%d")
            insert_daily_metric(
                product_id=p["product_id"],
                date_str=dt_str,
                price=float(m["price"]),
                rating=float(m["rating"]),
                review_count=int(m["reviews"]),
                bsr_rank=int(m["bsr"]),
                recent_reviews_text=p["reviews_sample"],
                db_path=db_path
            )

        ai = p["initial_ai"]
        upsert_ai_analysis(
            product_id=p["product_id"],
            trend_status=ai["trend_status"],
            sellability_score=ai["sellability_score"],
            website_ready=ai["website_ready"],
            estimated_margin_pct=ai["estimated_margin_pct"],
            recommended_selling_price=ai["recommended_selling_price"],
            estimated_sourcing_cost=ai["estimated_sourcing_cost"],
            ai_reasoning=ai["ai_reasoning"],
            red_flags=ai["red_flags"],
            customer_pain_points=ai["customer_pain_points"],
            marketing_angle_for_website=ai["marketing_angle_for_website"],
            ai_summary_tamil_english=ai["ai_summary_tamil_english"],
            date_str=base_date.strftime("%Y-%m-%d"),
            db_path=db_path
        )

    # Add top 2 winners to shortlist by default for immediate storefront view
    add_to_shortlist("AMZ_B09XYZLIGHT", custom_selling_price=549.0, notes="High priority launch: test with 50 units first", db_path=db_path)
    add_to_shortlist("AMZ_B0B_AIRFRYPOT", custom_selling_price=599.0, notes="Essential kitchen catalog winner", db_path=db_path)

    # Populate 7-day social metrics & initial 99% confidence master verdicts
    from social_trends import generate_7day_social_history
    import json

    week_start = (base_date - timedelta(days=6)).strftime("%Y-%m-%d")
    week_end = base_date.strftime("%Y-%m-%d")

    # Master verdict seed configurations
    verdict_blueprints = {
        "AMZ_B0B_AIRFRYPOT": {
            "confidence_score": 98.4,
            "ecom_consistency": 96.0,
            "social_viral": 98.0,
            "sourcing": 160.0,
            "target_price": 599.0,
            "profit": 439.0,
            "blueprint": {
                "pillar_1_ecom_consistency": "96% (7-day BSR jumped from 240 to 42, review growth +123 with stable price)",
                "pillar_2_social_viral": "98% (Viral on Instagram Reels under #KitchenGadgetsIndia, high 'Link please' velocity)",
                "pillar_3_google_spike": "92% (+48% search volume spike in India over last 7 days)",
                "pillar_4_unit_economics": "99% (₹160 IndiaMART bulk sourcing, selling at ₹599 gives ₹439 gross profit)",
                "pillar_5_monopoly_check": "95% (No dominant brand monopoly; perfect white-label winner for new D2C website)",
                "target_audience": "Urban Indian homemakers & fitness lovers (25-45) using air fryers daily",
                "ad_hook_tanglish": "Air fryer clean panna kashdama irukka? Just indha food-grade silicone pot podunga, clean panna zero seconds!",
                "supplier_search": "Food Grade Silicone Air Fryer Pot 20cm Surat / Delhi Wholesale IndiaMART"
            },
            "summary_tanglish": "🔥 #1 Master Launch Winner! 98.4% Confidence. Air fryer demand surge aagudhu, ₹160 bulk sourcing, ₹599-ku website-la instant sales guaranteed."
        },
        "AMZ_B09XYZLIGHT": {
            "confidence_score": 96.2,
            "ecom_consistency": 94.0,
            "social_viral": 95.0,
            "sourcing": 140.0,
            "target_price": 549.0,
            "profit": 409.0,
            "blueprint": {
                "pillar_1_ecom_consistency": "94% (BSR rank leaped 81.6% from 480 to 88, review velocity +76)",
                "pillar_2_social_viral": "95% (Viral on YouTube Shorts home makeover & interior decor hacks)",
                "pillar_3_google_spike": "89% (+36% 7-day search surge in India)",
                "pillar_4_unit_economics": "96% (Sourcing ₹140, ₹549 retail, 74.5% margin before ad spend)",
                "pillar_5_monopoly_check": "92% (Aesthetic home lighting category open for fast branding)",
                "target_audience": "Homeowners, renters, aesthetics lovers in Metro & Tier-1 cities",
                "ad_hook_tanglish": "Wardrobe dark-ah irukka? Drill panna theva illa! Stick panna automatic magnetic light on aagum.",
                "supplier_search": "Smart PIR Motion Sensor LED Strip Light Rechargeable IndiaMART Bulk"
            },
            "summary_tanglish": "⭐ #2 Launch Winner! 96.2% Confidence. Aesthetic home decor impulse buy, ₹140 sourcing, ₹549 selling price-la high conversion."
        },
        "AMZ_TECH_CLEAN_PEN": {
            "confidence_score": 93.8,
            "ecom_consistency": 91.0,
            "social_viral": 94.0,
            "sourcing": 48.0,
            "target_price": 399.0,
            "profit": 351.0,
            "blueprint": {
                "pillar_1_ecom_consistency": "91% (BSR from 175 to 36, review velocity +174)",
                "pillar_2_social_viral": "94% (Massive comment intent: 'Send link bro' across tech shorts)",
                "pillar_3_google_spike": "85% (Consistent daily search demand for earphone cleaning)",
                "pillar_4_unit_economics": "98% (Sourcing just ₹48, featherweight 45g shipping cost)",
                "pillar_5_monopoly_check": "90% (Low price sweet spot ₹399 with free delivery converts instantly)",
                "target_audience": "College students, remote workers, gadget enthusiasts",
                "ad_hook_tanglish": "Unga AirPods-la dust and dirt irukka? Indha 5-in-1 pen tool 1 minute-la brand new aakkidum!",
                "supplier_search": "5 in 1 Multi Function Earphone Cleaning Pen Tool Wholesale IndiaMART"
            },
            "summary_tanglish": "🎯 #3 Launch Winner! 93.8% Confidence. Ultra-low sourcing cost (₹48), lightweight shipping, instant ₹399 impulse conversion."
        }
    }

    for p in demo_products:
        pid = p["product_id"]
        # Generate 7-day social metrics
        social_records = generate_7day_social_history(pid, p["title"], base_viral_score=float(p["initial_ai"]["sellability_score"]))
        for s in social_records:
            insert_social_metric(
                product_id=pid,
                date_str=s["date"],
                social_views_score=s["social_views_score"],
                buyer_intent_comments_score=s["buyer_intent_comments_score"],
                google_trend_score=s["google_trend_score"],
                viral_velocity_7d=s["viral_velocity_7d"],
                trending_platform=s["trending_platform"],
                db_path=db_path
            )

        # Insert master verdict if top product
        if pid in verdict_blueprints:
            vb = verdict_blueprints[pid]
            upsert_weekly_launch_verdict(
                week_start_date=week_start,
                week_end_date=week_end,
                product_id=pid,
                confidence_score=vb["confidence_score"],
                ecom_consistency_7d=vb["ecom_consistency"],
                social_viral_score=vb["social_viral"],
                sourcing_cost_est=vb["sourcing"],
                target_selling_price=vb["target_price"],
                net_profit_per_unit=vb["profit"],
                launch_blueprint_json=json.dumps(vb["blueprint"]),
                verdict_summary_tanglish=vb["summary_tanglish"],
                db_path=db_path
            )


def insert_social_metric(
    product_id: str,
    date_str: str,
    social_views_score: int,
    buyer_intent_comments_score: int,
    google_trend_score: int,
    viral_velocity_7d: float,
    trending_platform: str = "Instagram Reels",
    db_path: str = DB_FILE
) -> None:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO social_metrics_history (product_id, date, social_views_score, buyer_intent_comments_score, google_trend_score, viral_velocity_7d, trending_platform)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(product_id, date) DO UPDATE SET
        social_views_score=excluded.social_views_score,
        buyer_intent_comments_score=excluded.buyer_intent_comments_score,
        google_trend_score=excluded.google_trend_score,
        viral_velocity_7d=excluded.viral_velocity_7d,
        trending_platform=excluded.trending_platform;
    """, (product_id, date_str, social_views_score, buyer_intent_comments_score, google_trend_score, viral_velocity_7d, trending_platform))
    conn.commit()
    conn.close()


def get_social_metrics_history(product_id: str, limit: int = 7, db_path: str = DB_FILE) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT date, social_views_score, buyer_intent_comments_score, google_trend_score, viral_velocity_7d, trending_platform
    FROM social_metrics_history
    WHERE product_id = ?
    ORDER BY date ASC
    LIMIT ?;
    """, (product_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def upsert_weekly_launch_verdict(
    week_start_date: str,
    week_end_date: str,
    product_id: str,
    confidence_score: float,
    ecom_consistency_7d: float,
    social_viral_score: float,
    sourcing_cost_est: float,
    target_selling_price: float,
    net_profit_per_unit: float,
    launch_blueprint_json: str,
    verdict_summary_tanglish: str,
    db_path: str = DB_FILE
) -> None:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO weekly_launch_verdict (
        week_start_date, week_end_date, product_id, confidence_score,
        ecom_consistency_7d, social_viral_score, sourcing_cost_est,
        target_selling_price, net_profit_per_unit, launch_blueprint_json,
        verdict_summary_tanglish
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(week_start_date, product_id) DO UPDATE SET
        week_end_date=excluded.week_end_date,
        confidence_score=excluded.confidence_score,
        ecom_consistency_7d=excluded.ecom_consistency_7d,
        social_viral_score=excluded.social_viral_score,
        sourcing_cost_est=excluded.sourcing_cost_est,
        target_selling_price=excluded.target_selling_price,
        net_profit_per_unit=excluded.net_profit_per_unit,
        launch_blueprint_json=excluded.launch_blueprint_json,
        verdict_summary_tanglish=excluded.verdict_summary_tanglish;
    """, (week_start_date, week_end_date, product_id, confidence_score, ecom_consistency_7d, social_viral_score, sourcing_cost_est, target_selling_price, net_profit_per_unit, launch_blueprint_json, verdict_summary_tanglish))
    conn.commit()
    conn.close()


def get_latest_weekly_verdicts(limit: int = 10, db_path: str = DB_FILE) -> List[Dict[str, Any]]:
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT w.*, p.title, p.platform, p.category, p.image_url, p.url
    FROM weekly_launch_verdict w
    JOIN products p ON w.product_id = p.product_id
    ORDER BY w.confidence_score DESC, w.id DESC
    LIMIT ?;
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_product_weekly_verdict(product_id: str, db_path: str = DB_FILE) -> Optional[Dict[str, Any]]:
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT w.*, p.title, p.platform, p.category, p.image_url, p.url
    FROM weekly_launch_verdict w
    JOIN products p ON w.product_id = p.product_id
    WHERE w.product_id = ?
    ORDER BY w.id DESC
    LIMIT 1;
    """, (product_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_combined_7day_product_signals(product_id: str, db_path: str = DB_FILE) -> Any:
    import pandas as pd
    ecom_history = get_product_metrics_history(product_id, days=7, db_path=db_path)
    social_history = get_social_metrics_history(product_id, limit=7, db_path=db_path)
    
    ecom_dict = {row["date"]: row for row in ecom_history}
    social_dict = {row["date"]: row for row in social_history}
    
    all_dates = sorted(list(set(list(ecom_dict.keys()) + list(social_dict.keys()))))
    rows = []
    for d in all_dates:
        ec = ecom_dict.get(d, {})
        sc = social_dict.get(d, {})
        rows.append({
            "date": d,
            "product_id": product_id,
            "social_views_score": sc.get("social_views_score", 50.0),
            "buyer_intent_score": sc.get("buyer_intent_comments_score", 50.0),
            "google_trend_score": sc.get("google_trend_score", 50.0),
            "viral_velocity_7d": sc.get("viral_velocity_7d", 10.0),
            "price": ec.get("price", 0.0),
            "rating": ec.get("rating", 4.0),
            "review_count": ec.get("review_count", 0),
            "bsr_rank": ec.get("bsr_rank", 1000)
        })
    return pd.DataFrame(rows)



def log_agent_run(
    status: str,
    scraped_count: int = 0,
    analyzed_count: int = 0,
    auto_shortlisted_count: int = 0,
    summary: str = "",
    details: str = "",
    timestamp: Optional[str] = None,
    db_path: str = DB_FILE
) -> int:
    if not timestamp:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO agent_logs (timestamp, status, scraped_count, analyzed_count, auto_shortlisted_count, summary, details)
    VALUES (?, ?, ?, ?, ?, ?, ?);
    """, (timestamp, status, scraped_count, analyzed_count, auto_shortlisted_count, summary, details))
    log_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return log_id


def get_agent_logs(limit: int = 20, db_path: str = DB_FILE) -> List[Dict[str, Any]]:
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, timestamp, status, scraped_count, analyzed_count, auto_shortlisted_count, summary, details
    FROM agent_logs
    ORDER BY timestamp DESC, id DESC
    LIMIT ?;
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_last_agent_run(db_path: str = DB_FILE) -> Optional[Dict[str, Any]]:
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, timestamp, status, scraped_count, analyzed_count, auto_shortlisted_count, summary, details
    FROM agent_logs
    ORDER BY timestamp DESC, id DESC
    LIMIT 1;
    """)
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


if __name__ == "__main__":
    init_db()
    seed_demo_data()
    print("Database initialized and seeded with 10 Indian e-commerce products!")
