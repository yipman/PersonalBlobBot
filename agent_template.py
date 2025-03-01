import sys
import os
from openai import OpenAI

def main():
    if len(sys.argv) != 3:
        print("Usage: python agent_script.py <agent_icon> <task>")
        sys.exit(1)

    agent_icon = sys.argv[1]
    task = sys.argv[2]
    print(f"Executing agent {agent_icon} for task: {task}")

    try:
         # Local OpenAI compatible API URL
        client = OpenAI(api_key="local", base_url="http://localhost:11434/v1")

        response = client.chat.completions.create(
            model="llama3.2:3b",  # Ollama Model Name
            messages=[
                {
                    "role": "user",
                    "content": f"The agent {agent_icon} needs to perform this task: {task}. Please explain this task for the agent."
                }
            ],
            )
        print(response.choices[0].message.content)
    except Exception as e:
        print(f"An error occurred: {e}")

    print(f"Agent {agent_icon} has completed the task: {task}")

if __name__ == "__main__":
    main()