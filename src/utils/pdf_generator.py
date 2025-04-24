import logging
import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT, TA_CENTER

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler("bot.log", encoding="utf-8"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def register_fonts():
    """Register TrueType fonts for supported languages."""
    font_dir = os.path.join(os.path.dirname(__file__), "fonts")
    os.makedirs(font_dir, exist_ok=True)

    font_map = {
        "ml": ("NotoSansMalayalam-Regular", "NotoSansMalayalam-Regular.ttf"),
        "hi": ("NotoSansDevanagari-Regular", "NotoSansDevanagari-Regular.ttf"),
        "ta": ("NotoSansTamil-Regular", "NotoSansTamil-Regular.ttf"),
        "te": ("NotoSansTelugu-Regular", "NotoSansTelugu-Regular.ttf"),
        "bn": ("NotoSansBengali-Regular", "NotoSansBengali-Regular.ttf"),
        "kn": ("NotoSansKannada-Regular", "NotoSansKannada-Regular.ttf"),
        "en": ("Helvetica", None)
    }

    for lang, (font_name, font_file) in font_map.items():
        if font_file:
            font_path = os.path.join(font_dir, font_file)
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont(font_name, font_path))
                    logger.info(f"Registered font: {font_name} for language {lang}")
                except Exception as e:
                    logger.error(f"Failed to register font {font_name}: {str(e)}")
            else:
                logger.warning(f"Font file {font_file} not found for language {lang}. Using Helvetica as fallback.")
        else:
            logger.debug(f"Using built-in font {font_name} for language {lang}")


async def generate_pdf(diet_plan: dict, output_filename: str, language: str = "en", user_info: dict = None) -> str:
    """
    Generate a structured PDF for a diet plan with daily meal tables.

    Args:
        diet_plan (dict): Structured diet plan with days, meals, and notes.
        output_filename (str): Name of the output PDF file.
        language (str): Language code (e.g., 'en', 'ml').
        user_info (dict): User details (name, age, condition).

    Returns:
        str: Path to the generated PDF file, or None if generation fails.
    """
    try:
        # Register fonts
        register_fonts()

        # Ensure output directory
        output_dir = os.path.join("temp")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, output_filename)

        # Initialize PDF document
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            leftMargin=0.5 * inch,
            rightMargin=0.5 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.5 * inch
        )
        styles = getSampleStyleSheet()

        # Font selection
        font_map = {
            "ml": "NotoSansMalayalam-Regular",
            "hi": "NotoSansDevanagari-Regular",
            "ta": "NotoSansTamil-Regular",
            "te": "NotoSansTelugu-Regular",
            "bn": "NotoSansBengali-Regular",
            "kn": "NotoSansKannada-Regular",
            "en": "Helvetica"
        }
        font_name = font_map.get(language, "Helvetica")

        # Custom styles
        title_style = ParagraphStyle(
            name="Title",
            fontSize=18,
            leading=22,
            textColor=colors.darkblue,
            spaceAfter=12,
            fontName=font_name,
            alignment=TA_CENTER
        )
        subtitle_style = ParagraphStyle(
            name="Subtitle",
            fontSize=14,
            leading=16,
            textColor=colors.black,
            spaceAfter=8,
            fontName=font_name,
            alignment=TA_LEFT
        )
        body_style = ParagraphStyle(
            name="Body",
            fontSize=11,
            leading=13,
            spaceAfter=6,
            fontName=font_name,
            alignment=TA_LEFT,
            wordWrap="CJK"
        )
        table_header_style = ParagraphStyle(
            name="TableHeader",
            fontSize=12,
            leading=14,
            textColor=colors.white,
            fontName=font_name,
            alignment=TA_LEFT
        )

        # Translate title if needed
        title_text = "Personalized Diet Plan"
        if language != "en":
            from src.input_processing.translation import translate_text
            title_text = await translate_text("Personalized Diet Plan", "en", language) or title_text

        # Build content
        story = []

        # Header
        story.append(Paragraph(title_text, title_style))
        story.append(Spacer(1, 12))

        # User info
        if user_info:
            user_text = f"Name: {user_info.get('name', 'Unknown')} | Age: {user_info.get('age', 'Unknown')} | Condition: {user_info.get('condition', 'None')}"
            if language != "en":
                user_text = await translate_text(user_text, "en", language) or user_text
            story.append(Paragraph(user_text, subtitle_style))
            story.append(Spacer(1, 12))

        # Daily meal plans
        for day, meals in diet_plan.get("days", {}).items():
            day_title = f"Day {day}"
            if language != "en":
                day_title = await translate_text(day_title, "en", language) or day_title
            story.append(Paragraph(day_title, subtitle_style))
            story.append(Spacer(1, 6))

            # Table for meals
            table_data = [["Time", "Meal", "Details"]]
            for meal in meals:
                time = meal.get("time", "")
                meal_type = meal.get("type", "")
                details = meal.get("details", "")
                if language != "en" and meal_type:
                    meal_type = await translate_text(meal_type, "en", language) or meal_type
                table_data.append([
                    Paragraph(time, body_style),
                    Paragraph(meal_type, body_style),
                    Paragraph(details, body_style)
                ])

            table = Table(table_data, colWidths=[1.5 * inch, 1.5 * inch, 4.0 * inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), font_name),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(table)
            story.append(Spacer(1, 12))

        # Notes section
        notes = diet_plan.get("notes", "")
        if notes:
            notes_title = "Additional Notes"
            if language != "en":
                notes_title = await translate_text(notes_title, "en", language) or notes_title
            story.append(Paragraph(notes_title, subtitle_style))
            story.append(Spacer(1, 6))
            story.append(Paragraph(notes, body_style))
            story.append(Spacer(1, 12))

        # Footer template
        def add_footer(canvas, doc):
            canvas.saveState()
            footer_text = f"Generated on {datetime.now().strftime('%Y-%m-%d')} | Page {doc.page}"
            canvas.setFont(font_name, 10)
            canvas.drawCentredString(letter[0] / 2, 0.25 * inch, footer_text)
            canvas.restoreState()

        # Build PDF
        doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
        logger.info(f"Generated PDF: {output_path} for language {language}")
        return output_path
    except Exception as e:
        logger.error(f"Error generating PDF {output_filename} for language {language}: {str(e)}", exc_info=True)
        return None