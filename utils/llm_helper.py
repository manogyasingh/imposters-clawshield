import base64
import json
import os
from openai import OpenAI

from utils.config import (
    OPENROUTER_API_BASE,
    OPENROUTER_API_KEY,
    OPENROUTER_VISION_MODEL,
)


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def detect_form_fields(image_path, api_base=None, api_key=None, model=None):
    """
    Sends the image to OpenRouter to detect form fields.
    Returns a list of dicts: {'label': str, 'box_2d': [x1, y1, x2, y2]}
    Coordinates are normalized 0-1000.
    """
    api_base = api_base or OPENROUTER_API_BASE
    api_key = api_key or OPENROUTER_API_KEY
    model = model or OPENROUTER_VISION_MODEL

    if image_path.startswith("file://"):
        image_path = image_path.replace("file://", "")

    base64_image = encode_image(image_path)

    if not api_key:
        print("Warning: No OPENROUTER_API_KEY configured.")
        return []

    client = OpenAI(base_url=api_base, api_key=api_key)

    prompt = (
        "You are an expert Intelligent Document Processing (IDP) engine specializing in form layout analysis and optical character recognition.\n\n"
        "**YOUR GOAL:**\n"
        "Analyze the provided image of a form and detect the exact bounding box coordinates for every \"Input Field.\"\n\n"
        "**DEFINITION OF \"INPUT FIELD\":**\n"
        "An Input Field is any visual element where a user is expected to enter data or make a selection. You must look for three specific visual patterns:\n"
        "1.  **Text Box Containers:** Rectangular outlines or shaded boxes containing empty whitespace.\n"
        "2.  **Text Lines:** Horizontal underlines (solid or dotted) meant for handwriting text.\n"
        "3.  **Selection Mechanisms:** Checkboxes (square), radio buttons (circular), or comb fields (segmented boxes for individual characters).\n\n"
        "**STRICT CONSTRAINTS:**\n"
        "1.  **Exclusion:** Do NOT include the field label in the bounding box. (e.g., If the form says \"Name: [_____]\", box ONLY the \"[_____]\" area. Exclude the word \"Name:\").\n"
        "2.  **Margin:** Leave a small visual MARGIN between the label text and the start of the bounding box. Do not let the box touch the label.\n"
        "3.  **Line Alignment:** For horizontal lines (underscores), the bounding box should cover the empty space *immediately above* the line (where text is written) and the line itself. Do not position it too high or too low.\n"
        "4.  **Tightness:** The bounding box must be tightly cropped to the visual boundaries of the input area (width-wise), but tall enough to contain handwriting.\n"
        "5.  **Coordinate Format:** Return coordinates on a **0-1000 integer scale**. Format: `[xmin, ymin, xmax, ymax]`. Example: `[100, 200, 500, 250]`.\n"
        "6.  **Granularity:** If there is a \"Comb Field\" (multiple small boxes for one ID number), create ONE bounding box for the entire group, not individual boxes for each character.\n\n"
        "**OUTPUT FORMAT:**\n"
        "Return ONLY a valid JSON object containing a list of fields. Do not include markdown formatting (like ```json). Use the following schema:\n\n"
        "{\n"
        "  \"form_fields\": [\n"
        "    {\n"
        "      \"id\": \"field_001\",\n"
        "      \"label_text\": \"The text label associated with this field (e.g. 'Name', 'DOB')\",\n"
        "      \"type\": \"text_box | text_line | checkbox\",\n"
        "      \"bbox_2d\": [xmin, ymin, xmax, ymax]\n"
        "    }\n"
        "  ]\n"
        "}"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
            max_tokens=1024,
        )
        
        content = response.choices[0].message.content
        print(f"LLM Response: {content}") # Debugging
        
        # Cleanup markdown if present
        content = content.replace("```json", "").replace("```", "").strip()
        
        try:
            data = json.loads(content)
            raw_fields = data.get("form_fields", [])
            
            # Normalize to our internal format: {'label': id, 'box_2d': [x1, y1, x2, y2]}
            processed_fields = []
            for f in raw_fields:
                bbox = f.get('bbox_2d')
                if bbox and len(bbox) == 4:
                    # Input is [xmin, ymin, xmax, ymax]
                    xmin, ymin, xmax, ymax = bbox
                    processed_fields.append({
                        'label': f.get('label_text') or f.get('id', 'unknown'),
                        'box_2d': [xmin, ymin, xmax, ymax],
                        'type': f.get('type')
                    })
            return processed_fields
        except json.JSONDecodeError:
            print(f"Failed to parse JSON: {content}")
            # Try to find JSON object in the string if there's extra text
            try:
                start = content.find('{')
                end = content.rfind('}') + 1
                if start != -1 and end != -1:
                    json_str = content[start:end]
                    data = json.loads(json_str)
                    raw_fields = data.get("form_fields", [])
                    processed_fields = []
                    for f in raw_fields:
                        bbox = f.get('bbox_2d')
                        if bbox and len(bbox) == 4:
                            xmin, ymin, xmax, ymax = bbox
                            processed_fields.append({
                                'label': f.get('label_text') or f.get('id', 'unknown'),
                                'box_2d': [xmin, ymin, xmax, ymax],
                                'type': f.get('type')
                            })
                    return processed_fields
            except:
                pass
            return []

    except Exception as e:
        print(f"Exception calling Local LLM: {e}")
        return []
