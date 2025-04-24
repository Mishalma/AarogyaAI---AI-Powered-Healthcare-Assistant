# test_pdf.py
import asyncio
from src.utils.pdf_generator import generate_pdf
async def test():
    path = await generate_pdf("നിന്റെ പേര് എന്താണ്?", "test_ml.pdf", language="ml")
    print(path)
asyncio.run(test())