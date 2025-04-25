AarogyaAI: AI-Powered Healthcare Assistant🩺
Overview
AarogyaAI is a Telegram bot designed to democratize healthcare access in India by providing personalized health services in 22 Indian languages through voice and text inputs. It enables users to upload medical reports, receive tailored diet plans, understand medicine usage instructions, and access predictive health risk assessments based on lifestyle, genetic, and medical data. Built with a focus on inclusivity, AarogyaAI promotes health equity for rural and underserved communities, aligning with SDG 3 (Good Health and Well-Being).
Key features include:

🌟 Features
🔤 Multilingual Support: Processes queries and delivers responses in 22 Indian languages using Google Cloud Translate.

🧾 Medical Report Analysis: Extracts data from uploaded prescriptions or reports (PDF/image) via OCR to generate personalized insights.

🍱 AI-Generated Diet Plans: Crafts 7-day, condition-specific meal plans (e.g., for diabetes) using Google Gemini API—localized to regional cuisine.

💊 Medicine Usage Guidance: Provides clear, contextual instructions for prescription adherence in native languages.

🔮 Predictive Health Risk Analysis (WIP): Assesses future risks based on lifestyle, genetic, and historical medical data.

🔒 Robust Backend: Built on MongoDB with TTL indexing, logging, and error-handling for secure, efficient data flow.

🎯 SDG 3 Compliant: Empowers marginalized communities, promoting Good Health and Well-Being.


Tech Stack

Programming Language: Python 3.8+
Framework: python-telegram-bot
AI/ML: Google Gemini API (for diet plan generation and predictive analysis)
Database: MongoDB (user profiles, interactions, prompt caching)
Localization: Google Cloud Translate, Google Cloud Text-to-Speech
Document Processing: Tesseract OCR, pdf2image, ReportLab (PDF generation)
HTTP Client: httpx
Workflow Automation: n8n (backup messaging)
Fonts: Noto Sans Malayalam (for localized PDF rendering)

Project Structure
AarogyaAI/
├── src/
│   ├── ai_pipeline/
│   │   └── diet_agent.py       # Diet plan generation logic
│   ├── bot/
│   │   └── telegram_bot.py     # Telegram bot handlers
│   ├── database/
│   │   └── mongodb.py          # MongoDB connection and operations
│   ├── input_processing/
│   │   ├── asr.py              # Audio transcription
│   │   ├── ocr.py              # PDF/image text extraction
│   │   └── translation.py      # Text translation
│   ├── utils/
│   │   ├── helpers.py          # Utility functions
│   │   ├── pdf_generator.py    # PDF creation
│   │   └── fonts/
│   │       └── NotoSansMalayalam-Regular.ttf
├── temp/                       # Temporary files (PDFs, audio)
├── .env                        # Environment variables
├── bot.log                     # Application logs
└── README.md

Prerequisites

Python 3.8+
MongoDB (local or cloud instance)
Google Cloud account with API keys for Gemini, Translate, and Text-to-Speech
Tesseract OCR installed (Windows: add to PATH)
n8n installed for workflow automation
Conda or virtualenv for environment management

Setup Instructions

Clone the Repository:
git clone https://github.com/your-repo/aarogyaai.git
cd aarogyaai


Set Up Environment:

Create and activate a virtual environment:conda create -n venv python=3.8
conda activate venv


Install dependencies:pip install pymongo google-cloud-translate google-generativeai python-telegram-bot reportlab google-cloud-texttospeech httpx pdf2image pytesseract




Configure Environment Variables:

Create a .env file in the root directory:TELEGRAM_BOT_TOKEN=your_telegram_bot_token
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/google-credentials.json
MONGODB_URI=mongodb://localhost:27017
GEMINI_API_KEY=your_gemini_api_key
N8N_WEBHOOK_URL=http://localhost:5678/webhook/diet-plan-text
DIAGNOSTIC_MODE=True


Update GOOGLE_APPLICATION_CREDENTIALS and GEMINI_API_KEY with your credentials.


Set Up MongoDB:



Install Fonts:

Download NotoSansMalayalam-Regular.ttf from GitHub.
Place it in src/utils/fonts/.


Set Up Tesseract OCR:

Windows: Download from GitHub and add to PATH.
Configure in src/input_processing/ocr.py:pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"




Start n8n:

Install and run n8n:npm install -g n8n
n8n start


Ensure the diet_plan_text workflow is active at http://localhost:5678.


Run the Bot:
python -m src.bot.telegram_bot



Usage

Start Interaction:

Send /start to select a language and complete user setup (name, age, allergies).
Example: Select Malayalam, enter name "Haaa", age, and allergies (e.g., "None").


Health Queries:

Send voice or text queries (e.g., "തലവേദന" for headache).
Response: Currently returns a placeholder message.


Diet Plan Generation:

Send /dietplan and choose:
Option 1: Upload a medical report (PDF/image) to extract conditions (e.g., diabetes) and receive a personalized diet plan PDF.
Option 2: Specify a condition (e.g., "diabetic") to get a 7-day diet plan PDF.
Option 3: Request a general diet plan.


Output: A PDF (e.g., temp/Diet_Plan_5267655631.pdf) with structured tables in the user’s language (e.g., Malayalam), including culturally relevant meals.


Medicine Instructions:

Upload a prescription to receive localized usage instructions.


Predictive Analysis:

Input lifestyle and medical data to receive health risk assessments (feature under development).



Example Workflow

User: Sends /dietplan, selects option 2, enters "diabetic".
Bot: Generates a Malayalam PDF with:
Title: "വ്യക്തിഗത ഡയറ്റ് പ്ലാൻ"
User Info: "Name: Haaa | Age: Unknown | Condition: Diabetes"
7-Day Plan: Tables with meals (e.g., Breakfast: "2 ഗോതമ്പ് ദോശ, 1 കപ്പ് സാമ്പാർ")
Notes: "നിന്റെ ഭക്ഷണ സമയം സ്ഥിരമായി പാലിക്കുക."



Troubleshooting

MongoDB Index Errors:

Check indexes:use aarogyaai
db.interactions.getIndexes()


Drop conflicting indexes:db.interactions.dropIndex("user_id_1_timestamp_1")




Invalid JSON Diet Plan:

Check bot.log for Gemini API responses:type bot.log | findstr "Raw Gemini response"


Test Gemini API:import google.generativeai as genai
genai.configure(api_key="your_gemini_api_key")
model = genai.GenerativeModel("gemini-1.5-pro")
prompt = "..."
print(model.generate_content(prompt).text)




OCR Issues:

Test OCR:from src.input_processing.ocr import extract_text_from_pdf
print(extract_text_from_pdf("test_report.pdf"))




PDF Rendering Issues:

Verify NotoSansMalayalam-Regular.ttf in src/utils/fonts/.
Check bot.log for ReportLab errors.



Contributing

Fork the repository and submit pull requests for bug fixes or new features.
Report issues via GitHub Issues, including bot.log and MongoDB outputs.

License
This project is licensed under the MIT License.
Contact
For inquiries, contact the development team at [mohammadmishal430@gmail.com].
