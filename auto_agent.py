"""
auto_agent.py - 100% Fully Autonomous Background Agent Loop & Scheduler
"The Logic Inside Your Agent" on Auto-Pilot

Autonomous Cycle:
1. Runs scraper.py to scan fresh ₹100–₹1,000 products from Amazon India & Meesho.
2. Updates daily metrics snapshots in storage.py (products_history.db).
3. Executes analyzer.py (Rule-Based + Gemini 2.5 Flash) on products.
4. Auto-adds winning products (sellability_score >= 80 and website_ready == True) to storefront_shortlist.
5. Logs execution stats & details to agent_logs table in SQLite.
6. Sends automatic WhatsApp Web / Mobile Push alerts for newly discovered winners.
"""

import os
import sys
import time
import json
import logging
import argparse
import threading
import urllib.parse
import webbrowser
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
import requests
from dotenv import load_dotenv

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from storage import (
    init_db,
    log_agent_run,
    get_agent_logs,
    get_last_agent_run,
    get_all_products_with_latest_data,
    add_to_shortlist,
    get_shortlist
)
from scraper import run_full_scan
from analyzer import run_analysis_for_all_products, generate_7day_master_verdict

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [AutoAgent] %(message)s"
)
logger = logging.getLogger("AutoAgent")

# Directory for Playwright persistent WhatsApp session
WHATSAPP_SESSION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "whatsapp_session")

# Global Background Scheduler State
_SCHEDULER_LOCK = threading.Lock()
_GLOBAL_SCHEDULER: Optional[BackgroundScheduler] = None
_IS_RUNNING = False
_LAST_RUN_TIME: Optional[str] = None
_NEXT_RUN_TIME: Optional[str] = None
_CURRENT_INTERVAL_MINUTES = 5


def generate_wa_me_link(phone: str, message: str) -> str:
    """Generates direct 1-click wa.me link with pre-filled message (Zero API key needed)."""
    clean_phone = "".join(c for c in str(phone) if c.isdigit())
    encoded_text = urllib.parse.quote(message)
    return f"https://wa.me/{clean_phone}?text={encoded_text}"


def open_whatsapp_in_browser(phone: str, message: str) -> str:
    """Opens WhatsApp Web/Desktop in default browser with pre-filled message."""
    link = generate_wa_me_link(phone, message)
    try:
        webbrowser.open(link)
    except Exception as e:
        logger.warning(f"Could not open browser automatically: {e}")
    return link


def is_whatsapp_linked() -> tuple[bool, str]:
    """
    Checks whether a verified WhatsApp Web session exists in ./whatsapp_session.
    Returns (is_linked: bool, status_description: str).
    """
    session_dir = WHATSAPP_SESSION_DIR
    if not os.path.exists(session_dir):
        return False, "Session folder not created yet"

    marker_file = os.path.join(session_dir, "linked.json")
    if os.path.exists(marker_file):
        try:
            with open(marker_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            linked_time = data.get("linked_at", "Saved")
            return True, f"Linked & Active ({linked_time})"
        except Exception:
            return True, "Linked & Active"

    # Secondary check: inspect Chromium Default profile for WhatsApp IndexedDB / cookies
    default_dir = os.path.join(session_dir, "Default")
    if os.path.exists(default_dir):
        idb_dir = os.path.join(default_dir, "IndexedDB")
        if os.path.exists(idb_dir):
            try:
                entries = os.listdir(idb_dir)
                if any("whatsapp" in e.lower() for e in entries):
                    return True, "Linked session detected"
            except Exception:
                pass

    return False, "Not linked yet"


def launch_whatsapp_qr_linking(timeout_seconds: int = 180) -> tuple[bool, str]:
    """
    Launches a visible Playwright Chromium browser pointing to https://web.whatsapp.com
    using ./whatsapp_session user data dir so the user scans their WhatsApp QR code once.
    Detects successful login, records session metadata, and closes safely.
    """
    os.makedirs(WHATSAPP_SESSION_DIR, exist_ok=True)
    logger.info(f"Opening visible Chromium for WhatsApp Web QR linking. Session dir: {WHATSAPP_SESSION_DIR}")

    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=WHATSAPP_SESSION_DIR,
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox"
                ],
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page = browser.pages[0] if browser.pages else browser.new_page()
            page.goto("https://web.whatsapp.com", wait_until="domcontentloaded", timeout=60000)

            print("\n" + "=" * 60)
            print("  WhatsApp Web QR Linking Window Opened!")
            print("  1. Open WhatsApp on your phone.")
            print("  2. Go to Settings / Menu -> Linked Devices -> Link a Device.")
            print("  3. Point your camera at the QR code on the browser screen.")
            print("=" * 60 + "\n")

            start_t = time.time()
            logged_in = False
            while time.time() - start_t < timeout_seconds:
                try:
                    # Selectors indicating user is authenticated into WhatsApp Web
                    selectors = [
                        '#pane-side',
                        '[data-testid="chat-list"]',
                        '[aria-label="Chat list"]',
                        'div[contenteditable="true"][data-tab="3"]'
                    ]
                    for sel in selectors:
                        loc = page.locator(sel)
                        if loc.count() > 0 and loc.first.is_visible():
                            logged_in = True
                            break
                    if logged_in:
                        break
                    page.wait_for_timeout(1000)
                except Exception as ex:
                    # If user closed the window manually
                    if "closed" in str(ex).lower():
                        break
                    time.sleep(1)

            if logged_in:
                marker_file = os.path.join(WHATSAPP_SESSION_DIR, "linked.json")
                with open(marker_file, "w", encoding="utf-8") as f:
                    json.dump({
                        "linked": True,
                        "linked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }, f)
                logger.info("WhatsApp Web session successfully authenticated and saved!")
                page.wait_for_timeout(3000)
                try:
                    browser.close()
                except Exception:
                    pass
                return True, "WhatsApp Web successfully linked and saved to ./whatsapp_session!"
            else:
                try:
                    browser.close()
                except Exception:
                    pass
                return False, "WhatsApp Web linking window was closed or timed out before QR scan completed."

    except Exception as e:
        err_msg = str(e)
        logger.error(f"launch_whatsapp_qr_linking error: {err_msg}")
        if "Process singleton" in err_msg or "EBUSY" in err_msg:
            return False, "WhatsApp session directory is currently in use by another browser process. Please close it first."
        return False, f"Failed to open WhatsApp QR window: {err_msg}"


def send_whatsapp_web_auto(phone: str, message: str, timeout_seconds: int = 45) -> tuple[bool, str]:
    """
    Sends WhatsApp message 100% automatically using the saved persistent WhatsApp Web session in ./whatsapp_session.
    Opens the chat with pre-filled message, triggers the send action, and waits for socket delivery.
    Zero API keys, zero CallMeBot, zero costs.
    """
    clean_phone = "".join(c for c in str(phone) if c.isdigit())
    if not clean_phone:
        return False, "No destination phone number provided."

    os.makedirs(WHATSAPP_SESSION_DIR, exist_ok=True)
    is_linked, _ = is_whatsapp_linked()
    if not is_linked:
        return False, "WhatsApp Web is not linked yet. Click '🔗 Step 1: Link WhatsApp QR (One-Time Setup)' first."

    from playwright.sync_api import sync_playwright

    encoded_msg = urllib.parse.quote(message)
    target_url = f"https://web.whatsapp.com/send?phone={clean_phone}&text={encoded_msg}"
    logger.info(f"Opening WhatsApp Web auto-sender for +{clean_phone}...")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=WHATSAPP_SESSION_DIR,
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox"
                ],
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page = browser.pages[0] if browser.pages else browser.new_page()
            page.goto(target_url, wait_until="domcontentloaded", timeout=timeout_seconds * 1000)

            # Check if session got disconnected (QR code appears)
            try:
                qr = page.locator('canvas[aria-label="Scan me!"], div[data-ref]')
                if qr.count() > 0 and qr.first.is_visible():
                    browser.close()
                    marker_file = os.path.join(WHATSAPP_SESSION_DIR, "linked.json")
                    if os.path.exists(marker_file):
                        try:
                            os.remove(marker_file)
                        except Exception:
                            pass
                    return False, "WhatsApp session disconnected or expired. Please re-scan QR via '🔗 Step 1: Link WhatsApp QR'."
            except Exception:
                pass

            # Try locating send button or pressing Enter
            sent = False
            start_wait = time.time()
            while time.time() - start_wait < 25:
                # 1. Primary: send button
                send_selectors = [
                    'button[data-testid="compose-btn-send"]',
                    'span[data-icon="send"]',
                    'button[aria-label="Send"]'
                ]
                for s in send_selectors:
                    btn = page.locator(s)
                    if btn.count() > 0 and btn.first.is_visible():
                        btn.first.click()
                        sent = True
                        logger.info("Clicked WhatsApp Web send button.")
                        break
                if sent:
                    break

                # 2. Fallback: message box Enter key
                msg_box = page.locator('footer div[contenteditable="true"]').first
                if msg_box.count() > 0 and msg_box.is_visible():
                    msg_box.focus()
                    msg_box.press("Enter")
                    sent = True
                    logger.info("Sent WhatsApp message via Enter key.")
                    break

                page.wait_for_timeout(1000)

            if not sent:
                # Check for invalid phone popup
                invalid_popup = page.locator('div:has-text("Phone number shared via url is invalid")')
                if invalid_popup.count() > 0 and invalid_popup.first.is_visible():
                    browser.close()
                    return False, f"WhatsApp says phone number +{clean_phone} is invalid or not registered."
                browser.close()
                return False, "WhatsApp Web chat opened but send button was not ready within 25 seconds."

            # Wait 4 seconds for message socket delivery
            page.wait_for_timeout(4000)
            browser.close()
            logger.info(f"WhatsApp Web message automatically sent to +{clean_phone}!")
            return True, f"WhatsApp Web: Message sent automatically to +{clean_phone}!"

    except Exception as e:
        err_str = str(e)
        logger.error(f"WhatsApp Web auto-send error: {err_str}")
        if "Process singleton" in err_str or "EBUSY" in err_str or "Target page, context or browser has been closed" in err_str:
            return False, "WhatsApp session folder is currently locked by another browser window. Please close any open Chrome/Playwright windows."
        return False, f"WhatsApp Web error: {err_str}"


def send_ntfy_push(
    topic: str,
    title: str,
    message: str,
    click_url: Optional[str] = None
) -> tuple[bool, str]:
    """
    Sends instant mobile push notification via Ntfy.sh (Zero API key, zero registration).
    Uses JSON payload (requests.post("https://ntfy.sh", json={...})) so emojis (🚀, ₹)
    never fail with latin-1 codec errors.
    """
    clean_topic = topic.strip().replace(" ", "_")
    if not clean_topic:
        return False, "Ntfy topic name is empty."

    payload = {
        "topic": clean_topic,
        "title": title,
        "message": message,
        "priority": 4,
        "tags": ["rocket", "shopping_cart", "moneybag"]
    }
    if click_url:
        payload["click"] = click_url

    try:
        resp = requests.post(
            "https://ntfy.sh",
            json=payload,
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=10
        )
        if resp.status_code == 200:
            logger.info(f"Ntfy push sent successfully to topic '{clean_topic}'.")
            return True, f"Push sent to ntfy.sh/{clean_topic}"
        else:
            return False, f"Ntfy returned HTTP {resp.status_code}: {resp.text[:100]}"
    except Exception as e:
        return False, f"Ntfy error: {str(e)}"


def send_green_api_whatsapp(
    instance_id: str,
    api_token: str,
    phone: str,
    message: str
) -> tuple[bool, str]:
    """Sends WhatsApp message via Green-API."""
    clean_phone = "".join(c for c in str(phone) if c.isdigit())
    if not clean_phone or not instance_id or not api_token:
        return False, "Green-API instance_id, token, and phone are required."

    url = f"https://api.green-api.com/waInstance{instance_id}/sendMessage/{api_token}"
    payload = {
        "chatId": f"{clean_phone}@c.us",
        "message": message
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            return True, f"Green-API message sent to +{clean_phone}"
        else:
            return False, f"Green-API returned HTTP {resp.status_code}: {resp.text[:100]}"
    except Exception as e:
        return False, f"Green-API error: {str(e)}"


def send_whatsapp_alert(
    message: str,
    phone: Optional[str] = None,
    api_key: Optional[str] = None,
    ntfy_topic: Optional[str] = None,
    green_instance: Optional[str] = None,
    green_token: Optional[str] = None,
    auto_open_browser: bool = False
) -> tuple[bool, str, str]:
    """
    Multi-channel alert dispatcher supporting:
    - Mode 0: 100% Keyless Automatic WhatsApp Web (Playwright persistent session in ./whatsapp_session)
    - Mode 1: Direct WhatsApp wa.me 1-click link (fallback)
    - Mode 2: Free Ntfy.sh zero-config mobile push
    - Mode 3: Green-API / CallMeBot / Meta WhatsApp API
    Returns (success: bool, status_message: str, wa_me_link: str).
    """
    wa_phone = phone or os.getenv("WHATSAPP_PHONE", "").strip()
    wa_key = api_key or os.getenv("WHATSAPP_API_KEY", "").strip()
    topic = ntfy_topic or os.getenv("NTFY_TOPIC", "").strip()
    g_instance = green_instance or os.getenv("GREEN_API_INSTANCE_ID", "").strip()
    g_token = green_token or os.getenv("GREEN_API_TOKEN", "").strip()

    clean_p = "".join(c for c in wa_phone if c.isdigit())
    wa_link = generate_wa_me_link(clean_p, message) if clean_p else ""

    if auto_open_browser and clean_p:
        open_whatsapp_in_browser(clean_p, message)

    results = []
    any_success = False

    # Channel 0: Automatic WhatsApp Web (Persistent Browser Session)
    if clean_p:
        is_linked, _ = is_whatsapp_linked()
        if is_linked:
            w_ok, w_msg = send_whatsapp_web_auto(clean_p, message)
            results.append(w_msg)
            if w_ok:
                any_success = True

    # Channel 1: Free Ntfy.sh Mobile Push
    if topic:
        n_ok, n_msg = send_ntfy_push(
            topic=topic,
            title="🚀 The Logic Inside Your Agent Alert",
            message=message,
            click_url=wa_link or "https://share.streamlit.io"
        )
        results.append(f"Ntfy: {n_msg}")
        if n_ok:
            any_success = True

    # Channel 2: Green-API
    if g_instance and g_token and clean_p:
        g_ok, g_msg = send_green_api_whatsapp(g_instance, g_token, clean_p, message)
        results.append(f"Green-API: {g_msg}")
        if g_ok:
            any_success = True

    # Channel 3: CallMeBot Free API
    if clean_p:
        if wa_key:
            try:
                url = "https://api.callmebot.com/whatsapp.php"
                resp = requests.get(url, params={"phone": clean_p, "text": message, "apikey": wa_key}, timeout=15)
                if resp.status_code == 200 and ("error" not in resp.text.lower() or "queued" in resp.text.lower()):
                    results.append(f"CallMeBot: Sent to +{clean_p}")
                    any_success = True
                else:
                    results.append(f"CallMeBot: Error ({resp.status_code})")
            except Exception as e:
                results.append(f"CallMeBot: {str(e)}")
        else:
            results.append("CallMeBot: Skipped (API Key is empty. Click 'Link WhatsApp QR' or use Ntfy/Green-API)")

    # Channel 4: Meta WhatsApp Cloud API Fallback
    meta_token = os.getenv("META_WHATSAPP_TOKEN", "").strip()
    meta_phone_id = os.getenv("META_PHONE_NUMBER_ID", "").strip()
    to_phone = os.getenv("WHATSAPP_TO_PHONE", "").strip()
    if meta_token and meta_phone_id and to_phone:
        try:
            url = f"https://graph.facebook.com/v19.0/{meta_phone_id}/messages"
            headers = {"Authorization": f"Bearer {meta_token}", "Content-Type": "application/json"}
            payload = {
                "messaging_product": "whatsapp",
                "to": "".join(c for c in to_phone if c.isdigit()),
                "type": "text",
                "text": {"body": message}
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=15)
            if resp.status_code in [200, 201]:
                results.append("Meta API: Sent")
                any_success = True
            else:
                results.append(f"Meta API: Error ({resp.status_code})")
        except Exception as e:
            results.append(f"Meta API: {str(e)}")

    if any_success:
        status_msg = " | ".join(results)
        return True, status_msg, wa_link
    elif wa_link:
        status_msg = " | ".join(results) if results else "Direct WhatsApp 1-Click Link Generated."
        return True, status_msg, wa_link
    else:
        return False, "No phone number or alert channel configured. Enter your mobile number in the sidebar.", ""


def test_whatsapp_connection(
    phone: Optional[str] = None,
    api_key: Optional[str] = None,
    ntfy_topic: Optional[str] = None,
    green_instance: Optional[str] = None,
    green_token: Optional[str] = None,
    auto_open_browser: bool = False
) -> tuple[bool, str, str]:
    """Sends a verification message to test alert delivery across all configured channels."""
    test_msg = (
        "🚀 *The Logic Inside Your Agent*\n"
        "✅ *Alert System Test Successful!*\n\n"
        "Your autonomous Indian E-commerce hunter is active. You will receive real-time alerts "
        "whenever high-margin winning products (₹100–₹1,000) are auto-shortlisted."
    )
    return send_whatsapp_alert(
        test_msg,
        phone=phone,
        api_key=api_key,
        ntfy_topic=ntfy_topic,
        green_instance=green_instance,
        green_token=green_token,
        auto_open_browser=auto_open_browser
    )


def run_autonomous_cycle(api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Executes one complete end-to-end autonomous cycle:
    Scrape -> Store -> Analyze -> Auto-Shortlist -> Log -> Multi-Channel Alert
    """
    global _LAST_RUN_TIME
    start_time = datetime.now()
    start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
    _LAST_RUN_TIME = start_str
    logger.info(f"🚀 Starting Autonomous Cycle at {start_str}...")

    init_db()

    scraped_count = 0
    analyzed_count = 0
    auto_shortlisted_count = 0
    summary = ""
    details_dict = {}

    try:
        # Step 1 & 2: Scrape & Store
        logger.info("Step 1: Scraping fresh market listings (₹100 - ₹1000)...")
        scraped_items = run_full_scan(
            search_queries=["trending gadgets under 1000", "kitchen tools under 500", "impulse buy items under 800"],
            allow_simulation_fallback=True
        )
        scraped_count = len(scraped_items)
        logger.info(f"Captured {scraped_count} product metrics.")

        # Step 3: Run AI Analysis
        logger.info("Step 2: Executing AI Brain Analysis...")
        analysis_results = run_analysis_for_all_products(api_key=api_key)
        analyzed_count = len(analysis_results)
        logger.info(f"Evaluated {analyzed_count} products.")

        # Step 3b: Compute 7-Day Omni-Channel Master Launch Verdicts (99% Confidence)
        logger.info("Step 3b: Synthesizing 7-Day Omni-Channel Master Launch Verdicts...")
        master_verdicts = []
        try:
            master_verdicts = generate_7day_master_verdict(api_key=api_key, limit_winners=3)
            logger.info(f"Synthesized {len(master_verdicts)} 7-day master launch verdicts.")
        except Exception as mv_err:
            logger.warning(f"7-day master verdict synthesis warning: {mv_err}")

        # Step 4: Auto-shortlist winners (sellability_score >= 80 and website_ready == True)
        logger.info("Step 4: Checking for Auto-Shortlist qualification (Score >= 80 & Website Ready)...")
        current_products = get_all_products_with_latest_data()
        auto_shortlisted_items = []

        for p in current_products:
            score = int(p.get("sellability_score") or 0)
            is_ready = bool(p.get("website_ready"))
            is_already_shortlisted = bool(p.get("is_shortlisted"))

            if score >= 80 and is_ready and not is_already_shortlisted:
                rec_price = p.get("recommended_selling_price") or (p.get("price", 0) * 1.5)
                note_str = f"Auto-Shortlisted by AI Agent on {start_str} (Score: {score}/100)"
                add_to_shortlist(
                    product_id=p["product_id"],
                    custom_selling_price=rec_price,
                    notes=note_str
                )
                auto_shortlisted_count += 1
                auto_shortlisted_items.append({
                    "title": p.get("title"),
                    "price": p.get("price"),
                    "recommended_price": rec_price,
                    "score": score,
                    "summary_tanglish": p.get("ai_summary_tamil_english")
                })

        summary = f"Cycle finished: {scraped_count} scanned, {analyzed_count} analyzed, {len(master_verdicts)} 7-day verdicts, {auto_shortlisted_count} auto-shortlisted winners."
        logger.info(summary)

        details_dict = {
            "scraped_count": scraped_count,
            "analyzed_count": analyzed_count,
            "master_verdicts_count": len(master_verdicts),
            "auto_shortlisted": auto_shortlisted_items,
            "duration_seconds": round((datetime.now() - start_time).total_seconds(), 2)
        }

        # Step 5: Log to SQLite
        log_agent_run(
            status="SUCCESS",
            scraped_count=scraped_count,
            analyzed_count=analyzed_count,
            auto_shortlisted_count=auto_shortlisted_count,
            summary=summary,
            details=json.dumps(details_dict),
            timestamp=start_str
        )

        # Step 6: Dispatch Alerts for new winners & #1 Launch Recommendation
        if auto_shortlisted_count > 0 or master_verdicts:
            top_winner = master_verdicts[0] if master_verdicts else None
            wa_msg = (
                f"🚀 *The Logic Inside Your Agent — Auto-Pilot Alert!*\n\n"
                f"🎯 Focus: ₹100–₹1,000 Sweet Spot (Amazon & Meesho)\n"
                f"📅 Time: `{start_str}`\n\n"
            )
            if top_winner:
                wa_msg += (
                    f"🏆 *#1 7-DAY MASTER LAUNCH WINNER ({top_winner['confidence_score']:.1f}% Confidence):*\n"
                    f"📦 *Product:* {top_winner['title']}\n"
                    f"💰 Sourcing: ₹{top_winner['sourcing_cost_est']:.0f} | 🎯 Website Price: ₹{top_winner['target_selling_price']:.0f}\n"
                    f"💵 Net Profit: ₹{top_winner['net_profit_per_unit']:.0f}/unit\n"
                    f"🗣️ *Hook:* _{top_winner['launch_blueprint'].get('ad_hook_tanglish', '')[:100]}_\n\n"
                )
            if auto_shortlisted_count > 0:
                wa_msg += f"🔥 *{auto_shortlisted_count} New Winning Product(s) Shortlisted:*\n"
                for item in auto_shortlisted_items[:2]:
                    wa_msg += (
                        f"-----------------------------\n"
                        f"📦 *Product:* {item['title'][:50]}\n"
                        f"💰 Market: ₹{item['price']:.0f} | 🎯 Target: ₹{item['recommended_price']:.0f} | Score: `{item['score']}/100`\n"
                    )
            wa_msg += (
                f"-----------------------------\n"
                f"👉 Open your Streamlit Dashboard (Tab 1: 🏆 7-Day Master Verdict) to launch now!"
            )
            send_whatsapp_alert(wa_msg)

        return {
            "status": "SUCCESS",
            "timestamp": start_str,
            "scraped_count": scraped_count,
            "analyzed_count": analyzed_count,
            "auto_shortlisted_count": auto_shortlisted_count,
            "summary": summary
        }

    except Exception as e:
        error_msg = f"Autonomous Cycle failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        log_agent_run(
            status="ERROR",
            scraped_count=scraped_count,
            analyzed_count=analyzed_count,
            auto_shortlisted_count=auto_shortlisted_count,
            summary=error_msg,
            details=json.dumps({"error": str(e)}),
            timestamp=start_str
        )
        return {
            "status": "ERROR",
            "timestamp": start_str,
            "error": str(e)
        }


def get_apscheduler() -> BackgroundScheduler:
    """Returns singleton BackgroundScheduler."""
    global _GLOBAL_SCHEDULER
    with _SCHEDULER_LOCK:
        if _GLOBAL_SCHEDULER is None:
            _GLOBAL_SCHEDULER = BackgroundScheduler(daemon=True)
            _GLOBAL_SCHEDULER.start()
        elif not _GLOBAL_SCHEDULER.running:
            _GLOBAL_SCHEDULER.start()
        return _GLOBAL_SCHEDULER


def start_background_scheduler(interval_minutes: int = 5, api_key: Optional[str] = None) -> bool:
    """Starts the autonomous scheduler using APScheduler BackgroundScheduler."""
    global _CURRENT_INTERVAL_MINUTES, _IS_RUNNING, _NEXT_RUN_TIME
    sched = get_apscheduler()
    _CURRENT_INTERVAL_MINUTES = interval_minutes

    def _job_wrapper():
        global _LAST_RUN_TIME, _NEXT_RUN_TIME
        _LAST_RUN_TIME = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        run_autonomous_cycle(api_key=api_key)
        job = sched.get_job("auto_agent_cycle")
        if job and job.next_run_time:
            _NEXT_RUN_TIME = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")

    sched.add_job(
        _job_wrapper,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="auto_agent_cycle",
        name="Auto-Pilot Cycle",
        replace_existing=True,
        max_instances=1,
        coalesce=True
    )
    _IS_RUNNING = True
    job = sched.get_job("auto_agent_cycle")
    if job and job.next_run_time:
        _NEXT_RUN_TIME = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"Autonomous APScheduler activated with {interval_minutes} minute intervals.")
    return True


def stop_background_scheduler() -> bool:
    """Stops the autonomous background scheduler job."""
    global _IS_RUNNING, _NEXT_RUN_TIME
    sched = get_apscheduler()
    job = sched.get_job("auto_agent_cycle")
    if job:
        try:
            sched.remove_job("auto_agent_cycle")
        except Exception:
            pass
    _IS_RUNNING = False
    _NEXT_RUN_TIME = "Stopped"
    logger.info("Autonomous APScheduler stopped.")
    return True


def is_scheduler_running() -> bool:
    sched = get_apscheduler()
    job = sched.get_job("auto_agent_cycle")
    return sched.running and job is not None and job.next_run_time is not None


def get_scheduler_status() -> Dict[str, Any]:
    sched = get_apscheduler()
    job = sched.get_job("auto_agent_cycle")
    running = sched.running and (job is not None and job.next_run_time is not None)
    next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if (job and job.next_run_time) else "Stopped"
    last_log = get_last_agent_run()
    return {
        "is_active": running,
        "interval_minutes": _CURRENT_INTERVAL_MINUTES,
        "last_run": _LAST_RUN_TIME or (last_log["timestamp"] if last_log else "None"),
        "next_run": next_run if running else "Stopped",
        "last_summary": last_log["summary"] if last_log else "No runs yet",
        "last_status": last_log["status"] if last_log else "IDLE"
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run The Logic Inside Your Agent in 100% Autonomous Mode.")
    parser.add_argument("--once", action="store_true", help="Execute single autonomous cycle and exit.")
    parser.add_argument("--test-5min", action="store_true", help="Run background loop every 5 minutes.")
    parser.add_argument("--interval-minutes", type=int, default=240, help="Run interval in minutes (default 240 = 4 hours).")
    parser.add_argument("--interval-hours", type=float, default=None, help="Run interval in hours.")
    parser.add_argument("--link-whatsapp", action="store_true", help="Open visible Chromium window to scan WhatsApp Web QR code once.")
    parser.add_argument("--test-whatsapp", action="store_true", help="Send a test message across all configured channels.")
    parser.add_argument("--timeout", type=int, default=180, help="Timeout in seconds for WhatsApp QR window.")

    args = parser.parse_args()

    if args.link_whatsapp:
        print("Opening visible WhatsApp Web QR linking window...")
        ok, msg = launch_whatsapp_qr_linking(timeout_seconds=args.timeout)
        print("Status:", msg)
        sys.exit(0 if ok else 1)

    if args.test_whatsapp:
        print("Dispatching test alert across configured notification channels...")
        ok, msg, link = test_whatsapp_connection()
        print(f"Result: {ok}")
        print(f"Status: {msg}")
        if link:
            print(f"Direct WhatsApp Link: {link}")
        sys.exit(0 if ok else 1)

    if args.once:
        print("Running single autonomous cycle...")
        result = run_autonomous_cycle()
        print("Result:", result)
        sys.exit(0)

    interval_min = 5 if args.test_5min else (int(args.interval_hours * 60) if args.interval_hours else args.interval_minutes)

    print(f"Starting The Logic Inside Your Agent 24/7 Daemon (Every {interval_min} minutes)...")
    print("Press Ctrl+C to stop.")
    start_background_scheduler(interval_minutes=interval_min)

    # Immediately trigger initial cycle on standalone start
    print("Triggering initial cycle...")
    run_autonomous_cycle()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping agent...")
        stop_background_scheduler()
        print("Agent stopped safely.")
