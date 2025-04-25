
# AarogyaAI: AI-Powered Healthcare Assistant 🩺

## Overview
**AarogyaAI** is a multilingual AI-powered Telegram bot designed to democratize access to healthcare in India. It supports **22 Indian languages** via voice and text, enabling users to:

- Upload medical reports for insights  
- Receive personalized, regional diet plans  
- Understand medication usage  
- Get predictive health risk analysis (WIP)  

Built with a mission to promote **health equity**, especially in rural and underserved communities, **AarogyaAI** aligns with **SDG 3 – Good Health and Well-Being**.

---

## 🌟 Features

- 🔤 **Multilingual Support**  
  Powered by Google Cloud Translate, supports 22 Indian languages.

- 🧾 **Medical Report Analysis**  
  Extracts key data from uploaded reports (PDF/images) via OCR.

- 🍱 **AI-Generated Diet Plans**  
  Google Gemini-based condition-specific 7-day meal plans, localized to regional cuisine.

- 💊 **Medicine Usage Guidance**  
  Provides native-language instructions for prescriptions.

- 🔮 **Predictive Health Risk Analysis** *(WIP)*  
  Future disease risk predictions based on lifestyle, genetics, and history.

- 🔒 **Robust Backend**  
  Secure MongoDB with TTL indexing, logging, and structured error handling.

- 🎯 **SDG 3 Compliant**  
  Empowers marginalized communities through inclusive digital health tools.

---

## 💻 Tech Stack

| Category | Technology |
|---------|-------------|
| Language | Python 3.8+ |
| Bot Framework | `python-telegram-bot` |
| AI/ML | Google Gemini API |
| Database | MongoDB |
| Localization | Google Cloud Translate, Text-to-Speech |
| Document Processing | Tesseract OCR, `pdf2image`, ReportLab |
| HTTP Client | `httpx` |
| Automation | `n8n` |
| Fonts | Noto Sans Malayalam |

---

## 📁 Project Structure

```
AarogyaAI/
├── src/
│   ├── ai_pipeline/
│   │   └── diet_agent.py
│   ├── bot/
│   │   └── telegram_bot.py
│   ├── database/
│   │   └── mongodb.py
│   ├── input_processing/
│   │   ├── asr.py
│   │   ├── ocr.py
│   │   └── translation.py
│   ├── utils/
│   │   ├── helpers.py
│   │   ├── pdf_generator.py
│   │   └── fonts/
│   │       └── NotoSansMalayalam-Regular.ttf
├── temp/                  
├── .env                  
├── bot.log              
└── README.md
```

---

## ⚙️ Prerequisites

- Python 3.8+
- MongoDB (local/cloud)
- Google Cloud account (Translate, Text-to-Speech, Gemini API keys)
- Tesseract OCR (configured in PATH)
- `n8n` for automation
- Conda or virtualenv for environment management

---

## 🚀 Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/your-repo/aarogyaai.git
cd aarogyaai
```

### 2. Create Environment

```bash
conda create -n venv python=3.8
conda activate venv
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
# OR install manually:
pip install pymongo google-cloud-translate google-generativeai python-telegram-bot reportlab google-cloud-texttospeech httpx pdf2image pytesseract
```

### 4. Set Environment Variables

Create a `.env` file:

```dotenv
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
GOOGLE_APPLICATION_CREDENTIALS=/path/to/google-credentials.json
MONGODB_URI=mongodb://localhost:27017
GEMINI_API_KEY=your_gemini_api_key
N8N_WEBHOOK_URL=http://localhost:5678/webhook/diet-plan-text
DIAGNOSTIC_MODE=True
```

### 5. Install Fonts

Download `NotoSansMalayalam-Regular.ttf` and place it in:

```
src/utils/fonts/
```

### 6. Configure Tesseract

For Windows:
```python
# In src/input_processing/ocr.py
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

### 7. Start n8n Automation Server

```bash
npm install -g n8n
n8n start
```

Ensure workflow is live at `http://localhost:5678`.

### 8. Run the Bot

```bash
python -m src.bot.telegram_bot
```

---

## ✨ Usage

### Initial Setup

1. Send `/start`
2. Choose your preferred language
3. Provide details (Name, Age, Allergies)

---

### 🤖 Commands

#### 🥗 /dietplan

Choose from:
- Upload a report to extract conditions & generate diet
- Specify a condition (e.g., "diabetic")
- Request a general diet

**Output**: A localized PDF diet plan.

#### 💊 Prescription Upload

Upload a prescription for medicine instructions in your language.

#### 🔮 Predictive Risk (WIP)

Input lifestyle/medical data to get a predictive risk assessment.

---

### 🔁 Example Interaction

**User**: `/dietplan`, chooses option 2, inputs "diabetic"  
**Bot**: Returns PDF:
```
Title: വ്യക്തിഗത ഡയറ്റ് പ്ലാൻ
Name: Haaa | Age: Unknown | Condition: Diabetes

7-Day Plan:
Day 1 - Breakfast: 2 ഗോതമ്പ് ദോശ, 1 കപ്പ് സാമ്പാർ
...
Notes: നിന്റെ ഭക്ഷണ സമയം സ്ഥിരമായി പാലിക്കുക.
```

---

## 🛠️ Troubleshooting

### MongoDB Index Error

```bash
use aarogyaai
db.interactions.dropIndex("user_id_1_timestamp_1")
```

### Diet Plan Issues

- Check logs:
```bash
type bot.log | findstr "Raw Gemini response"
```

- Test Gemini manually:
```python
import google.generativeai as genai
genai.configure(api_key="your_gemini_api_key")
model = genai.GenerativeModel("gemini-1.5-pro")
print(model.generate_content("...").text)
```

### OCR Debug

```python
from src.input_processing.ocr import extract_text_from_pdf
print(extract_text_from_pdf("sample_report.pdf"))
```

---

## 🤝 Contributing

- Fork and submit PRs for new features or bug fixes.
- Report issues via GitHub including `bot.log` and MongoDB dumps.

---

## 📄 License

Licensed under the **MIT License**.

---

## 📬 Contact

For support or collaboration, email:  
**[mohammadmishal430@gmail.com](mailto:mohammadmishal430@gmail.com)**

---

Let me know if you’d like a badge section (build status, version, license), or a shorter TL;DR version too!
