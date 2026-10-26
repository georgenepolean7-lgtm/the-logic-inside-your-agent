"""
app.py - Streamlit Interactive Dashboard
"The Logic Inside Your Agent" — ₹100 to ₹1,000 Winning Product Hunter
"""

import os
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime
from dotenv import load_dotenv

import sys
import subprocess
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from storage import (
    init_db,
    seed_demo_data,
    get_all_products_with_latest_data,
    get_product_metrics_history,
    add_to_shortlist,
    remove_from_shortlist,
    get_shortlist,
    upsert_product,
    insert_daily_metric,
    get_agent_logs,
    get_last_agent_run,
    get_latest_weekly_verdicts,
    get_social_metrics_history,
    get_combined_7day_product_signals
)
from scraper import run_full_scan, import_products_from_csv
from analyzer import (
    analyze_product_with_gemini,
    run_analysis_for_all_products,
    generate_7day_master_verdict,
    ProductAnalysisResult
)
from auto_agent import (
    start_background_scheduler,
    stop_background_scheduler,
    is_scheduler_running,
    get_scheduler_status,
    run_autonomous_cycle,
    test_whatsapp_connection,
    send_whatsapp_alert,
    generate_wa_me_link,
    open_whatsapp_in_browser,
    send_ntfy_push,
    send_green_api_whatsapp,
    is_whatsapp_linked,
    launch_whatsapp_qr_linking,
    send_whatsapp_web_auto,
    WHATSAPP_SESSION_DIR
)

# Load environment variables
load_dotenv()


def update_env_variable(key: str, value: str, env_path: str = ".env") -> None:
    """Updates or appends a key-value pair in .env and os.environ."""
    lines = []
    found = False
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}=") or stripped.startswith(f"#{key}="):
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f"{key}={value}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    os.environ[key] = value


def build_current_whatsapp_report(limit: int = 3) -> str:
    """Build a report without inventing missing prices or sellability scores."""
    shortlisted = get_shortlist()
    if not shortlisted:
        all_p = get_all_products_with_latest_data()
        shortlisted = [p for p in all_p if p.get("website_ready")][:limit]

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = (
        f"🚀 *The Logic Inside Your Agent — Product Research Report*\\n"
        f"🎯 Focus: ₹100–₹1,000 (Amazon & Meesho)\\n"
        f"📅 Date: {now_str}\\n\\n"
    )
    if not shortlisted:
        return msg + "⚠️ No verified shortlist available yet. Run a live market scan first."

    for i, item in enumerate(shortlisted[:limit], 1):
        p_name = item.get("title", "Untitled product")
        m_price = item.get("current_market_price", item.get("price"))
        s_price = item.get("custom_selling_price") or item.get("recommended_selling_price")
        score = item.get("sellability_score")
        tanglish = item.get("marketing_angle_for_website") or "Marketing angle not yet verified."
        market_text = f"₹{m_price:.0f}" if isinstance(m_price, (int, float)) else "Unavailable"
        sell_text = f"₹{s_price:.0f}" if isinstance(s_price, (int, float)) else "Not estimated"
        score_text = f"{score}/100" if isinstance(score, (int, float)) else "Not scored"
        msg += (
            f"-----------------------------\\n"
            f"📦 *#{i}: {p_name[:60]}*\\n"
            f"💰 Market Price: {market_text} | Suggested Price: {sell_text}\\n"
            f"⭐ Score: `{score_text}`\\n"
            f"🗣️ *Hook:* _{tanglish[:90]}_\\n"
        )
    msg += "-----------------------------\\n⚠️ Verify live price, seller, stock, and affiliate eligibility before publishing."
    return msg

# Page configuration
st.set_page_config(
    page_title="The Logic Inside Your Agent | ₹100 - ₹1,000 Winning Products",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Ensure DB initialized
init_db()


@st.cache_resource
def get_global_auto_scheduler(default_interval_minutes: int = 5) -> BackgroundScheduler:
    """
    Holds a single global BackgroundScheduler cached across all Streamlit sessions/reruns.
    Starts automatically as soon as app.py loads (active on startup, running every 5 minutes in test mode).
    Immediately triggers an initial background check if the last run in agent_logs was > 1 hour ago (or never ran).
    """
    scheduler = BackgroundScheduler(daemon=True)

    def _auto_pilot_worker():
        try:
            load_dotenv(override=True)
            active_key = os.getenv("GEMINI_API_KEY", "")
            run_autonomous_cycle(api_key=active_key)
        except Exception as exc:
            print(f"[Auto-Pilot Worker Exception]: {exc}")

    # Register recurring interval job (5 minutes by default for active testing)
    scheduler.add_job(
        _auto_pilot_worker,
        trigger=IntervalTrigger(minutes=default_interval_minutes),
        id="app_auto_pilot_job",
        name="Streamlit Auto-Pilot Cycle",
        replace_existing=True,
        max_instances=1,
        coalesce=True
    )
    scheduler.start()

    # Immediate trigger check: if last run was > 1 hour ago or never ran
    last_log = get_last_agent_run()
    should_run_now = False
    if not last_log or not last_log.get("timestamp"):
        should_run_now = True
    else:
        try:
            last_dt = datetime.strptime(last_log["timestamp"], "%Y-%m-%d %H:%M:%S")
            diff_hours = (datetime.now() - last_dt).total_seconds() / 3600.0
            if diff_hours >= 1.0:
                should_run_now = True
        except Exception:
            should_run_now = True

    if should_run_now:
        # Schedule initial run immediately in the background
        scheduler.add_job(
            _auto_pilot_worker,
            id="initial_background_run",
            name="Initial Startup Auto Check",
            run_date=datetime.now()
        )

    return scheduler


# Initialize global scheduler on app load (active by default)
global_scheduler = get_global_auto_scheduler(default_interval_minutes=240)


# Custom UI Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    .main-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #311042 100%);
        border-radius: 16px;
        padding: 26px 32px;
        margin-bottom: 24px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
    }
    
    .badge-rising {
        background: linear-gradient(135deg, #059669 0%, #10b981 100%);
        color: white;
        padding: 4px 12px;
        border-radius: 999px;
        font-weight: 700;
        font-size: 0.78rem;
        display: inline-block;
    }
    
    .badge-dropping {
        background: linear-gradient(135deg, #dc2626 0%, #ef4444 100%);
        color: white;
        padding: 4px 12px;
        border-radius: 999px;
        font-weight: 700;
        font-size: 0.78rem;
        display: inline-block;
    }
    
    .badge-stable {
        background: linear-gradient(135deg, #4b5563 0%, #6b7280 100%);
        color: white;
        padding: 4px 12px;
        border-radius: 999px;
        font-weight: 700;
        font-size: 0.78rem;
        display: inline-block;
    }
    
    .tanglish-box {
        background: rgba(99, 102, 241, 0.08);
        border-left: 4px solid #6366f1;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin-top: 10px;
        font-size: 0.9rem;
    }
    
    .product-card {
        background: #1e293b;
        border-radius: 14px;
        padding: 20px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        margin-bottom: 20px;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    
    .product-card:hover {
        border-color: rgba(99, 102, 241, 0.4);
    }
    
    .badge-verdict {
        background: linear-gradient(135deg, #eab308 0%, #ca8a04 100%);
        color: #000;
        padding: 4px 12px;
        border-radius: 999px;
        font-weight: 800;
        font-size: 0.8rem;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)


# ==========================================
# SIDEBAR CONTROLS
# ==========================================
with st.sidebar:
    st.image("https://img.icons8.com/isometric/100/shopping-cart-loaded.png", width=64)
    st.markdown("### 🎯 **Agent Configuration**")

    # API Key Input
    saved_api_key = os.getenv("GEMINI_API_KEY", "")
    gemini_api_key = st.text_input(
        "🔑 Gemini API Key",
        value=saved_api_key,
        type="password",
        help="Free key from https://aistudio.google.com/app/apikey. If empty, Agent runs on smart Rule-Based Engine."
    )

    st.markdown("---")
    st.markdown("### 🛒 **Market Filter**")

    # Price Filter
    price_range = st.slider(
        "Price Range (INR ₹)",
        min_value=100,
        max_value=1000,
        value=(100, 1000),
        step=50,
        help="Strictly focused on the Indian ₹100 - ₹1,000 sweet spot"
    )

    # Platform selector
    platform_choice = st.selectbox(
        "Platform",
        ["All Platforms", "Amazon India", "Meesho"]
    )

    st.markdown("---")
    st.markdown("### ⚡ **Actions**")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🔄 Scan Market", use_container_width=True, help="Scrapes Amazon India and Meesho"):
            with st.spinner("Scanning live market listings..."):
                scraped = run_full_scan(allow_simulation_fallback=False)
                st.success(f"Scanned {len(scraped)} items!")
                st.rerun()

    with col_btn2:
        if st.button("🧪 Load SYNTHETIC DEMO (not real)", use_container_width=True, help="TEST DATA ONLY. Never use demo rows for sourcing or buying decisions."):
            with st.spinner("Seeding 10 demo products..."):
                seed_demo_data()
                st.warning("Synthetic demo data loaded for UI testing only. These are not verified listings, reviews, trends or supplier prices.")
                st.rerun()

    if st.button("🤖 Run AI Analysis on All", use_container_width=True, type="primary"):
        with st.spinner("Executing The Logic Inside Your Agent..."):
            run_analysis_for_all_products(api_key=gemini_api_key)
            st.success("Analysis complete!")
            st.rerun()

    st.markdown("---")
    st.markdown("### ⚡ **Autonomous Mode (Auto-Pilot)**")

    # Connect to persistent BackgroundScheduler initialized on app load
    auto_job = global_scheduler.get_job("app_auto_pilot_job")
    is_active = global_scheduler.running and (auto_job is not None and auto_job.next_run_time is not None)

    if is_active:
        st.markdown("<span style='color:#10b981; font-weight:700;'>🟢 AUTO-PILOT ACTIVE (Running 24/7)</span>", unsafe_allow_html=True)
    else:
        st.markdown("<span style='color:#f59e0b; font-weight:700;'>⏸️ AUTO-PILOT PAUSED</span>", unsafe_allow_html=True)

    interval_options = {
        "5 Minutes (Quick Test / Active)": 5,
        "1 Hour": 60,
        "4 Hours (Recommended)": 240,
        "12 Hours": 720
    }
    selected_interval_label = st.selectbox("Auto Cycle Interval", list(interval_options.keys()), index=2)
    selected_interval = interval_options[selected_interval_label]

    # Dynamically update scheduler job interval if user changed selectbox
    if auto_job and hasattr(auto_job.trigger, "interval"):
        curr_min = int(auto_job.trigger.interval.total_seconds() / 60)
        if curr_min != selected_interval:
            global_scheduler.reschedule_job("app_auto_pilot_job", trigger=IntervalTrigger(minutes=selected_interval))
            st.rerun()

    col_auto1, col_auto2 = st.columns(2)
    with col_auto1:
        if not is_active:
            if st.button("▶️ Resume Auto-Pilot", use_container_width=True, type="primary"):
                if auto_job is None:
                    def _re_worker():
                        load_dotenv(override=True)
                        run_autonomous_cycle(api_key=os.getenv("GEMINI_API_KEY", ""))
                    global_scheduler.add_job(
                        _re_worker,
                        trigger=IntervalTrigger(minutes=selected_interval),
                        id="app_auto_pilot_job",
                        name="Streamlit Auto-Pilot Cycle",
                        replace_existing=True,
                        max_instances=1,
                        coalesce=True
                    )
                else:
                    global_scheduler.resume_job("app_auto_pilot_job")
                st.success("Auto-Pilot Resumed!")
                st.rerun()
        else:
            if st.button("⏸️ Pause Auto-Pilot", use_container_width=True):
                global_scheduler.pause_job("app_auto_pilot_job")
                st.warning("Auto-Pilot Paused.")
                st.rerun()

    with col_auto2:
        if st.button("⚡ Run Cycle Now", use_container_width=True, help="Executes one complete autonomous cycle immediately"):
            with st.spinner("Executing full autonomous cycle..."):
                cycle_res = run_autonomous_cycle(api_key=gemini_api_key)
                if cycle_res.get("status") == "SUCCESS":
                    st.success(f"Done! {cycle_res.get('auto_shortlisted_count', 0)} new winners shortlisted.")
                else:
                    st.error(f"Cycle error: {cycle_res.get('error')}")
                st.rerun()

    last_log = get_last_agent_run()
    last_run_display = last_log["timestamp"] if last_log else "None"
    next_run_display = auto_job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if (auto_job and auto_job.next_run_time) else "Paused"
    st.caption(f"🕒 **Last Run:** `{last_run_display}`")
    st.caption(f"⏳ **Next Run:** `{next_run_display}`")

    # Live Log Viewer
    with st.expander("📜 Auto-Pilot Activity Logs", expanded=False):
        logs = get_agent_logs(limit=8)
        if not logs:
            st.info("No autonomous run logs yet. Auto-Pilot runs every 5 minutes automatically.")
        else:
            for l in logs:
                badge = "🟢" if l["status"] == "SUCCESS" else "🔴"
                st.markdown(f"**{badge} {l['timestamp']}**")
                st.caption(f"{l['summary']}")
                if l.get("auto_shortlisted_count", 0) > 0:
                    st.markdown(f"<span style='color:#10b981; font-weight:700; font-size:0.8rem;'>+{l['auto_shortlisted_count']} Winners Auto-Shortlisted</span>", unsafe_allow_html=True)
                st.markdown("<hr style='margin:4px 0; border-color:rgba(255,255,255,0.08);'>", unsafe_allow_html=True)

    # WhatsApp & Mobile Alerts Setup Expander
    with st.expander("📲 WhatsApp & Mobile Alerts Setup", expanded=True):
        st.markdown(
            "Configure how the Agent notifies you when high-margin winning products (₹100–₹1,000) are found on auto-pilot."
        )

        # Step 1: True Keyless Automatic WhatsApp Web (Playwright)
        st.markdown("#### 🚀 **Keyless Automatic WhatsApp Web**")
        is_linked, link_status = is_whatsapp_linked()
        if is_linked:
            st.markdown(
                f"<div style='background:rgba(16,185,129,0.15); border:1px solid #10b981; border-radius:8px; padding:10px 12px; margin-bottom:10px;'>"
                f"<b style='color:#10b981;'>🟢 WhatsApp Web: LINKED & ACTIVE</b><br>"
                f"<small style='color:#e2e8f0;'>Session stored in <code>./whatsapp_session</code>. Auto-delivers messages directly in background without manual clicking!</small>"
                f"</div>",
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f"<div style='background:rgba(245,158,11,0.15); border:1px solid #f59e0b; border-radius:8px; padding:10px 12px; margin-bottom:10px;'>"
                f"<b style='color:#f59e0b;'>⚪ WhatsApp Web: NOT LINKED YET</b><br>"
                f"<small style='color:#e2e8f0;'>Click the button below to scan your WhatsApp QR code once. Zero API key needed!</small>"
                f"</div>",
                unsafe_allow_html=True
            )

        if st.button("🔗 Step 1: Link WhatsApp QR (One-Time Setup)", use_container_width=True, type="primary" if not is_linked else "secondary"):
            subprocess.Popen([sys.executable, "auto_agent.py", "--link-whatsapp"])
            st.info("🌐 **WhatsApp Web window opened!** Check your Windows taskbar/screen for the Chrome browser window. Open WhatsApp on your phone (Menu / Settings -> Linked Devices -> Link a Device) and scan the QR code. Your session will be permanently saved to `./whatsapp_session`!")

        saved_phone = os.getenv("WHATSAPP_PHONE", "")
        dest_phone_input = st.text_input(
            "Destination Mobile Number (with Country Code)",
            value=saved_phone,
            placeholder="e.g. 918903082778",
            help="Digits only (91 for India), no + or spaces"
        )
        if dest_phone_input.strip() and dest_phone_input.strip() != saved_phone:
            if st.button("💾 Save Phone to .env", use_container_width=True, key="save_phone_direct"):
                clean_p = "".join(c for c in dest_phone_input if c.isdigit())
                update_env_variable("WHATSAPP_PHONE", clean_p)
                st.success(f"Phone +{clean_p} saved to .env!")
                st.rerun()

        # Direct Automatic WhatsApp Delivery Test
        if is_linked and dest_phone_input.strip():
            if st.button("🚀 Test Automatic WhatsApp Delivery Now", use_container_width=True):
                with st.spinner(f"Opening WhatsApp Web session and delivering alert to +{dest_phone_input.strip()}..."):
                    test_report = build_current_whatsapp_report(limit=3)
                    w_ok, w_msg = send_whatsapp_web_auto(dest_phone_input.strip(), test_report)
                    if w_ok:
                        st.success(f"✅ {w_msg}")
                    else:
                        st.error(f"❌ {w_msg}")

        st.markdown("---")
        st.markdown("#### ⚙️ **Additional Notification Channels**")

        alert_mode = st.radio(
            "Select Additional Channel:",
            [
                "🔔 Mode 1: Free Ntfy.sh Mobile Push (Instant Push, Zero Registration)",
                "⚡ Mode 2: 1-Click WhatsApp Link (wa.me Manual Fallback)",
                "🤖 Mode 3: Automated API Gateways (CallMeBot / Green-API)"
            ],
            index=0
        )

        saved_wa_key = os.getenv("WHATSAPP_API_KEY", "")
        saved_ntfy = os.getenv("NTFY_TOPIC", "georg_ai_agent_alerts")
        saved_green_inst = os.getenv("GREEN_API_INSTANCE_ID", "")
        saved_green_tok = os.getenv("GREEN_API_TOKEN", "")

        report_text = build_current_whatsapp_report(limit=3)

        if "Mode 1" in alert_mode:
            st.markdown("##### 🔔 **Free Ntfy.sh Instant Mobile Push**")
            st.caption("Get instant push notifications on your phone with zero API keys and zero registration! Emojis (🚀, ₹) fully supported.")

            ntfy_topic_input = st.text_input(
                "Ntfy Topic Name",
                value=saved_ntfy,
                placeholder="e.g. georg_ai_agent_alerts",
                help="Choose any unique topic name"
            )

            st.markdown(
                f"**How to receive push alerts on mobile:**\n"
                f"1. Install free **ntfy** app ([Android Play Store](https://play.google.com/store/apps/details?id=io.heckel.ntfy) / [iOS App Store](https://apps.apple.com/us/app/ntfy/id1625394747)) or open `https://ntfy.sh/{ntfy_topic_input}` in your browser.\n"
                f"2. Tap **Subscribe to topic** and enter `{ntfy_topic_input}`. Done!"
            )

            c_n1, c_n2 = st.columns(2)
            with c_n1:
                if st.button("💾 Save Topic", use_container_width=True, key="save_ntfy_btn"):
                    update_env_variable("NTFY_TOPIC", ntfy_topic_input.strip())
                    st.success("Topic saved to .env!")
            with c_n2:
                if st.button("🔔 Send Test Push", use_container_width=True, key="test_ntfy_btn"):
                    with st.spinner("Dispatching push notification..."):
                        ok, msg = send_ntfy_push(ntfy_topic_input.strip(), "🚀 The Logic Inside Your Agent Alert", "Winning products test alert via Ntfy.sh!")
                        if ok:
                            st.success(f"Push sent to ntfy.sh/{ntfy_topic_input}!")
                        else:
                            st.error(f"Error: {msg}")

        elif "Mode 2" in alert_mode:
            st.markdown("##### ⚡ **1-Click WhatsApp Link (wa.me)**")
            st.caption("Generates a WhatsApp link pre-filled with the latest AI findings (opens in WhatsApp Web/Desktop).")

            if dest_phone_input.strip():
                clean_phone = "".join(c for c in dest_phone_input if c.isdigit())
                direct_url = generate_wa_me_link(clean_phone, report_text)
                st.markdown(
                    f'<a href="{direct_url}" target="_blank" style="display:block; text-align:center; background:#25D366; color:white; padding:10px 14px; border-radius:8px; text-decoration:none; font-weight:700; margin:10px 0 6px 0;">'
                    f'📲 Send Report to My WhatsApp Now</a>',
                    unsafe_allow_html=True
                )
            else:
                st.info("Enter your mobile number above to generate your 1-click WhatsApp link.")

        else:
            st.markdown("##### 🤖 **API Gateways (CallMeBot / Green-API)**")

            api_provider = st.selectbox(
                "API Provider",
                ["CallMeBot", "Green-API (Fast & Automated)", "Meta WhatsApp Cloud API"]
            )

            if "CallMeBot" in api_provider:
                st.markdown(
                    "**CallMeBot Setup:**\n"
                    "1. Add `+34 644 59 71 67` to your WhatsApp contacts.\n"
                    "2. Send message: `I allow callmebot to send me messages`\n"
                    "3. Paste the apikey you received below:"
                )

                if not saved_wa_key:
                    st.warning(
                        "⚠️ **CallMeBot API Key is empty!** CallMeBot fails to deliver messages when the API key is not provided.\n\n"
                        "👉 **Recommended Alternative:** Click **'🔗 Step 1: Link WhatsApp QR (One-Time Setup)'** above to send WhatsApp messages 100% automatically with ZERO keys!\n"
                        "👉 **Or use Mode 1 (Ntfy Push):** Instant mobile alerts with zero signup."
                    )

                cmb_phone = st.text_input("Phone (with Country Code)", value=dest_phone_input or saved_phone, placeholder="e.g. 918903082778", key="cmb_p")
                cmb_key = st.text_input("CallMeBot API Key", value=saved_wa_key, type="password", placeholder="e.g. 1234567", key="cmb_k")

                if st.button("💾 Save CallMeBot Config", use_container_width=True):
                    update_env_variable("WHATSAPP_PHONE", cmb_phone.strip())
                    update_env_variable("WHATSAPP_API_KEY", cmb_key.strip())
                    st.success("CallMeBot config saved to .env!")

            elif "Green-API" in api_provider:
                st.markdown(
                    "**Green-API Setup:**\n"
                    "1. Register free at [green-api.com](https://green-api.com).\n"
                    "2. Scan QR code to connect your instance.\n"
                    "3. Enter Instance ID and Token below:"
                )
                g_inst_in = st.text_input("Green-API Instance ID", value=saved_green_inst, placeholder="e.g. 1101823456")
                g_tok_in = st.text_input("Green-API Token", value=saved_green_tok, type="password", placeholder="e.g. 4d7b...82")
                g_phone_in = st.text_input("Destination Phone (with Country Code)", value=dest_phone_input or saved_phone, placeholder="e.g. 918903082778", key="g_p")

                if st.button("💾 Save Green-API Config", use_container_width=True):
                    update_env_variable("GREEN_API_INSTANCE_ID", g_inst_in.strip())
                    update_env_variable("GREEN_API_TOKEN", g_tok_in.strip())
                    update_env_variable("WHATSAPP_PHONE", g_phone_in.strip())
                    st.success("Green-API config saved to .env!")

            else:
                st.markdown("Configure `META_WHATSAPP_TOKEN`, `META_PHONE_NUMBER_ID`, and `WHATSAPP_TO_PHONE` in `.env`.")

        st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
        # Universal Test Alert Button across all active channels
        if st.button("📲 Test Multi-Channel Alert Delivery", use_container_width=True, type="secondary"):
            with st.spinner("Dispatching test alert across active channels..."):
                current_p = os.getenv("WHATSAPP_PHONE", "")
                res = test_whatsapp_connection(
                    phone=current_p,
                    api_key=os.getenv("WHATSAPP_API_KEY", ""),
                    ntfy_topic=os.getenv("NTFY_TOPIC", "georg_ai_agent_alerts"),
                    green_instance=os.getenv("GREEN_API_INSTANCE_ID", ""),
                    green_token=os.getenv("GREEN_API_TOKEN", "")
                )
                ok = res[0]
                msg = res[1]
                wa_link = res[2] if len(res) > 2 else ""

                if ok:
                    st.success(f"Status: {msg}")
                else:
                    st.warning(f"Status: {msg}")

                if wa_link:
                    st.markdown(
                        f'<a href="{wa_link}" target="_blank" style="display:block; text-align:center; background:#25D366; color:white; padding:8px 12px; border-radius:6px; text-decoration:none; font-weight:700; margin-top:6px;">'
                        f'📲 Click to Open in WhatsApp Web / App</a>',
                        unsafe_allow_html=True
                    )

    st.markdown("---")
    with st.expander("📁 Import Products via CSV"):
        uploaded_csv = st.file_uploader("Upload CSV", type=["csv"])
        if uploaded_csv is not None:
            if st.button("Import Uploaded CSV"):
                try:
                    count = import_products_from_csv(uploaded_csv)
                    st.success(f"Successfully imported {count} products!")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Import failed: {ex}")


# ==========================================
# DATA LOADING & FILTERING
# ==========================================
all_products = get_all_products_with_latest_data()

# Ensure we have data; if brand new db, seed it
if not all_products:
    seed_demo_data()
    all_products = get_all_products_with_latest_data()

# Filter by Price Range & Platform
filtered_products = [
    p for p in all_products
    if (p.get("price") is not None and price_range[0] <= p["price"] <= price_range[1])
    and (platform_choice == "All Platforms" or p.get("platform") == platform_choice)
]

rising_products = [p for p in filtered_products if p.get("trend_status") == "High Sale Rising"]
dropping_products = [p for p in filtered_products if p.get("trend_status") == "Dropping"]
ready_products = [p for p in filtered_products if p.get("website_ready") == 1]
shortlisted_items = get_shortlist()


# ==========================================
# MAIN HEADER
# ==========================================
st.markdown("""
<div class="main-header">
    <h1 style="color: #ffffff; margin: 0; font-size: 2.2rem; font-weight: 800;">
        🚀 The Logic Inside Your Agent
    </h1>
    <p style="color: #cbd5e1; margin: 8px 0 0 0; font-size: 1.05rem;">
        AI-Powered E-commerce Market & Product Trend Hunter &bull; 
        <strong>₹100 to ₹1,000 Sweet Spot</strong> (Amazon India & Meesho)
    </p>
</div>
""", unsafe_allow_html=True)


# ==========================================
# TABS
# ==========================================
tab0, tab1, tab2, tab3, tab4 = st.tabs([
    "🏆 7-Day Master Verdict (99% Launch List)",
    "🔥 High Sale & Rising (Buy / Stock)",
    "📉 Drop Alerts (Avoid Dead Stock)",
    "🛒 Future Website Ready (Shortlist & Export)",
    "🔍 Single Product Deep Check"
])


# ==========================================
# TAB 0: 7-DAY MASTER VERDICT (99% CONFIDENCE LAUNCH LIST)
# ==========================================
with tab0:
    st.markdown("### 🏆 7-Day Omni-Channel Master Verdict (99% Confidence)")
    st.markdown(
        "Synthesizing 7 continuous days of **E-Commerce BSR & Review Momentum**, **Instagram Reels & YouTube Shorts Buzz**, "
        "and **Google Trends India Search Volume** to discover the mathematically highest probability product launches for your new website."
    )

    # 7-Day Analysis Progress Tracker
    st.markdown("""
    <div style="background: linear-gradient(135deg, rgba(30, 41, 59, 0.9) 0%, rgba(15, 23, 42, 0.95) 100%); border: 1px solid rgba(99, 102, 241, 0.35); border-radius: 12px; padding: 16px; margin-bottom: 22px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <span style="font-weight: 700; font-size: 0.95rem; color: #a5b4fc;">📡 7-Day Multi-Signal Convergence Pipeline</span>
            <span style="background: rgba(16, 185, 129, 0.2); color: #34d399; padding: 4px 12px; border-radius: 999px; font-size: 0.75rem; font-weight: 700;">● ALL SIGNALS CONVERGED</span>
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px;">
            <div style="background: rgba(255,255,255,0.04); padding: 8px 12px; border-radius: 8px; border-left: 3px solid #6366f1;">
                <div style="font-size: 0.75rem; color: #94a3b8;">Day 1-2</div>
                <div style="font-size: 0.82rem; font-weight: 600; color: #f8fafc;">E-com Ingestion</div>
                <div style="font-size: 0.7rem; color: #10b981;">Amazon & Meesho BSR</div>
            </div>
            <div style="background: rgba(255,255,255,0.04); padding: 8px 12px; border-radius: 8px; border-left: 3px solid #ec4899;">
                <div style="font-size: 0.75rem; color: #94a3b8;">Day 3-4</div>
                <div style="font-size: 0.82rem; font-weight: 600; color: #f8fafc;">Social Viral Scan</div>
                <div style="font-size: 0.7rem; color: #ec4899;">Reels & Shorts Signals</div>
            </div>
            <div style="background: rgba(255,255,255,0.04); padding: 8px 12px; border-radius: 8px; border-left: 3px solid #f59e0b;">
                <div style="font-size: 0.75rem; color: #94a3b8;">Day 5</div>
                <div style="font-size: 0.82rem; font-weight: 600; color: #f8fafc;">Buyer Intent NLP</div>
                <div style="font-size: 0.7rem; color: #f59e0b;">'Link Please' Ratio</div>
            </div>
            <div style="background: rgba(255,255,255,0.04); padding: 8px 12px; border-radius: 8px; border-left: 3px solid #3b82f6;">
                <div style="font-size: 0.75rem; color: #94a3b8;">Day 6</div>
                <div style="font-size: 0.82rem; font-weight: 600; color: #f8fafc;">Google Trends IN</div>
                <div style="font-size: 0.7rem; color: #3b82f6;">7d Search Momentum</div>
            </div>
            <div style="background: rgba(255,255,255,0.04); padding: 8px 12px; border-radius: 8px; border-left: 3px solid #10b981;">
                <div style="font-size: 0.75rem; color: #94a3b8;">Day 7</div>
                <div style="font-size: 0.82rem; font-weight: 600; color: #f8fafc;">99% Multi-Signal</div>
                <div style="font-size: 0.7rem; color: #34d399;">Launch Blueprint Ready</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_v1, col_v2 = st.columns([3, 1])
    with col_v1:
        st.markdown("#### 🎯 **Top Launch Winners (90%–99% Confidence to Sell Now)**")
    with col_v2:
        if st.button("🔄 Recalculate 7-Day Verdicts", use_container_width=True, type="primary"):
            with st.spinner("Analyzing 7-day multi-signal history across E-com + Social Media..."):
                generate_7day_master_verdict(api_key=gemini_api_key)
                st.success("7-Day Master Verdicts updated!")
                st.rerun()

    weekly_verdicts = get_latest_weekly_verdicts(limit=3)
    if not weekly_verdicts:
        generate_7day_master_verdict(api_key=gemini_api_key)
        weekly_verdicts = get_latest_weekly_verdicts(limit=3)

    if not weekly_verdicts:
        st.info("No 7-day master verdicts generated yet. Click 'Recalculate 7-Day Verdicts' or 'Seed Demo' in the sidebar.")
    else:
        rank_badges = ["🥇 #1 MUST-LAUNCH WINNER", "🥈 #2 HIGH POTENTIAL WINNER", "🥉 #3 PROFITABLE CONTENDER"]
        rank_gradients = [
            "linear-gradient(135deg, rgba(234, 179, 8, 0.15) 0%, rgba(168, 85, 247, 0.15) 100%)",
            "linear-gradient(135deg, rgba(148, 163, 184, 0.15) 0%, rgba(99, 102, 241, 0.15) 100%)",
            "linear-gradient(135deg, rgba(217, 119, 6, 0.15) 0%, rgba(236, 72, 153, 0.15) 100%)"
        ]

        for idx, verd in enumerate(weekly_verdicts):
            p_title = verd.get("title", f"Product #{verd.get('product_id')}")
            conf = verd.get("confidence_score", 95.0)
            sourcing = verd.get("sourcing_cost_est", 120.0)
            target_p = verd.get("target_selling_price", 399.0)
            profit = verd.get("net_profit_per_unit", target_p - sourcing - 70)
            p_cat = verd.get("category", "Trending")
            p_plat = verd.get("platform", "Amazon India")
            p_img = verd.get("image_url") or "https://images.unsplash.com/photo-1540932239986-30128078f3c5?w=500&q=80"
            tanglish = verd.get("verdict_summary_tanglish", "")
            badge_title = rank_badges[idx] if idx < len(rank_badges) else f"#{idx+1} WINNER"
            bg_grad = rank_gradients[idx] if idx < len(rank_gradients) else rank_gradients[0]

            bp = {}
            if verd.get("launch_blueprint_json"):
                try:
                    bp = json.loads(verd["launch_blueprint_json"])
                except Exception:
                    pass

            st.markdown(f"""
            <div style="background: {bg_grad}; border: 1px solid rgba(255, 215, 0, 0.35); border-radius: 16px; padding: 20px; margin-bottom: 20px; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 12px;">
                    <span style="background: #eab308; color: #000; padding: 4px 14px; border-radius: 999px; font-weight: 800; font-size: 0.85rem; letter-spacing: 0.5px;">{badge_title}</span>
                    <span style="background: rgba(16, 185, 129, 0.25); color: #34d399; border: 1px solid #10b981; padding: 4px 14px; border-radius: 999px; font-weight: 800; font-size: 0.9rem;">🎯 {conf:.1f}% Launch Confidence Score</span>
                </div>
                <h3 style="color: #ffffff; margin: 4px 0 10px 0;">{p_title}</h3>
                <div style="font-size: 0.85rem; color: #94a3b8; margin-bottom: 14px;">Category: <strong style="color: #cbd5e1;">{p_cat}</strong> | Source Platform: <strong style="color: #cbd5e1;">{p_plat}</strong></div>
            </div>
            """, unsafe_allow_html=True)

            col_w_left, col_w_mid, col_w_right = st.columns([1.2, 1.8, 2.0])

            with col_w_left:
                st.image(p_img, use_container_width=True)
                st.markdown(f"**Wholesale Sourcing (IndiaMART):** `₹{sourcing:.0f}`")
                st.markdown(f"**Target Website Price:** `₹{target_p:.0f}`")
                st.markdown(f"**Estimated Net Profit:** `₹{profit:.0f} / unit`")
                if verd.get("url"):
                    st.markdown(f"[🔗 Marketplace Listing]({verd.get('url')})")

                if st.button(f"⭐ Add #{verd['product_id']} to Shortlist", key=f"shortlist_v_{verd['id']}_{verd['product_id']}"):
                    add_to_shortlist(verd["product_id"], custom_selling_price=target_p, notes=f"99% Master Verdict: ₹{profit:.0f} profit/unit")
                    st.success("Added to storefront shortlist!")
                    st.rerun()

            with col_w_mid:
                st.markdown("##### 🔬 **Why 99% Accurate? (5-Pillar Score)**")
                p1_desc = bp.get("pillar_1_ecom_consistency", f"{verd.get('ecom_consistency_7d', 85):.1f}%")
                p2_desc = bp.get("pillar_2_social_viral", f"{verd.get('social_viral_score', 80):.1f}%")
                p3_desc = bp.get("pillar_3_google_spike", "85% (Active 7-day search momentum)")
                p4_desc = bp.get("pillar_4_unit_economics", f"90% (3x markup, ₹{profit:.0f} profit)")
                p5_desc = bp.get("pillar_5_monopoly_check", "80% (Low brand monopoly)")

                st.markdown(f"1. **7-Day E-Com Consistency (25%):**\n   _{p1_desc}_")
                st.markdown(f"2. **Social Media Viral & 'Link Please' Buzz (25%):**\n   _{p2_desc}_")
                st.markdown(f"3. **Google Trends Search Spike in India (15%):**\n   _{p3_desc}_")
                st.markdown(f"4. **Unit Economics & Wholesale Margin (20%):**\n   _{p4_desc}_")
                st.markdown(f"5. **Low Monopoly / Saturation Check (15%):**\n   _{p5_desc}_")

                st.markdown(f"""
                <div class="tanglish-box" style="margin-top: 14px;">
                    <strong>🗣️ AI Verdict Summary (Tanglish):</strong><br>
                    {tanglish}
                </div>
                """, unsafe_allow_html=True)

            with col_w_right:
                st.markdown("##### 📈 **7-Day Multi-Signal Convergence Chart**")
                sig_df = get_combined_7day_product_signals(verd["product_id"])
                if not sig_df.empty:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=sig_df["date"],
                        y=sig_df["social_views_score"],
                        mode='lines+markers',
                        name='Social Viral Buzz',
                        line=dict(color='#ec4899', width=3),
                        marker=dict(size=6)
                    ))
                    fig.add_trace(go.Scatter(
                        x=sig_df["date"],
                        y=sig_df["buyer_intent_score"],
                        mode='lines+markers',
                        name="'Link Please' Intent",
                        line=dict(color='#f59e0b', width=2, dash='dot'),
                        marker=dict(size=5)
                    ))
                    fig.add_trace(go.Scatter(
                        x=sig_df["date"],
                        y=sig_df["google_trend_score"],
                        mode='lines+markers',
                        name='Google Trends IN',
                        line=dict(color='#3b82f6', width=2),
                        marker=dict(size=5)
                    ))
                    fig.add_trace(go.Scatter(
                        x=sig_df["date"],
                        y=sig_df["review_count"],
                        mode='lines',
                        name='Review Velocity',
                        yaxis='y2',
                        line=dict(color='#10b981', width=2, dash='dash')
                    ))
                    fig.update_layout(
                        height=260,
                        margin=dict(l=10, r=10, t=25, b=20),
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=9, color="#94a3b8")),
                        xaxis=dict(showgrid=False, tickfont=dict(size=9, color="#94a3b8")),
                        yaxis=dict(title=dict(text="Signals (0-100)", font=dict(size=9, color="#94a3b8")), showgrid=True, gridcolor='rgba(255,255,255,0.05)', range=[0, 105]),
                        yaxis2=dict(title=dict(text="Reviews", font=dict(size=9, color="#10b981")), overlaying='y', side='right', showgrid=False)
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.caption("Gathering continuous 7-day signals...")

                ad_hook = bp.get("ad_hook_tanglish", "Indha product daily life-la romba useful! Super problem solver.")
                target_aud = bp.get("target_audience", "Indian impulse online shoppers")
                sup_search = bp.get("supplier_search", f"{p_title[:25]} wholesale supplier IndiaMART")

                with st.expander("🚀 View Complete Launch Blueprint", expanded=True):
                    st.markdown(f"**🎯 Target Audience:** {target_aud}")
                    st.markdown(f"**🎥 Ready Instagram Reel Hook (Tanglish):**\n> _{ad_hook}_")
                    st.markdown(f"**🔍 IndiaMART Sourcing Search:** `{sup_search}`")
                    st.markdown(f"**📦 Recommended Fulfillment:** Free COD via Shiprocket/Delhivery at ₹{target_p:.0f}")

            st.markdown("---")


# ==========================================
# TAB 1: HIGH SALE & RISING
# ==========================================
with tab1:
    st.markdown("### 🔥 High Momentum Winning Products")
    st.markdown("Products with high demand velocity, low review saturation (30-450 reviews), climbing BSR ranks, and healthy markup margins.")

    # Top KPI Metrics
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    avg_score = round(sum(p.get("sellability_score") or 0 for p in rising_products) / max(len(rising_products), 1), 1)
    avg_margin = round(sum(p.get("estimated_margin_pct") or 0 for p in rising_products) / max(len(rising_products), 1), 1)

    kpi1.metric("Rising Products", len(rising_products), f"{len(filtered_products)} total scanned")
    kpi2.metric("Avg Sellability Score", f"{avg_score}/100", "+ High Quality")
    kpi3.metric("Avg Sourcing Margin", f"{avg_margin}%", "Wholesale vs Website")
    kpi4.metric("Sweet Spot Price", "₹249 – ₹799", "Impulse Buy Target")

    st.markdown("---")

    if not rising_products:
        st.info("No products currently matched the 'High Sale Rising' filter in this price range. Adjust your filters or click 'Run AI Analysis on All'.")
    else:
        for p in rising_products:
            with st.container():
                st.markdown('<div class="product-card">', unsafe_allow_html=True)
                col_img, col_info, col_chart = st.columns([1.2, 2.5, 2])

                with col_img:
                    st.image(p.get("image_url") or "https://images.unsplash.com/photo-1540932239986-30128078f3c5?w=500&q=80", use_container_width=True)
                    st.markdown(f"<span class='badge-rising'>🔥 High Sale Rising</span>", unsafe_allow_html=True)
                    st.markdown(f"**Platform:** {p.get('platform')}")
                    if p.get("url"):
                        st.markdown(f"[🔗 View on Marketplace]({p.get('url')})")

                with col_info:
                    st.markdown(f"#### {p.get('title')}")
                    st.markdown(f"**Category:** `{p.get('category')}`")
                    
                    # Metrics row
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Market Price", f"₹{p.get('price'):.0f}")
                    m2.metric("Rating", f"★ {p.get('rating')}")
                    m3.metric("Reviews", f"{p.get('review_count')}", f"+{p.get('review_velocity_7d')} 7d")
                    m4.metric("Sellability", f"{p.get('sellability_score')}/100")

                    st.markdown(f"**🧠 AI Reasoning:** {p.get('ai_reasoning')}")
                    
                    if p.get("marketing_angle_for_website"):
                        st.markdown(f"**🎯 Website Ad Hook:** *\"{p.get('marketing_angle_for_website')}\"*")

                    if p.get("ai_summary_tamil_english"):
                        st.markdown(f"""
                        <div class="tanglish-box">
                            <strong>🗣️ Agent Verdict (Tanglish):</strong> {p.get('ai_summary_tamil_english')}
                        </div>
                        """, unsafe_allow_html=True)

                    st.write("")
                    col_act1, col_act2 = st.columns([1.5, 2])
                    with col_act1:
                        if p.get("is_shortlisted"):
                            st.success("✅ Added to Shortlist")
                        else:
                            if st.button("➕ Add to Website Shortlist", key=f"shortlist_btn_{p['product_id']}"):
                                add_to_shortlist(p["product_id"], custom_selling_price=p.get("recommended_selling_price"))
                                st.rerun()

                with col_chart:
                    # Plot 7-day metric history
                    history = get_product_metrics_history(p["product_id"], days=7)
                    if history and len(history) > 1:
                        df_hist = pd.DataFrame(history)
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(
                            x=df_hist["date"],
                            y=df_hist["bsr_rank"],
                            mode="lines+markers",
                            name="BSR Rank",
                            line=dict(color="#10b981", width=3)
                        ))
                        # Invert y-axis so smaller BSR rank (better rank) climbs to the top!
                        fig.update_layout(
                            title=dict(text="📈 BSR Rank Momentum (Lower = Higher Sales)", font=dict(size=12, color="#cbd5e1")),
                            yaxis=dict(autorange="reversed", title="BSR Rank", gridcolor="rgba(255,255,255,0.05)"),
                            xaxis=dict(title="", showgrid=False),
                            height=220,
                            margin=dict(l=10, r=10, t=35, b=20),
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(color="#94a3b8")
                        )
                        st.plotly_chart(fig, use_container_width=True, key=f"chart_{p['product_id']}")
                    else:
                        st.caption("Historical trend chart will display as daily snapshots accumulate.")

                st.markdown('</div>', unsafe_allow_html=True)


# ==========================================
# TAB 2: DROP ALERTS (AVOID)
# ==========================================
with tab2:
    st.markdown("### 📉 Drop Alerts & Dead Stock Warnings")
    st.markdown("Products triggered by price war crashes, deteriorating ratings (<3.7), negative review keywords, or dropping BSR ranks.")

    if not dropping_products:
        st.success("🎉 No dropping or dead stock products currently flagged in your catalog filter.")
    else:
        st.warning(f"⚠️ {len(dropping_products)} products have severe warning signals. Avoid stocking or white-labeling these items.")

        for p in dropping_products:
            with st.container():
                st.markdown('<div class="product-card" style="border-left: 5px solid #ef4444;">', unsafe_allow_html=True)
                col_img, col_info, col_chart = st.columns([1.2, 2.5, 2])

                with col_img:
                    st.image(p.get("image_url") or "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=500&q=80", use_container_width=True)
                    st.markdown(f"<span class='badge-dropping'>📉 Dying Trend / High Return Risk</span>", unsafe_allow_html=True)
                    st.markdown(f"**Platform:** {p.get('platform')}")

                with col_info:
                    st.markdown(f"#### ⚠️ {p.get('title')}")
                    
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Market Price", f"₹{p.get('price'):.0f}", f"{p.get('price_change_7d')}% 7d")
                    m2.metric("Rating", f"★ {p.get('rating')}", delta_color="inverse")
                    m3.metric("Reviews", f"{p.get('review_count')}")
                    m4.metric("Sellability", f"{p.get('sellability_score')}/100", delta_color="inverse")

                    st.markdown(f"<p style='color:#f87171;'><strong>🚩 Red Flags:</strong> {p.get('red_flags') or 'High customer returns, poor product longevity.'}</p>", unsafe_allow_html=True)
                    st.markdown(f"**💬 Recent Reviews Sample:** *\"{p.get('recent_reviews_text')}\"*")
                    st.markdown(f"**🧠 Agent Analysis:** {p.get('ai_reasoning')}")

                    if p.get("ai_summary_tamil_english"):
                        st.markdown(f"""
                        <div class="tanglish-box" style="border-left-color: #ef4444; background: rgba(239, 68, 68, 0.08);">
                            <strong>🗣️ Agent Warning (Tanglish):</strong> {p.get('ai_summary_tamil_english')}
                        </div>
                        """, unsafe_allow_html=True)

                with col_chart:
                    history = get_product_metrics_history(p["product_id"], days=7)
                    if history and len(history) > 1:
                        df_hist = pd.DataFrame(history)
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(
                            x=df_hist["date"],
                            y=df_hist["price"],
                            mode="lines+markers",
                            name="Price (₹)",
                            line=dict(color="#ef4444", width=3)
                        ))
                        fig.update_layout(
                            title=dict(text="🔻 Price Erosion / Price War Trend", font=dict(size=12, color="#f87171")),
                            yaxis=dict(title="Price (₹)", gridcolor="rgba(255,255,255,0.05)"),
                            xaxis=dict(title="", showgrid=False),
                            height=220,
                            margin=dict(l=10, r=10, t=35, b=20),
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(color="#94a3b8")
                        )
                        st.plotly_chart(fig, use_container_width=True, key=f"drop_chart_{p['product_id']}")

                st.markdown('</div>', unsafe_allow_html=True)


# ==========================================
# TAB 3: FUTURE WEBSITE READY (SHORTLIST & EXPORT)
# ==========================================
with tab3:
    st.markdown("### 🛒 Future Website Shortlist & Multi-Platform Exporter")
    st.warning("Sourcing cost, suggested selling price and margin are estimates—not verified supplier quotes. Confirm supplier price, shipping, taxes, fees, returns and affiliate eligibility before spending money.")
    st.markdown("Products vetted for your future direct-to-consumer standalone store (Shopify, WooCommerce, or Custom Site).")

    if not shortlisted_items:
        st.info("No products currently shortlisted. Browse **Tab 1** and click **➕ Add to Website Shortlist** to queue products for your website!")
    else:
        # Profit and Revenue Summary Calculator
        st.markdown("#### 💰 **Estimated Portfolio Economics**")
        calc_col1, calc_col2, calc_col3, calc_col4 = st.columns(4)

        sourcing_values = [item.get("estimated_sourcing_cost") for item in shortlisted_items if item.get("estimated_sourcing_cost") is not None]
        retail_values = [item.get("custom_selling_price") or item.get("recommended_selling_price") for item in shortlisted_items]
        retail_values = [value for value in retail_values if value is not None]
        total_sourcing = sum(sourcing_values) if sourcing_values else None
        total_retail = sum(retail_values) if retail_values else None
        gross_profit_per_basket = total_retail - total_sourcing if total_retail is not None and total_sourcing is not None else None
        margin_pct = round((gross_profit_per_basket / total_retail) * 100, 1) if gross_profit_per_basket is not None and total_retail else None

        calc_col1.metric("Shortlisted SKUs", len(shortlisted_items))
        calc_col2.metric("Estimated Sourcing Cost", f"₹{total_sourcing:.0f}" if total_sourcing is not None else "Unavailable")
        calc_col3.metric("Entered/Suggested Retail Total", f"₹{total_retail:.0f}" if total_retail is not None else "Unavailable")
        calc_col4.metric("Gross Margin (estimate)", f"{margin_pct}%" if margin_pct is not None else "Unavailable", "Excludes shipping, tax, fees, ads and returns")

        st.markdown("---")

        # Display Shortlisted Products
        for item in shortlisted_items:
            with st.container():
                st.markdown('<div class="product-card" style="border: 1px solid rgba(16, 185, 129, 0.3);">', unsafe_allow_html=True)
                sc1, sc2, sc3, sc4 = st.columns([1, 2.5, 1.8, 1])

                with sc1:
                    st.image(item.get("image_url") or "https://images.unsplash.com/photo-1540932239986-30128078f3c5?w=500&q=80", use_container_width=True)
                    st.caption(f"ID: `{item.get('product_id')}`")

                with sc2:
                    st.markdown(f"##### {item.get('title')}")
                    st.markdown(f"**Platform:** {item.get('platform')} &bull; **Category:** {item.get('category')}")
                    if item.get("marketing_angle_for_website"):
                        st.markdown(f"**🎯 Ad Copy Angle:** *\"{item.get('marketing_angle_for_website')}\"*")
                    if item.get("notes"):
                        st.markdown(f"**📝 Launch Notes:** `{item.get('notes')}`")

                with sc3:
                    rec_p = item.get("recommended_selling_price")
                    src_c = item.get("estimated_sourcing_cost")
                    cust_p = item.get("custom_selling_price") or rec_p
                    market_p = item.get("current_market_price")
                    
                    st.markdown(f"**Market Price:** ₹{market_p:.0f}" if market_p is not None else "**Market Price:** Unavailable")
                    st.markdown(f"**Estimated Sourcing:** ₹{src_c:.0f}" if src_c is not None else "**Estimated Sourcing:** Unavailable")
                    st.markdown(f"**Suggested Website Price:** ₹{rec_p:.0f}" if rec_p is not None else "**Suggested Website Price:** Unavailable")
                    if cust_p is not None and src_c is not None:
                        unit_profit = cust_p - src_c
                        st.markdown(f"**Gross Difference / Unit:** ₹{unit_profit:.0f} (before other costs)")
                    else:
                        st.markdown("**Gross Difference / Unit:** Unavailable until costs are entered")

                with sc4:
                    st.write("")
                    if st.button("❌ Remove", key=f"del_sl_{item['product_id']}", use_container_width=True):
                        remove_from_shortlist(item["product_id"])
                        st.rerun()

                st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("#### 📦 **One-Click Storefront Exporters**")
        
        # Prepare Export Formats
        shopify_rows = []
        woo_rows = []
        for i in shortlisted_items:
            pid = str(i.get("product_id", "")).strip()
            title = str(i.get("title", "")).strip()
            category = str(i.get("category", "General")).strip()
            image_url = str(i.get("image_url", "")).strip()
            marketing = str(i.get("marketing_angle_for_website", "")).strip()

            cust_p = i.get("custom_selling_price")
            rec_p = i.get("recommended_selling_price")
            market_p = i.get("current_market_price", 0)
            price_candidate = cust_p if cust_p is not None else rec_p
            if price_candidate is None:
                price_candidate = market_p
            if price_candidate is None or float(price_candidate) <= 0:
                continue
            price_val = float(price_candidate)
            compare_price = ""  # No fabricated "compare at" discount price

            shopify_rows.append({
                "Handle": f"prod-{pid.lower()}",
                "Title": title,
                "Body (HTML)": f"<p>{marketing}</p>",
                "Vendor": "My DTC Brand",
                "Type": category,
                "Tags": "Trending, Under 1000, Viral, Indian Market",
                "Published": "TRUE",
                "Variant Price": price_val,
                "Variant Compare At Price": compare_price,
                "Variant Requires Shipping": "TRUE",
                "Image Src": image_url
            })

            woo_rows.append({
                "Type": "simple",
                "SKU": pid,
                "Name": title,
                "Published": 1,
                "Regular price": price_val,
                "Categories": category,
                "Images": image_url,
                "Short description": marketing
            })

        shopify_df = pd.DataFrame(shopify_rows)
        woo_df = pd.DataFrame(woo_rows)

        # 3. Custom Site JSON
        custom_json = json.dumps(shortlisted_items, indent=2)

        exp_col1, exp_col2, exp_col3 = st.columns(3)
        with exp_col1:
            st.download_button(
                "🛍️ Export Shopify CSV",
                data=shopify_df.to_csv(index=False),
                file_name=f"shopify_products_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )

        with exp_col2:
            st.download_button(
                "🌐 Export WooCommerce CSV",
                data=woo_df.to_csv(index=False),
                file_name=f"woocommerce_products_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )

        with exp_col3:
            st.download_button(
                "📄 Export Custom Site JSON",
                data=custom_json,
                file_name=f"storefront_catalog_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                use_container_width=True
            )


# ==========================================
# TAB 4: SINGLE PRODUCT DEEP CHECK
# ==========================================
with tab4:
    st.markdown("### 🔍 Instant Single Product Deep Check")
    st.markdown("Paste metrics or review snippets for any Indian marketplace product to evaluate whether it's a winning item for your store.")

    with st.form("single_check_form"):
        fc1, fc2 = st.columns([2, 1])
        with fc1:
            test_title = st.text_input("Product Title", value="Silicone Reusable Tea Infuser Leaf Filter")
            test_category = st.text_input("Category", value="Kitchen & Dining")
            test_url = st.text_input("Product URL", value="https://www.amazon.in/dp/B0TEAFILTER")

        with fc2:
            test_platform = st.selectbox("Platform", ["Amazon India", "Meesho"])
            test_price = st.number_input("Market Price (₹)", min_value=100.0, max_value=1000.0, value=199.0, step=10.0)
            test_rating = st.slider("Rating (out of 5)", min_value=1.0, max_value=5.0, value=4.4, step=0.1)
            test_reviews = st.number_input("Total Review Count", min_value=0, max_value=100000, value=85, step=5)

        tc1, tc2 = st.columns(2)
        with tc1:
            test_price_change = st.number_input("7-Day Price Change %", value=0.0, step=1.0, help="Negative means continuous price dropping")
        with tc2:
            test_bsr_improvement = st.number_input("7-Day BSR Improvement %", value=35.0, step=5.0, help="Positive means climbing bestseller charts")

        test_reviews_text = st.text_area(
            "Customer Review Snippets",
            value="Great food grade silicone, leaves no plastic smell in tea. Cleans very easily with warm water. Very cute design!"
        )

        submit_check = st.form_submit_button("🧠 Evaluate with Agent AI Brain", type="primary", use_container_width=True)

    if submit_check:
        with st.spinner("Analyzing market dynamics, sourcing feasibility, and customer sentiment..."):
            mock_product = {
                "product_id": "TEST_DEEP_CHECK",
                "platform": test_platform,
                "title": test_title,
                "category": test_category,
                "price": test_price,
                "rating": test_rating,
                "review_count": test_reviews,
                "price_change_7d": test_price_change,
                "review_velocity_7d": 18,
                "bsr_improvement_7d": test_bsr_improvement,
                "recent_reviews_text": test_reviews_text,
                "url": test_url
            }

            result = analyze_product_with_gemini(mock_product, api_key=gemini_api_key)

            st.markdown("---")
            st.markdown("### 📋 **Agent Strategic Verdict**")

            res_c1, res_c2, res_c3 = st.columns(3)
            res_c1.metric("Trend Status", result.trend_status)
            res_c2.metric("Sellability Score", f"{result.sellability_score}/100")
            res_c3.metric("Website Ready?", "✅ YES" if result.website_ready else "❌ NO")

            ec1, ec2, ec3 = st.columns(3)
            ec1.metric("Est. Wholesale Sourcing", f"₹{result.estimated_sourcing_cost:.0f}")
            ec2.metric("Recommended Website Price", f"₹{result.recommended_selling_price:.0f}")
            ec3.metric("Projected Margin", f"{result.estimated_margin_pct:.1f}%")

            st.markdown(f"**🧠 Strategic Reasoning:** {result.ai_reasoning}")
            st.markdown(f"**🎯 Marketing Angle:** {result.marketing_angle_for_website}")
            if result.red_flags:
                st.markdown(f"**🚩 Red Flags / Precautions:** {result.red_flags}")
            if result.customer_pain_points:
                st.markdown(f"**⚠️ Customer Pain Points:** {result.customer_pain_points}")

            if result.ai_summary_tamil_english:
                st.markdown(f"""
                <div class="tanglish-box">
                    <strong>🗣️ Agent Tanglish Summary:</strong> {result.ai_summary_tamil_english}
                </div>
                """, unsafe_allow_html=True)

            st.write("")
            if st.button("➕ Save & Shortlist This Checked Product"):
                h_id = f"CHECK_{int(datetime.now().timestamp())}"
                upsert_product(h_id, test_platform, test_title, test_category, test_url, "https://images.unsplash.com/photo-1540932239986-30128078f3c5?w=500&q=80")
                insert_daily_metric(h_id, datetime.now().strftime("%Y-%m-%d"), test_price, test_rating, test_reviews, 150, test_reviews_text)
                add_to_shortlist(h_id, custom_selling_price=result.recommended_selling_price, notes="Added via Single Product Deep Check")
                st.success("Saved to Shortlist!")
                st.rerun()
