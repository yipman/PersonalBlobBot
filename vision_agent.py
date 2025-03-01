import base64
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)

def encode_image_to_base64(image_path):
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        logger.error(f"Error encoding image: {e}")
        return None

def analyze_image(image_path):
    """Analyze image using LLaVA model for detailed description and text extraction"""
    try:
        base64_image = encode_image_to_base64(image_path)
        if not base64_image:
            return "Failed to process image"

        client = OpenAI(api_key="local", base_url="http://localhost:11434/v1")
        
        prompt = (
            "Please analyze this image in detail. Provide:\n"
            "1. A detailed description of what you see\n"
            "2. Any text that appears in the image\n"
            "3. Notable objects, colors, and patterns\n"
            "4. The overall context or setting"
        )

        response = client.chat.completions.create(
            model="llava",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
        )
        
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Vision analysis error: {e}")
        return f"Failed to analyze image: {str(e)}"
