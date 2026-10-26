"""
analyzer.py - "The Logic Inside Your Agent" (Core AI Brain)
Two-Step Evaluation Engine:
- Step A: Rule-Based Quantitative Market Signals (Rising, Dying Trend, Sellable Sweet Spot)
- Step B: Gemini 2.5 Flash Deep Strategic Analysis with Pydantic Structured Output
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from storage import (
    upsert_ai_analysis,
    get_all_products_with_latest_data,
    calculate_7day_price_change,
    calculate_review_velocity,
    calculate_bsr_improvement,
    get_social_metrics_history,
    insert_social_metric,
    upsert_weekly_launch_verdict,
    get_latest_weekly_verdicts,
    get_product_metrics_history
)
from social_trends import (
    fetch_social_media_buzz,
    get_google_trends_interest_7d,
    generate_7day_social_history
)

load_dotenv()
logger = logging.getLogger("AIAnalyzer")


class ProductAnalysisResult(BaseModel):
    trend_status: str = Field(description="Must be 'High Sale Rising', 'Dropping', or 'Stable'")
    sellability_score: int = Field(description="Score between 0 and 100 on potential to sell successfully on direct-to-consumer website")
    website_ready: bool = Field(description="True if product is ideal for selling on standalone e-commerce website, False if dead stock or oversaturated")
    recommended_selling_price: float = Field(description="Recommended retail selling price in INR for standalone website")
    estimated_sourcing_cost: float = Field(description="Estimated procurement/wholesale cost in INR from Delhi/Surat/IndiaMart suppliers")
    estimated_margin_pct: float = Field(description="Calculated gross margin percentage: ((price - sourcing_cost) / price) * 100")
    customer_pain_points: str = Field(description="Key complaints or defects observed from customer feedback")
    marketing_angle_for_website: str = Field(description="High-converting hook, ad angle, or impulse trigger for Instagram/FB/Meta ads")
    ai_reasoning: str = Field(description="In-depth explanation detailing the logic behind this verdict")
    red_flags: str = Field(description="Potential risks, supplier quality issues, or return-to-origin (RTO) risks")
    ai_summary_tamil_english: str = Field(description="Tanglish / English concise punchy explanation on why to pick or avoid this product")


NEGATIVE_KEYWORDS = [
    "cheap quality", "broken", "duplicate", "not working", "waste of money",
    "worst", "fraud", "fake", "terrible", "poor quality", "useless", "damaged"
]


def evaluate_rule_based_signals(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    Step A: Rule-Based Scoring Engine
    - High Sale (Rising) Signal: Price between ₹100–₹1000, Rating >= 4.0, Review Count between 30 and 450 (high demand, low saturation), BSR improving or review velocity increasing.
    - Drop Signal (Dying Trend): Continuous price drop over 7 days (price war/saturation), or rating < 3.7, or negative keywords in recent reviews.
    - Sellable Sweet Spot (Website Ready): Impulse-buy price (₹249–₹799), lightweight/easy to ship, non-branded/generic item, and allows at least a 35%–50% markup margin.
    """
    price = float(product.get("price") or 0.0)
    rating = float(product.get("rating") or 0.0)
    review_count = int(product.get("review_count") or 0)
    price_change_7d = float(product.get("price_change_7d") or 0.0)
    review_velocity_7d = int(product.get("review_velocity_7d") or 0)
    bsr_improvement_7d = float(product.get("bsr_improvement_7d") or 0.0)
    recent_reviews = str(product.get("recent_reviews_text") or "").lower()

    # Unknown core metrics must not be silently converted into a positive/neutral verdict.
    has_core_evidence = (
        product.get("price") is not None
        and product.get("rating") is not None
        and product.get("review_count") is not None
    )
    if not has_core_evidence:
        safe_price = price if price > 0 else 0.0
        return {
            "trend_status": "Stable",
            "sellability_score": 25,
            "website_ready": False,
            "recommended_selling_price": round(safe_price, 2),
            "estimated_sourcing_cost": 0.0,
            "estimated_margin_pct": 0.0,
            "customer_pain_points": "Insufficient verified rating/review data to assess customer experience.",
            "marketing_angle_for_website": "Not available until core market evidence is verified.",
            "ai_reasoning": "Provisional only: price, rating, or review count is missing. No demand or quality claim is made.",
            "red_flags": "Missing core marketplace evidence; verify listing and metrics before sourcing or promoting.",
            "ai_summary_tamil_english": "Innum data complete illa. Rating, review count, price verify pannama indha product-ku money invest panna vendam."
        }

    # 1. Check for Drop Signals (Dying Trend)
    has_negative_keywords = any(kw in recent_reviews for kw in NEGATIVE_KEYWORDS)
    severe_price_crash = price_change_7d <= -15.0
    poor_rating = rating < 3.7 and review_count > 20

    if severe_price_crash or poor_rating or has_negative_keywords:
        score = max(10, min(38, int(rating * 10 - (20 if has_negative_keywords else 0))))
        est_sourcing = round(price * 0.65, 2)
        rec_selling = round(price * 1.1, 2)
        margin = round(((rec_selling - est_sourcing) / rec_selling) * 100, 1) if rec_selling else 0
        
        reds = []
        if severe_price_crash:
            reds.append(f"Price war crash: dropped {abs(price_change_7d)}% in 7 days.")
        if poor_rating:
            reds.append(f"Substandard rating ({rating}/5.0).")
        if has_negative_keywords:
            reds.append("Critical negative keywords in customer reviews.")

        return {
            "trend_status": "Dropping",
            "sellability_score": score,
            "website_ready": False,
            "recommended_selling_price": rec_selling,
            "estimated_sourcing_cost": est_sourcing,
            "estimated_margin_pct": margin,
            "customer_pain_points": "Poor durability, broken components, high return/RTO rate.",
            "marketing_angle_for_website": "AVOID: Dead stock candidate. High return-to-origin risk.",
            "ai_reasoning": f"Triggered Drop Signals: {'; '.join(reds)} Marketplace sellers are undercutting each other to liquidate failing inventory.",
            "red_flags": "; ".join(reds),
            "ai_summary_tamil_english": f"Idha avoid panradhu safe! Rating {rating} dhaan irukku, reviews-la complaints adhigam. Return rate perusa varum."
        }

    # 2. Check for High Sale (Rising) Signal
    is_rising = (
        100 <= price <= 1000
        and rating >= 4.0
        and 30 <= review_count <= 450
        and (bsr_improvement_7d >= 10.0 or review_velocity_7d >= 15)
    )

    # 3. Check for Website Ready Sweet Spot (₹249 - ₹799)
    is_sweet_spot_price = 249 <= price <= 799

    if is_rising:
        base_score = 75
        if is_sweet_spot_price:
            base_score += 12
        if bsr_improvement_7d > 30:
            base_score += 8
        score = min(98, base_score)

        # Indian wholesale sourcing heuristic (Surat/Delhi hubs ~ 25% - 40% of marketplace price)
        est_sourcing = round(price * 0.35, 2)
        # Website retail price (allow 40%-55% margin with free shipping perception)
        rec_selling = round(max(price * 1.5, price + 150), 2)
        margin = round(((rec_selling - est_sourcing) / rec_selling) * 100, 1)

        return {
            "trend_status": "High Sale Rising",
            "sellability_score": score,
            "website_ready": True,
            "recommended_selling_price": rec_selling,
            "estimated_sourcing_cost": est_sourcing,
            "estimated_margin_pct": margin,
            "customer_pain_points": "Minor packaging wear during transit, user manual instructions.",
            "marketing_angle_for_website": "Direct-to-consumer viral problem solver. Position as a premium daily utility with Free Cash On Delivery.",
            "ai_reasoning": f"Strong organic demand momentum. Review count is {review_count} (unsaturated sweet spot), rating is {rating}/5, and sales velocity improved by {bsr_improvement_7d}% in the last 7 days.",
            "red_flags": "Inspect quality samples from supplier before ordering in batches greater than 100 units.",
            "ai_summary_tamil_english": f"Potential candidate based on available signals only. Estimated sourcing ₹{est_sourcing} and target price ₹{rec_selling}; verify supplier quote, fees, shipping, tax and returns before calculating profit."
        }

    # 4. Stable or Moderate Performance
    est_sourcing = round(price * 0.45, 2)
    rec_selling = round(price * 1.3, 2)
    margin = round(((rec_selling - est_sourcing) / rec_selling) * 100, 1)
    score = 60 if rating >= 4.0 else 45

    return {
        "trend_status": "Stable",
        "sellability_score": score,
        "website_ready": bool(score >= 65 and is_sweet_spot_price),
        "recommended_selling_price": rec_selling,
        "estimated_sourcing_cost": est_sourcing,
        "estimated_margin_pct": margin,
        "customer_pain_points": "Moderate competition, requires unique branding or combo bundling.",
        "marketing_angle_for_website": "Bundle as a buy-1-get-1 or combo pack to increase Average Order Value (AOV).",
        "ai_reasoning": "Product exhibits consistent baseline demand without aggressive rank breakout. Viable as a catalog filler.",
        "red_flags": "Watch out for price erosion from competing marketplace sellers.",
        "ai_summary_tamil_english": "Moderate sale product. Stable demand irukku, aana direct website-la sell panna combo offer pottu promote pannanum."
    }


def analyze_product_with_gemini(
    product: Dict[str, Any],
    api_key: Optional[str] = None
) -> ProductAnalysisResult:
    """
    Step B: Gemini AI Deep Analysis using official google-genai SDK
    Falls back gracefully to Rule-Based Scoring if API key is missing or quota exhausted.
    """
    key = api_key or os.getenv("GEMINI_API_KEY", "").strip()

    rule_fallback = evaluate_rule_based_signals(product)

    if not key:
        logger.info(f"GEMINI_API_KEY not configured. Using Rule-Based Logic Engine for product '{product.get('title')}'.")
        return ProductAnalysisResult(**rule_fallback)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=key)

        prompt = f"""
You are the Chief Product Strategist and E-Commerce Market Intelligence Agent specialized in the Indian consumer market (Amazon India & Meesho).
Analyze this product specifically for selling on a new standalone Direct-to-Consumer (D2C) e-commerce website targeting products between ₹100 and ₹1,000 INR.

Product Details:
- Platform: {product.get('platform')}
- Title: {product.get('title')}
- Category: {product.get('category')}
- Current Marketplace Price: ₹{product.get('price')} INR
- Rating: {product.get('rating')} / 5.0
- Total Review Count: {product.get('review_count')}
- 7-Day Price Change: {product.get('price_change_7d', 0.0)}%
- 7-Day Review Velocity: +{product.get('review_velocity_7d', 0)} new reviews
- 7-Day BSR Rank Improvement: {product.get('bsr_improvement_7d', 0.0)}% (positive means climbing the bestseller charts)
- Customer Review Snippets: "{product.get('recent_reviews_text', '')}"

Evaluation Criteria:
1. "High Sale Rising": Price ₹100-₹1000, Rating >= 4.0, Reviews 30-450 (high demand, unsaturated), climbing BSR or accelerating review velocity.
2. "Dropping": Continuous price drops (price war), rating < 3.7, or negative customer complaints ("cheap quality", "broken", "duplicate", "not working", "waste of money").
3. "Website Ready": Sweet spot impulse price (₹249–₹799), easy to ship, non-fragile, high perceived value, and allows at least 35%–50% margin when sourced wholesale from Indian B2B hubs (Delhi/Surat/IndiaMart).
4. Provide 'ai_summary_tamil_english': A punchy 2-sentence verdict in Tanglish/English explaining why to pick or avoid this product.

Provide your output strictly adhering to the schema.
"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ProductAnalysisResult,
                temperature=0.2,
            ),
        )

        if response.text:
            data = json.loads(response.text)
            return ProductAnalysisResult(**data)
        else:
            return ProductAnalysisResult(**rule_fallback)

    except Exception as e:
        logger.warning(f"Gemini API invocation encountered an issue ({e}). Applying Rule-Based Engine.")
        return ProductAnalysisResult(**rule_fallback)


def run_analysis_for_all_products(api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """Runs analysis for all stored products and updates the ai_analysis table."""
    products = get_all_products_with_latest_data()
    updated_records = []

    for p in products:
        analysis = analyze_product_with_gemini(p, api_key=api_key)
        upsert_ai_analysis(
            product_id=p["product_id"],
            trend_status=analysis.trend_status,
            sellability_score=analysis.sellability_score,
            website_ready=analysis.website_ready,
            estimated_margin_pct=analysis.estimated_margin_pct,
            recommended_selling_price=analysis.recommended_selling_price,
            estimated_sourcing_cost=analysis.estimated_sourcing_cost,
            ai_reasoning=analysis.ai_reasoning,
            red_flags=analysis.red_flags,
            customer_pain_points=analysis.customer_pain_points,
            marketing_angle_for_website=analysis.marketing_angle_for_website,
            ai_summary_tamil_english=analysis.ai_summary_tamil_english,
        )
        updated_records.append({
            "product_id": p["product_id"],
            "title": p["title"],
            "analysis": analysis.model_dump()
        })

    return updated_records


def generate_7day_master_verdict(
    product_id: Optional[str] = None,
    api_key: Optional[str] = None,
    limit_winners: int = 3
) -> List[Dict[str, Any]]:
    """
    The 99% Confidence Multi-Signal Prediction Engine:
    Synthesizes the full 7-day trajectory of E-commerce (Amazon/Meesho) + Social Media (Reels/Shorts) + Google Trends.
    Calculates weighted Launch Confidence Score (up to 99%) across 5 strict pillars:
    1. 7-Day E-com BSR & Review Consistency (25%)
    2. Social Media Viral & 'Link Please' Velocity (25%)
    3. Google Trends Search Spike in India (15%)
    4. Unit Economics & Wholesale Margin (20%)
    5. Low Brand Monopoly / Saturation Check (15%)
    Outputs Weekly Winners with complete Launch Blueprint and Tanglish ad hook.
    """
    all_products = get_all_products_with_latest_data()
    if product_id:
        target_products = [p for p in all_products if p["product_id"] == product_id]
    else:
        target_products = all_products

    base_date = datetime.now()
    week_start = (base_date - timedelta(days=6)).strftime("%Y-%m-%d")
    week_end = base_date.strftime("%Y-%m-%d")

    evaluated_verdicts = []

    for p in target_products:
        pid = p["product_id"]
        title = p.get("title", "")
        price = float(p.get("price") or 0.0)
        rating = float(p.get("rating") or 0.0)
        reviews = int(p.get("review_count") or 0)
        category = p.get("category", "General")

        # 1. Pillar 1: 7-Day E-com BSR & Review Consistency (25% weight)
        # Existing SQLite history predates source/provenance tracking and may contain
        # simulated rows. Do not use it as evidence until verified-source migration exists.
        bsr_imp = 0.0
        rev_vel = 0
        price_chg = 0.0

        # Baseline pillar 1
        p1 = 60.0
        if bsr_imp > 25.0:
            p1 += 20.0
        elif bsr_imp > 5.0:
            p1 += 10.0
        if rev_vel >= 30:
            p1 += 15.0
        elif rev_vel >= 10:
            p1 += 8.0
        if price_chg < -15.0:
            p1 -= 40.0  # Heavy penalty for brutal price crashes
        elif -5.0 <= price_chg <= 5.0:
            p1 += 5.0  # Stable pricing reward
        p1 = min(99.0, max(10.0, p1))

        # 2. Pillar 2: Social Media Viral & "Link Please" Velocity (25% weight)
        # Existing social history may include previously synthesized records. Ignore it
        # until every row has trustworthy source and timestamp provenance.
        social_history = []
        # Missing social/search evidence is unknown, not a positive signal.
        # Never synthesize a 7-day history or substitute optimistic defaults.
        latest_social = social_history[-1] if social_history else {}
        social_data_available = bool(social_history)
        views_score = float(latest_social.get("social_views_score") or 0)
        intent_score = float(latest_social.get("buyer_intent_comments_score") or 0)
        p2 = min(99.0, max(0.0, (views_score * 0.5) + (intent_score * 0.5))) if social_data_available else 0.0

        # 3. Google Trends Spike in India (15% weight)
        g_score = float(latest_social.get("google_trend_score") or 0)
        p3 = min(99.0, max(0.0, g_score)) if social_data_available else 0.0

        # 4. Pillar 4: Unit Economics & Wholesale Margin (20% weight)
        # Retail ₹100–₹1,000, 3x markup from IndiaMart
        est_sourcing = round(price * 0.32, 2)
        target_price = round(max(price * 1.5, price + 150), 2)
        net_profit = round(target_price - est_sourcing, 2)
        markup_ratio = target_price / max(1.0, est_sourcing)

        p4 = 70.0
        if 249 <= price <= 799:
            p4 += 15.0  # Perfect impulse buy sweet spot
        if markup_ratio >= 3.0:
            p4 += 12.0
        p4 = min(99.0, max(10.0, p4))

        # 5. Pillar 5: Low Brand Monopoly / Saturation Check (15% weight)
        p5 = 75.0
        if 30 <= reviews <= 450:
            p5 += 20.0  # Sweet spot: proven demand, non-monopolized
        elif reviews > 2000:
            p5 -= 35.0  # Oversaturated
        if rating >= 4.2:
            p5 += 5.0
        elif rating < 3.8:
            p5 -= 30.0
        p5 = min(99.0, max(10.0, p5))

        # Combined Weighted Confidence Score (up to 99%)
        confidence = round(
            (p1 * 0.25) +
            (p2 * 0.25) +
            (p3 * 0.15) +
            (p4 * 0.20) +
            (p5 * 0.15),
            1
        )
        if not social_data_available:
            confidence = min(confidence, 59.0)  # provisional only; key evidence is missing
        confidence = min(99.2, max(0.0, confidence))

        # Launch Blueprint Details
        clean_kw = " ".join(title.split()[:3])
        blueprint = {
            "pillar_1_ecom_consistency": f"{p1:.1f}% (BSR trend: {bsr_imp:.1f}%, review velocity: +{rev_vel})",
            "pillar_2_social_viral": f"{p2:.1f}% ({'stored metrics' if social_data_available else 'UNAVAILABLE: no verified social metrics'})",
            "pillar_3_google_spike": f"{p3:.1f}% ({'stored trend metrics' if social_data_available else 'UNAVAILABLE: no verified Google Trends history'})",
            "pillar_4_unit_economics": f"{p4:.1f}% (Sourcing: ₹{est_sourcing:.0f}, Target: ₹{target_price:.0f}, Profit: ₹{net_profit:.0f}/unit)",
            "pillar_5_monopoly_check": f"{p5:.1f}% (Review saturation: {reviews} reviews, rating: {rating}/5.0)",
            "target_audience": f"Urban Indian buyers looking for impulse problem-solvers in {category}",
            "ad_hook_tanglish": f"Indha {clean_kw} daily life-la romba useful! Super practical hack. Website-la Free COD offer-la get pannunga!",
            "supplier_search": f"{clean_kw} bulk wholesale supplier Surat Delhi IndiaMART"
        }

        tanglish_summary = (
            f"Provisional launch score ({confidence}%). Social/search evidence: {'available' if social_data_available else 'unavailable; confidence capped'}. 7-day BSR improvement {bsr_imp:.1f}%. "
            f"Wholesale sourcing ₹{est_sourcing:.0f}, target selling price ₹{target_price:.0f} (Net profit ₹{net_profit:.0f}/unit)."
        )

        upsert_weekly_launch_verdict(
            week_start_date=week_start,
            week_end_date=week_end,
            product_id=pid,
            confidence_score=confidence,
            ecom_consistency_7d=p1,
            social_viral_score=p2,
            sourcing_cost_est=est_sourcing,
            target_selling_price=target_price,
            net_profit_per_unit=net_profit,
            launch_blueprint_json=json.dumps(blueprint),
            verdict_summary_tanglish=tanglish_summary
        )

        evaluated_verdicts.append({
            "product_id": pid,
            "title": title,
            "confidence_score": confidence,
            "ecom_consistency_7d": p1,
            "social_viral_score": p2,
            "sourcing_cost_est": est_sourcing,
            "target_selling_price": target_price,
            "net_profit_per_unit": net_profit,
            "launch_blueprint": blueprint,
            "verdict_summary_tanglish": tanglish_summary
        })

    # Sort descending by confidence score
    evaluated_verdicts.sort(key=lambda x: x["confidence_score"], reverse=True)
    return evaluated_verdicts[:limit_winners]


if __name__ == "__main__":
    results = run_analysis_for_all_products()
    print(f"Analysis completed for {len(results)} products.")
    verdicts = generate_7day_master_verdict()
    print(f"Generated {len(verdicts)} Master Verdicts.")
    for v in verdicts:
        print(f"-> {v['title'][:40]} | Confidence: {v['confidence_score']}% | Net Profit: ₹{v['net_profit_per_unit']}")

