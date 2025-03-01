from openai import OpenAI

def generate_summary(content, content_type):
    try:
        client = OpenAI(api_key="local", base_url="http://localhost:11434/v1")
        
        prompt = f"Please provide a brief summary of this {content_type}: {content}"
        
        response = client.chat.completions.create(
            model="llama3.2:3b",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
        )
        
        return response.choices[0].message.content
    except Exception as e:
        print(f"Summary generation error: {e}")
        return "Failed to generate summary"
