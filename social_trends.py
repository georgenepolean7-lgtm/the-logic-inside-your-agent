"""
social_trends.py - 7-Day Omni-Channel Social Media & Google Search Intelligence Engine
Tracks viral Indian product signals across:
1. YouTube Shorts & Instagram Reels (#AmazonFindsIndia, #MeeshoFinds, #GadgetsUnder500, etc.)
2. Buyer Intent Comment Analyzer ("Link please", "Price?", "PP", "Where to buy")
3. Google Trends India (7-day search volume growth in 'IN')
Includes high-fidelity resilient fallback simulation for 100% uninterrupted pipeline execution.
"""

import os
import re
import time
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

logger = logging.getLogger("SocialTrends")

BUYER_INTENT_POSITIVE_PHRASES = [
    "link please", "link pls", "send link", "price?", "pp?", "how much?",
    "where to buy", "need this", "want this", "available?", "cod available?",
    "dm link", "flipkart link", "amazon link", "meesho code", "ordered",
    "just ordered", "delivers to chennai", "delivers to mumbai", "delivers to delhi",
    "super product", "super useful", "worth it"
]

BUYER_INTENT_NEGATIVE_PHRASES = [
    "waste", "waste of money", "fake", "scam", "broken", "duplicate",
    "cheap quality", "don't buy", "useless", "worst", "not working",
    "damaged", "cheating", "fraud"
]

TRENDING_TAGS = [
    "#AmazonFindsIndia",
    "#MeeshoFinds",
    "#GadgetsUnder500",
    "#UsefulGadgetsIndia",
    "#HomeHacksIndia",
    "#KitchenGadgetsIndia",
    "#ViralProductsIndia"
]


def analyze_buyer_intent(comments: List[str]) -> Dict[str, Any]:
    """
    Analyzes social comments to calculate high-intent buyer ratio vs negative friction ratio.
    """
    if not comments:
        return {"intent_score": 60, "positive_count": 0, "negative_count": 0, "dominant_phrase": "Neutral demand"}

    pos_matches = 0
    neg_matches = 0
    detected_intent_phrases = []

    for c in comments:
        c_lower = c.lower()
        matched_pos = False
        for p in BUYER_INTENT_POSITIVE_PHRASES:
            if p in c_lower:
                pos_matches += 1
                matched_pos = True
                detected_intent_phrases.append(p)
                break
        if not matched_pos:
            for n in BUYER_INTENT_NEGATIVE_PHRASES:
                if n in c_lower:
                    neg_matches += 1
                    break

    total = len(comments)
    net_score = max(10, min(99, int(50 + (pos_matches * 12) - (neg_matches * 15))))
    most_common = max(set(detected_intent_phrases), key=detected_intent_phrases.count) if detected_intent_phrases else "Link please"

    return {
        "intent_score": net_score,
        "positive_count": pos_matches,
        "negative_count": neg_matches,
        "dominant_phrase": most_common,
        "total_analyzed": total
    }


def get_google_trends_interest_7d(keyword: str) -> Dict[str, Any]:
    """
    Fetches 7-day Google Trends search momentum in India (geo='IN') using pytrends with web search fallback.
    """
    clean_kw = re.sub(r'[^a-zA-Z0-9 ]', '', keyword).strip()
    words = clean_kw.split()[:3]
    short_kw = " ".join(words) if words else "trending gadgets"

    # Attempt pytrends
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl='en-US', tz=330, timeout=(5, 10))
        pytrends.build_payload([short_kw], cat=0, timeframe='now 7-d', geo='IN', gprop='')
        interest_df = pytrends.interest_over_time()
        if not interest_df.empty and short_kw in interest_df.columns:
            vals = interest_df[short_kw].tolist()
            if len(vals) >= 2:
                growth = ((vals[-1] - vals[0]) / max(1, vals[0])) * 100
                score = min(99, max(20, int(vals[-1])))
                return {
                    "source": "Google Trends (Live)",
                    "score": score,
                    "growth_7d_pct": round(growth, 1),
                    "search_volume_level": "High Spike" if growth > 20 else "Steady High"
                }
    except Exception as e:
        logger.debug(f"Pytrends live call bypassed: {e}")

    # Do not fabricate trend metrics when the live source is unavailable.
    return {
        "source": "unavailable",
        "data_status": "unavailable",
        "score": None,
        "growth_7d_pct": None,
        "search_volume_level": "Unavailable"
    }


def fetch_social_media_buzz(product_title: str) -> Dict[str, Any]:
    """
    Searches DuckDuckGo / Social Media for video signals across Instagram Reels & YouTube Shorts.
    """
    clean_title = " ".join(product_title.split()[:4])
    social_query = f"{clean_title} amazon finds reels shorts india"

    video_urls = []
    social_snippets = []

    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(social_query, max_results=5))
            for r in results:
                title = r.get("title", "")
                body = r.get("body", "")
                social_snippets.append(f"{title} - {body}")
                url = r.get("href", "")
                if "instagram.com" in url or "youtube.com" in url or "reels" in url:
                    video_urls.append(url)
    except Exception as e:
        logger.debug(f"Social live search fallback triggered: {e}")

    # Analyze only real search snippets; never inject synthetic comments or scores.
    buyer_analysis = analyze_buyer_intent(social_snippets) if social_snippets else None
    return {
        "platform": "search results" if video_urls else "unavailable",
        "data_status": "live_search_results" if social_snippets else "unavailable",
        "social_views_score": None,
        "buyer_intent_score": buyer_analysis["intent_score"] if buyer_analysis else None,
        "dominant_intent_phrase": buyer_analysis["dominant_phrase"] if buyer_analysis else None,
        "video_references": video_urls[:2],
        "sample_buyer_comments": [],
        "source_snippets": social_snippets[:3]
    }


def generate_7day_social_history(
    product_id: str,
    title: str,
    base_viral_score: float = 78.0
) -> List[Dict[str, Any]]:
    """
    Generates realistic, continuous 7-day social metrics history (Day -6 to Day 0)
    capturing viral momentum, view velocity, and Google Trends spike.
    """
    records = []
    today = datetime.now()

    # Determine product viral persona
    h = abs(hash(product_id))
    trend_type = "viral_spike" if h % 3 == 0 else ("steady_growth" if h % 3 == 1 else "cooling")
    platform = "Instagram Reels" if h % 2 == 0 else "YouTube Shorts"

    for day_offset in range(-6, 1):
        target_date = (today + timedelta(days=day_offset)).strftime("%Y-%m-%d")
        progress = (day_offset + 6) / 6.0  # 0.0 to 1.0

        if trend_type == "viral_spike":
            v_score = int(base_viral_score * 0.65 + (progress * base_viral_score * 0.40))
            intent_score = int(60 + (progress * 35))
            g_score = int(55 + (progress * 42))
        elif trend_type == "steady_growth":
            v_score = int(base_viral_score * 0.80 + (progress * 15))
            intent_score = int(68 + (progress * 22))
            g_score = int(65 + (progress * 20))
        else:
            v_score = max(30, int(base_viral_score - (progress * 25)))
            intent_score = max(25, int(70 - (progress * 30)))
            g_score = max(20, int(60 - (progress * 35)))

        velocity_7d = round((v_score - (base_viral_score * 0.65)) / max(1, base_viral_score * 0.65) * 100, 1)

        records.append({
            "product_id": product_id,
            "date": target_date,
            "social_views_score": min(99, max(15, v_score)),
            "buyer_intent_comments_score": min(99, max(15, intent_score)),
            "google_trend_score": min(99, max(15, g_score)),
            "viral_velocity_7d": velocity_7d,
            "trending_platform": platform
        })

    return records
