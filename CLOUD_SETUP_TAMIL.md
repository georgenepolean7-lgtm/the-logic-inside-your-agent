# 🚀 The Logic Inside Your Agent — 24/7 Cloud & WhatsApp Setup Guide
### (தமிழில் முழுமையான வழிகாட்டி / Tamil & Tanglish Step-by-Step Guide)

உங்கள் Laptop ஆஃப் (Switch OFF) செய்யப்பட்டிருந்தாலும் கூட, இந்த Agent கிளவுடில் (GitHub Actions) 24/7 தானாக இயங்கி, Amazon India & Meesho-வில் ₹100 முதல் ₹1,000 விலையில் உள்ள High-Profit Winning Products-ஐ தேடிக் கண்டுபிடித்து **நேரடியாக உங்கள் WhatsApp-க்கு மெசேஜ் அனுப்பும்!**

---

## 📱 பகுதி 1: WhatsApp & Mobile Alerts அமைப்பது எப்படி? (3 எளிய வழிகள்)

CallMeBot API Key வருவதற்கு தாமதமானால் கவலைப்பட வேண்டாம்! இந்த Agent-ல் 3 சூப்பர் வழிகள் உள்ளன:

### ⚡ Mode 1: No-API-Key Direct WhatsApp (உடனடி 1-Click WhatsApp) — Zero Setup!
- எந்த API Key-யும் தேவையில்லை! காத்திருக்க வேண்டிய அவசியமும் இல்லை.
- Sidebar-ல் உங்கள் மொபைல் எண்ணை Country Code-டன் (`919876543210`) உள்ளிட்டு **"💾 Save Phone"** கிளிக் செய்யவும்.
- **"📲 Send Report to My WhatsApp Now"** பட்டனை கிளிக் செய்தால், வாட்ஸ்அப் தானாகவே திறந்து AI கண்டுபிடித்த அனைத்து Winning Products விவரங்களும் தானாகவே Type செய்யப்பட்டிருக்கும்!
- **"🌐 Open in Browser"** கொடுத்தால் லோக்கல் பிரவுசரிலேயே WhatsApp Web நேரடியாகத் திறக்கும்.

### 🔔 Mode 2: Free Ntfy.sh Instant Mobile Push (Zero Registration & Zero API Key!)
- GitHub Actions 24/7 கிளவுடில் இயங்கும் போது உங்கள் மொபைலுக்கு உடனுக்குடன் Push Notification பெற இதுவே சிறந்த வழி!
- **Step 1:** உங்கள் போனில் இலவச **ntfy** செயலியை ஏற்றவும் ([Android Play Store](https://play.google.com/store/apps/details?id=io.heckel.ntfy) / [iOS App Store](https://apps.apple.com/us/app/ntfy/id1625394747)) அல்லது பிரவுசரில் `https://ntfy.sh/<your_topic>` திறக்கவும்.
- **Step 2:** செயலியினுள் **Subscribe to topic** கிளிக் செய்து ஒரு தனித்துவமான பெயரை கொடுக்கவும் (எ.கா: `georg_ai_agent_alerts`).
- **Step 3:** Sidebar-ல் அந்த Topic பெயரை உள்ளிட்டு **"💾 Save Topic"** கிளிக் செய்யவும்.
- **Step 4:** **"🔔 Send Test Push"** கிளிக் செய்தால் உடனடியாக உங்கள் மொபைலில் Push Notification ஒலிக்கும்!

### 🤖 Mode 3: Automated API (Green-API / CallMeBot / Meta Cloud)
1. **Green-API (மிகவும் விரைவானது):**
   - [green-api.com](https://green-api.com) சென்று இலவச கணக்கு தொடங்கி QR Code-ஐ Scan செய்யவும்.
   - Instance ID & API Token-ஐ Sidebar-ல் உள்ளிட்டு சேமிக்கவும்.
2. **CallMeBot (இலவசம்):**
   - `+34 644 59 71 67` என்ற எண்ணிற்கு WhatsApp-ல் `I allow callmebot to send me messages` என அனுப்பவும்.
   - வரும் API Key-ஐ Sidebar-ல் உள்ளிடவும்.


---

## ☁️ பகுதி 2: லேப்டாப் OFF-ஆ இருந்தாலும் 24/7 இயங்குவது எப்படி? (GitHub Actions)

ஏற்கனவே இந்த புராஜெக்ட்டில் [`.github/workflows/autonomous_agent.yml`](.github/workflows/autonomous_agent.yml) ஃபைல் சேர்க்கப்பட்டுள்ளது. இது ஒவ்வொரு **4 மணி நேரத்திற்கும் தானாகவே இயங்கும்**.

### Step 1: GitHub-ல் புதிய Repository உருவாக்கவும்
1. [github.com](https://github.com) சென்று Login செய்யவும்.
2. **New Repository** உருவாக்கவும் (எ.கா: `ecommerce-ai-agent`). Repository-ஐ **Private** அல்லது **Public** ஆக வைக்கலாம்.

### Step 2: உங்கள் Code-ஐ GitHub-க்கு Push செய்யவும்
உங்கள் லேப்டாப் டெர்மினலில் இந்த கமாண்டுகளை இயக்கவும்:

```powershell
cd "c:\Users\georg\OneDrive\Desktop\The Logic Inside Your Agent"
git init
git add .
git commit -m "Deploy 24/7 Autonomous Market Agent"
git branch -M main
git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/ecommerce-ai-agent.git
git push -u origin main
```

### Step 3: GitHub Secrets Add செய்யவும் (முக்கியமானது!)
1. உங்கள் GitHub Repo பக்கத்தில் **Settings** கிளிக் செய்யவும்.
2. இடது மெனுவில் **Secrets and variables** -> **Actions** கிளிக் செய்யவும்.
3. **New repository secret** கிளிக் செய்து கீழ்க்கண்ட Secrets-ஐ ஒவ்வொன்றாக சேர்க்கவும்:

| Secret Name | Value (மதிப்பு) | விளக்கம் |
|---|---|---|
| `GEMINI_API_KEY` | `AIzaSy...` | Google AI Studio-வில் பெற்ற இலவச கீ |
| `WHATSAPP_PHONE` | `919876543210` | உங்கள் வாட்ஸ்அப் எண் (91 உடன்) |
| `NTFY_TOPIC` | `georg_ai_agent_alerts` | Ntfy மொபைல் Push Topic (API Key தேவையில்லை) |
| `WHATSAPP_API_KEY` | `1234567` | CallMeBot API Key (விருப்பமானது) |
| `GREEN_API_INSTANCE_ID`| `1101823...` | Green-API Instance ID (விருப்பமானது) |
| `GREEN_API_TOKEN` | `4d7b...` | Green-API Token (விருப்பமானது) |

### Step 4: GitHub Actions தானாக இயங்குவதை சரிபார்க்கவும்
- GitHub Repo-வில் உள்ள **Actions** டேபிற்குச் செல்லவும்.
- **"24/7 Autonomous Market Hunter"** தேர்ந்தெடுக்கவும்.
- **Run workflow** கிளிக் செய்து உடனடியாக ஒரு முறை டெஸ்ட் செய்யலாம்.
- ஒவ்வொரு 4 மணி நேரத்திற்கும் GitHub இலவச கிளவுடில் தானாகவே ரன் ஆகி:
  1. அமேசான் & மீஷோவில் ட்ரெண்டிங் பொருட்களை ஸ்கேன் செய்யும்.
  2. Gemini AI மூலம் ஆராய்ந்து 80+ மதிப்பெண் பெற்ற பொருட்களை ஷார்ட்லிஸ்ட் செய்யும்.
  3. **உடனடியாக உங்கள் வாட்ஸ்அப்பிற்கு Alert அனுப்பும்!**
  4. புது டேட்டாபேஸை தானாகவே GitHub-ல் Commit செய்துவிடும்.

---

## 🌐 பகுதி 3: மொபைல் போனில் Dashboard பார்க்க Streamlit Community Cloud (100% Free)

நீங்கள் எங்கிருந்தாலும் உங்கள் மொபைல் பிரவுசரிலேயே இந்த டாஷ்போர்டை திறந்து பார்க்க:

1. [share.streamlit.io](https://share.streamlit.io) இணையதளத்திற்குச் செல்லவும்.
2. **Continue with GitHub** கொடுத்து Sign In செய்யவும்.
3. **"Create app"** அல்லது **"New app"** கிளிக் செய்யவும்:
   - **Repository:** உங்கள் GitHub repository (எ.கா: `username/ecommerce-ai-agent`)
   - **Branch:** `main`
   - **Main file path:** `app.py`
   - **App URL:** நீங்கள் விரும்பும் பெயர் (எ.கா: `my-market-agent.streamlit.app`)
4. கீழேயுள்ள **"Advanced settings"** கிளிக் செய்து, **Secrets** பெட்டியில் இதை பேஸ்ட் செய்யவும்:
   ```toml
   GEMINI_API_KEY = "your_gemini_api_key"
   WHATSAPP_PHONE = "919876543210"
   WHATSAPP_API_KEY = "your_callmebot_api_key"
   ```
5. **"Deploy!"** கிளிக் செய்யவும்.

2 நிமிடங்களில் உங்கள் சொந்த லைவ் இணையதள முகவரி (`https://my-market-agent.streamlit.app`) தயாராகிவிடும்! 

இனி உங்கள் லேப்டாப்பை ஆன் செய்ய வேண்டிய அவசியமே இல்லை — **GitHub Actions 24/7 Background-ல் இயங்கும், WhatsApp-ல் நோட்டிபிகேஷன் வரும், நீங்கள் மொபைலில் இருந்தே Shopify / WooCommerce CSV-ஐ டவுன்லோட் செய்து உங்கள் ஈ-காமர்ஸ் தளத்தில் பதிவேற்றலாம்!** 🚀
