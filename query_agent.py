import logging
from openai import OpenAI
import numpy as np

logger = logging.getLogger(__name__)

def get_embedding(text):
    try:
        if not text:
            return None
            
        client = OpenAI(api_key="local", base_url="http://localhost:11434/v1")
        response = client.embeddings.create(
            model="nomic-embed-text",  # Use this specific model for embeddings
            input=text
        )
        
        if not response.data or not response.data[0].embedding:
            print("No embedding data received")
            return None
            
        embedding = np.array(response.data[0].embedding, dtype=np.float32)
        if embedding.size == 0:
            print("Empty embedding received")
            return None
            
        return embedding
    except Exception as e:
        print(f"Embedding generation error: {e}")
        return None

def query_database(question, similar_blobs, user_id):
    try:
        client = OpenAI(api_key="local", base_url="http://localhost:11434/v1")
        
        if not similar_blobs:
            logger.warning("No similar blobs provided")
            return "I couldn't find any relevant information to answer your question."
            
        # Log the data we're working with
        logger.debug(f"Processing query for user {user_id} with {len(similar_blobs)} similar blobs")
        
        # Modified context to handle image content better
        context_items = []
        for blob in similar_blobs:
            blob_id, content, content_type, summary, similarity = blob
            content_prefix = "Image Analysis:" if content_type == "photo" else "Content:"
            context_items.append(
                f"{content_prefix} ({similarity:.2f} relevance)\n"
                f"{content}\n"
                f"Summary: {summary}"
            )
        
        context = "\n\n".join(context_items)
        
        prompt = (
            f"Context from database:\n{context}\n\n"
            f"Question: {question}\n"
            "Please provide a relevant answer based on the context above."
        )
        
        response = client.chat.completions.create(
            model="llama3.2:3b",
            messages=[{"role": "user", "content": prompt}]
        )
        
        if not response.choices:
            logger.error("No response choices received from LLM")
            return "Sorry, I couldn't generate an answer."
            
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"Query processing error: {e}", exc_info=True)
        return f"Sorry, I couldn't process your question due to an error: {str(e)}"

# Keep the original function for single blob queries
def query_blob(blob_content, blob_type, question):
    try:
        client = OpenAI(api_key="local", base_url="http://localhost:11434/v1")
        
        prompt = (
            f"Context: This is a {blob_type} content:\n"
            f"{blob_content}\n\n"
            f"Question: {question}\n"
            "Please provide a relevant answer based on the content above."
        )
        
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
        print(f"Query processing error: {e}")
        return "Sorry, I couldn't process your question."
