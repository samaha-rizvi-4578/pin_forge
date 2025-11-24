import google.generativeai as genai
from django.conf import settings

genai.configure(api_key=settings.GOOGLE_API_KEY)


model = genai.GenerativeModel("gemini-2.5-flash")

def generate_pin_content(product_name, attributes, description):
    prompt = f"""
    Generate Pinterest Pin content in STRICT JSON ONLY.

    Product:
    - Name: {product_name}
    - Attributes: {attributes}
    - Description: {description}

    Return JSON with fields:
    {{
        "title": "...",
        "description": "...",
        "hashtags": "...",
        "alt_text": "..."
    }}

    Do NOT include markdown. No explanations.
    """

    response = model.generate_content(prompt)

    import json
    try:
        return json.loads(response.text)
    except json.JSONDecodeError:
        return {"title": "", "description": response.text, "hashtags": "", "alt_text": ""}

