import re
import logging

logging.basicConfig(level=logging.INFO, filename="bot.log")
logger = logging.getLogger(__name__)

def analyze_health_indicators(text):
    indicators = {
        "blood_sugar": None,
        "bp_systolic": None,
        "bp_diastolic": None,
        "cholesterol": None,
        "creatinine": None,
        "bmi": None
    }
    conditions = []

    sugar_match = re.search(r'(?i)blood\s*(sugar|glucose)\s*[:=]\s*(\d+\.?\d*)', text)
    bp_match = re.search(r'(?i)blood\s*pressure\s*[:=]\s*(\d+)/(\d+)', text)
    chol_match = re.search(r'(?i)cholesterol\s*[:=]\s*(\d+\.?\d*)', text)
    creat_match = re.search(r'(?i)creatinine\s*[:=]\s*(\d+\.?\d*)', text)
    bmi_match = re.search(r'(?i)bmi\s*[:=]\s*(\d+\.?\d*)', text)

    if sugar_match:
        indicators["blood_sugar"] = float(sugar_match.group(2))
        if indicators["blood_sugar"] > 126:
            conditions.append({"name": "Diabetes", "likelihood": "High"})
        elif 100 < indicators["blood_sugar"] <= 126:
            conditions.append({"name": "Pre-diabetes", "likelihood": "Moderate"})

    if bp_match:
        indicators["bp_systolic"] = int(bp_match.group(1))
        indicators["bp_diastolic"] = int(bp_match.group(2))
        if indicators["bp_systolic"] > 140 or indicators["bp_diastolic"] > 90:
            conditions.append({"name": "Hypertension", "likelihood": "High"})
        elif 120 <= indicators["bp_systolic"] <= 140 or 80 <= indicators["bp_diastolic"] <= 90:
            conditions.append({"name": "Pre-hypertension", "likelihood": "Moderate"})

    if chol_match:
        indicators["cholesterol"] = float(chol_match.group(1))
        if indicators["cholesterol"] > 200:
            conditions.append({"name": "High Cholesterol", "likelihood": "High"})

    if creat_match:
        indicators["creatinine"] = float(creat_match.group(1))
        if indicators["creatinine"] > 1.2:
            conditions.append({"name": "Kidney Issue", "likelihood": "Moderate"})

    if bmi_match:
        indicators["bmi"] = float(bmi_match.group(1))
        if indicators["bmi"] > 30:
            conditions.append({"name": "Obesity", "likelihood": "High"})
        elif 25 <= indicators["bmi"] <= 30:
            conditions.append({"name": "Overweight", "likelihood": "Moderate"})

    return indicators, conditions