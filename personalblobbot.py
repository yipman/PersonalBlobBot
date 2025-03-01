import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from config import BOT_TOKEN
from database import BlobDatabase
from summary_agent import generate_summary
import os
from query_agent import query_blob, get_embedding, query_database
from vision_agent import analyze_image
from pathlib import Path
import re  # Add this import at the top
from openai import OpenAI
from datetime import datetime
from audio_agent import AudioGenerator

# Add these constants near the top
MAX_MESSAGE_LENGTH = 4096
SPLIT_MARKER = "\n\n"

# Add this helper function
async def split_and_send_message(message, text, reply_markup=None):
    """Split long messages and send them in chunks"""
    try:
        if len(text) <= MAX_MESSAGE_LENGTH:
            return await message.reply_text(text, reply_markup=reply_markup)
            
        parts = []
        current_part = ""
        
        # Split on paragraphs
        paragraphs = text.split(SPLIT_MARKER)
        
        for paragraph in paragraphs:
            if len(current_part) + len(paragraph) + len(SPLIT_MARKER) <= MAX_MESSAGE_LENGTH:
                current_part += (SPLIT_MARKER if current_part else "") + paragraph
            else:
                if current_part:
                    parts.append(current_part)
                current_part = paragraph
                
        if current_part:
            parts.append(current_part)
            
        # Send all parts except the last one
        for part in parts[:-1]:
            await message.reply_text(part)
            
        # Send last part with the reply markup
        return await message.reply_text(parts[-1], reply_markup=reply_markup)
            
    except Exception as e:
        logger.error(f"Error splitting message: {e}")
        return None

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

try:
    db = BlobDatabase()
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")
    exit(1)

# Add status emotes
STATUS_EMOTES = {
    'thinking': '🤔',
    'storing': '💾',
    'success': '✅',
    'error': '❌',
    'searching': '🔍',
    'processing': '⚙️',
    'sharing': '🌐',
    'listing': '📋',
    'question': '❓'
}

# Replace existing DOWNLOADS_DIR definition with:
PERSONALBLOBAI_DIR = os.path.join(str(Path.home()), '.personalblobai')

def get_user_storage_dir(user_id, storage_type='downloads'):
    """Get user-specific storage directory inside .personalblobai"""
    try:
        # Ensure base directory exists
        os.makedirs(PERSONALBLOBAI_DIR, exist_ok=True)
        
        # Create user directory
        user_dir = os.path.join(PERSONALBLOBAI_DIR, str(user_id))
        os.makedirs(user_dir, exist_ok=True)
        
        # Create storage type directory (downloads, documents, etc.)
        storage_dir = os.path.join(user_dir, storage_type)
        os.makedirs(storage_dir, exist_ok=True)
        
        logger.info(f"Using {storage_type} directory for user {user_id}: {storage_dir}")
        return storage_dir
    except Exception as e:
        logger.error(f"Error creating user storage directory: {e}")
        raise

async def send_status(message, status_type, text, reply_markup=None):
    """Send or edit a status message with appropriate emote and optional keyboard"""
    emote = STATUS_EMOTES.get(status_type, '')
    try:
        # Add audio button if keyboard exists
        if reply_markup and isinstance(reply_markup, InlineKeyboardMarkup):
            keyboard = list(reply_markup.inline_keyboard)
            if ':' in str(keyboard):
                first_button = keyboard[0][0]
                if hasattr(first_button, 'callback_data') and ':' in first_button.callback_data:
                    existing_id = first_button.callback_data.split(':')[1]
                    keyboard.append([
                        InlineKeyboardButton("🔊 Listen", callback_data=f"audio:{existing_id}")
                    ])
                    reply_markup = InlineKeyboardMarkup(keyboard)
        
        return await split_and_send_message(
            message,
            f"{emote} {text}",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error sending status: {e}")
        return None

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        'Hello! I am your Personal Blob AI assistant. I can help you store and manage '
        'all kinds of information in your private MyBlob or share it to TheBlob public space. '
        'Use /help to see what I can do!'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        'Available commands:\n'
        '/start - Start interacting with Personal Blob AI\n'
        '/help - Show this help message\n'
        '/store - Store information to MyBlob (private)\n'
        '/share - Share information to TheBlob (public)\n'
        '/unshare - Remove blob from TheBlob (make private)\n'
        '/ask - Ask me questions about stored information\n'
        '/theblob - Get link to TheBlob website\n'
        '\nI can handle text, images, videos, documents, and more!'
    )
    await update.message.reply_text(help_text)

async def ask_with_scope_buttons(msg, question: str):
    """Show buttons for MyBlob/TheBlob search scope"""
    keyboard = [
        [
            InlineKeyboardButton("Search MyBlob (Private)", callback_data=f"ask_private:{question}"),
            InlineKeyboardButton("Search TheBlob (Public)", callback_data=f"ask_public:{question}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await msg.reply_text(
        "Where would you like to search for the answer?",
        reply_markup=reply_markup
    )

async def parse_deep_thinking(response_text):
    """Parse structured deep thinking response"""
    try:
        # Extract thoughts and answer using regex
        thoughts_match = re.search(r'<think>(.*?)</think>', response_text, re.DOTALL)
        thoughts = thoughts_match.group(1).strip() if thoughts_match else ""
        
        # Get final answer (everything after </think>)
        answer = re.split(r'</think>', response_text)[-1].strip()
        
        # Format the response nicely
        formatted_response = (
            "🤔 Deep Thinking Process:\n"
            "━━━━━━━━━━━━━━━━━\n"
            f"{thoughts}\n\n"
            "📝 Final Analysis:\n"
            "━━━━━━━━━━━━━━━━━\n"
            f"{answer}"
        )
        return formatted_response
    
    except Exception as e:
        logger.error(f"Error parsing deep thinking response: {e}")
        return response_text  # Return original text if parsing fails

async def deep_think(content, user_id):
    """Perform deep thinking analysis using semantic search"""
    try:
        # Generate embedding for content
        content_embedding = get_embedding(content)
        if content_embedding is None or not content_embedding.any():
            return "Unable to analyze content semantically."
        
        # Search both private and public content
        private_blobs = db.search_similar_blobs(content_embedding, user_id, limit=6, public_only=False)
        public_blobs = db.search_similar_blobs(content_embedding, user_id, limit=6, public_only=True)
        
        # Format prompt with related content
        prompt_parts = ["Related information found:"]
        
        if private_blobs:
            prompt_parts.append("\nFrom private knowledge:")
            for _, content, _, summary, _ in private_blobs:
                if summary:
                    prompt_parts.append(f"- {summary}")
                else:
                    prompt_parts.append(f"- {content[:200]}...")
        
        if public_blobs:
            prompt_parts.append("\nFrom public knowledge:")
            for _, content, _, summary, _ in public_blobs:
                if summary:
                    prompt_parts.append(f"- {summary}")
                else:
                    prompt_parts.append(f"- {content[:200]}...")
        
        # Generate deep analysis with structured format
        client = OpenAI(api_key="local", base_url="http://localhost:11434/v1")
        prompt = (
            f"Content to analyze:\n{content}\n\n"
            f"{' '.join(prompt_parts)}\n\n"
            "Please provide a deep analysis considering:\n"
            "1. Key insights from the content to analyze\n"
            "2. Connections with related information found\n"
            "3. Potential implications or applications\n"
            "4. Critical thinking points"
        )
        
        response = client.chat.completions.create(
            model="deepseek-r1:1.5b",
            messages=[{"role": "user", "content": prompt}]
        )
        
        raw_response = response.choices[0].message.content
        return await parse_deep_thinking(raw_response)
        
    except Exception as e:
        logger.error(f"Deep thinking error: {e}")
        return "Sorry, I couldn't perform deep analysis at this time."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user = msg.from_user
    
    try:
        # Ensure user exists in database and get downloads directory
        db.ensure_user_exists(
            user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        user_downloads_dir = get_user_storage_dir(user.id)
        logger.info(f"Using storage directory: {user_downloads_dir}")
        
        # Check if message ends with "?" for text messages
        if msg.text and msg.text.strip().endswith('?'):
            logger.info("Question detected, showing options")
            keyboard = [
                [
                    InlineKeyboardButton("Store this question", callback_data=f"store:{msg.text}"),
                    InlineKeyboardButton("Search MyBlob", callback_data=f"ask_private:{msg.text}"),
                    InlineKeyboardButton("Search TheBlob", callback_data=f"ask_public:{msg.text}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await msg.reply_text(
                "I noticed you asked a question! What would you like to do?", 
                reply_markup=reply_markup
            )
            return

        status_msg = await send_status(msg, 'processing', "Processing your message...")
        
        try:
            # Handle different types of content
            if msg.text and not msg.text.startswith('/'):
                content_type = 'text'
                content = msg.text
                file_path = ''
                logger.info(f"Received text message: {content[:50]}...")
            elif msg.photo:
                content_type = 'photo'
                file = await msg.photo[-1].get_file()
                file_name = f"photo_{msg.photo[-1].file_unique_id}.jpg"
                file_path = os.path.join(user_downloads_dir, file_name)
                logger.info(f"Downloading photo to {file_path}")
                
                try:
                    # Ensure the directory exists
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    await file.download_to_drive(file_path)
                    logger.info(f"Photo downloaded successfully to {file_path}")
                except Exception as download_error:
                    logger.error(f"Error downloading photo: {download_error}")
                    raise
                
                # Analyze image with vision agent
                await send_status(msg, 'thinking', "Analyzing image...")
                vision_analysis = analyze_image(file_path)
                content = f"Image Analysis:\n{vision_analysis}\n"
                if msg.caption:
                    content += f"\nCaption: {msg.caption}"
                
                logger.info("Image analysis completed")
            elif msg.document:
                content_type = 'document'
                file = await msg.document.get_file()
                file_name = f"doc_{msg.document.file_unique_id}_{msg.document.file_name}"
                file_path = os.path.join(user_downloads_dir, file_name)
                logger.info(f"Downloading document to {file_path}")
                
                try:
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    await file.download_to_drive(file_path)
                    logger.info(f"Document downloaded successfully to {file_path}")
                except Exception as download_error:
                    logger.error(f"Error downloading document: {download_error}")
                    raise
            else:
                logger.warning(f"Unsupported content type from user {user.id}")
                await msg.reply_text("Sorry, this type of content is not supported yet.")
                return

            # Generate embedding for the content
            embedding = get_embedding(content)

            await send_status(msg, 'storing', "Storing in MyBlob...")
            # Store in MyBlob with embedding
            logger.info(f"Storing {content_type} content for user {user.id}")
            blob_id = db.store_blob(user.id, content_type, content, file_path, embedding=embedding)
            
            await send_status(msg, 'thinking', "Generating AI summary...")
            # Generate and store AI summary
            logger.info(f"Generating AI summary for blob {blob_id}")
            summary = generate_summary(content, content_type)
            db.update_summary(blob_id, summary)
            
            keyboard = [
                [
                    InlineKeyboardButton("Share to TheBlob", callback_data=f"share:{blob_id}"),
                    InlineKeyboardButton("Deep Think 🤔", callback_data=f"think:{blob_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await send_status(msg, 'success', 
                f"Content stored in MyBlob with ID {blob_id}!\n"
                f"Here's the AI summary:\n{summary}\n\n"
                f"Would you like to share this blob or perform deep analysis?",
                reply_markup=reply_markup
            )
            logger.info(f"Successfully processed and stored blob {blob_id}")
        except Exception as e:
            await status_msg.delete() if status_msg else None
            await send_status(msg, 'error', f"An error occurred: {e}")
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        await send_status(msg, 'error', f"An error occurred: {e}")

# Add this near the top with other global variables
TEMP_ANALYSES = {}  # Store temporary analyses with unique IDs
audio_gen = AudioGenerator()

async def send_audio_files(msg, audio_files):
    """Send multiple audio files as voice messages"""
    for file_path in audio_files:
        try:
            with open(file_path, 'rb') as audio:
                await msg.reply_voice(audio)
            os.remove(file_path)  # Clean up after sending
        except Exception as e:
            logger.error(f"Error sending audio: {e}")

# Update button_callback to handle error properly
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
        action, data = query.data.split(':', 1)
        logger.info(f"Processing button callback: {action} for data: {data}")
        
        if action == "audio":
            # Get the content to convert to audio
            if data.startswith('a'):  # Analysis ID format: a{timestamp}-{user_id}
                if data not in TEMP_ANALYSES:
                    await query.message.reply_text("Analysis expired or not found. Please try again.")
                    return
                content = TEMP_ANALYSES[data]
            else:
                # Handle regular blob ID
                try:
                    blob_id = int(data)
                    blob = db.get_blob_by_id(blob_id, query.from_user.id)
                    if not blob:
                        await query.message.reply_text("Content not found or access denied.")
                        return
                        
                    # Use the AI summary if this was a summary message
                    if "Here's the AI summary" in query.message.text:
                        content = blob[7]  # Get summary from blob
                        if not content:
                            content = "Summary not available."
                    else:
                        content = blob[3]  # Get original content
                except ValueError:
                    await query.message.reply_text("Invalid content ID")
                    return
            
            status_msg = await send_status(query.message, 'processing', "Generating audio...")
            
            # Generate and send audio
            audio_files = audio_gen.generate_audio(content, query.from_user.id)
            if audio_files:
                await send_audio_files(query.message, audio_files)
                await status_msg.delete()
            else:
                await status_msg.edit_text("❌ Failed to generate audio")
        elif action == "think":
            # Handle deep thinking request
            blob_id = int(data)
            blob = db.get_blob_by_id(blob_id, query.from_user.id)
            if not blob:
                await query.message.reply_text("Content not found or access denied.")
                return
                
            thinking_msg = await send_status(query.message, 'thinking', 
                "Performing deep analysis considering related information...")
            
            analysis = await deep_think(blob[3], query.from_user.id)
            
            # Generate unique ID for this analysis
            analysis_id = f"a{datetime.now().strftime('%Y%m%d%H%M%S')}-{query.from_user.id}"
            TEMP_ANALYSES[analysis_id] = analysis  # Store analysis temporarily
            
            # Add summarize button with just the ID
            keyboard = [
                [
                    InlineKeyboardButton("Summarize Analysis 📋", callback_data=f"summarize:{analysis_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await thinking_msg.delete() if thinking_msg else None
            await send_status(query.message, 'success', analysis, reply_markup=reply_markup)
            
        elif action == "summarize":
            # Process the deep thinking result using its ID
            analysis_id = data
            if analysis_id not in TEMP_ANALYSES:
                await query.message.reply_text("Analysis expired or not found. Please try again.")
                return
                
            thinking_content = TEMP_ANALYSES[analysis_id]
            del TEMP_ANALYSES[analysis_id]  # Clean up temporary storage
            
            status_msg = await send_status(query.message, 'processing', "Storing analysis as new blob...")
            
            try:
                # Generate embedding for the analysis
                embedding = get_embedding(thinking_content)
                
                # Store as new blob
                blob_id = db.store_blob(
                    query.from_user.id, 
                    'analysis', 
                    thinking_content, 
                    embedding=embedding
                )
                
                # Generate summary
                summary = generate_summary(thinking_content, 'analysis')
                db.update_summary(blob_id, summary)
                
                # Add share button to the new blob
                keyboard = [
                    [
                        InlineKeyboardButton("Share to TheBlob", callback_data=f"share:{blob_id}")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await status_msg.delete() if status_msg else None
                await send_status(
                    query.message, 
                    'success',
                    f"Analysis stored as blob {blob_id}!\n\n"
                    f"Summary:\n{summary}\n\n"
                    f"Would you like to share this analysis?",
                    reply_markup=reply_markup
                )
                
            except Exception as e:
                await status_msg.delete() if status_msg else None
                await send_status(query.message, 'error', f"Error storing analysis: {e}")
        elif action == "share":
            # Handle share button press
            blob_id = int(data)
            user_id = query.from_user.id
            
            try:
                db.update_publicity(blob_id, True, user_id)
                await query.message.edit_text(
                    f"{query.message.text}\n\n✨ Successfully shared to TheBlob!"
                )
                logger.info(f"User {user_id} shared blob {blob_id} to TheBlob")
            except ValueError as ve:
                await query.message.reply_text(str(ve))
            except Exception as e:
                await query.message.reply_text(f"An error occurred while sharing: {e}")
        elif action in ["ask_private", "ask_public"]:
            # Handle scoped queries
            await handle_scoped_query(
                query.message, 
                query.from_user.id, 
                data, 
                scope='public' if action == "ask_public" else 'private'
            )
            
    except Exception as e:
        logger.error(f"Error processing button callback: {e}")
        await query.message.reply_text(f"An error occurred: {e}")

async def share_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user_id = msg.from_user.id
    
    if not context.args:
        await msg.reply_text("Please provide the blob ID to share")
        return
    
    try:
        blob_id = int(context.args[0])
        db.update_publicity(blob_id, True, user_id)  # Pass user_id here
        await msg.reply_text(f"Blob {blob_id} has been shared to TheBlob!")
    except ValueError as ve:
        await msg.reply_text(str(ve))
    except Exception as e:
        await msg.reply_text(f"An error occurred: {e}")

async def unshare_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user_id = msg.from_user.id
    
    if not context.args:
        await msg.reply_text("Please provide the blob ID to unshare. Usage: /unshare <blob_id>")
        return
    
    try:
        blob_id = int(context.args[0])
        db.update_publicity(blob_id, False, user_id)  # Set is_public to False
        await msg.reply_text(f"Blob {blob_id} has been removed from TheBlob and is now private!")
    except ValueError as ve:
        await msg.reply_text(str(ve))
    except Exception as e:
        await msg.reply_text(f"An error occurred: {e}")

async def list_blobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    blobs = db.get_user_blobs(user_id)
    
    if not blobs:
        await update.message.reply_text("You don't have any stored blobs yet!")
        return
        
    response = "Your stored blobs:\n\n"
    for blob in blobs:
        username = blob[8] or "Unknown"  # Get username from joined query
        ownership = "Your blob" if blob[1] == user_id else f"Public blob by {username}"
        response += (
            f"ID: {blob[0]}\n"
            f"Type: {blob[2]}\n"
            f"Summary: {blob[7]}\n"
            f"Status: {ownership}\n"
            f"{'Public' if blob[5] else 'Private'}\n\n"
        )
    
    await update.message.reply_text(response)

async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE, *, from_callback=False):
    if not update or not update.message:
        logger.error("Received empty update or message")
        return
        
    msg = update.message
    if not msg.from_user:
        await msg.reply_text("Error: Could not identify user")
        return
        
    user_id = msg.from_user.id
    
    # Handle specific blob queries differently
    if context.args and context.args[0].isdigit():
        blob_id = int(context.args[0])
        question = ' '.join(context.args[1:])
        # ...existing specific blob query handling...
        return
        
    # For general queries, show scope selection
    question = ' '.join(context.args)
    if not question:
        await msg.reply_text("Please provide a question to ask")
        return
        
    await ask_with_scope_buttons(msg, question)

async def handle_scoped_query(msg, user_id, question, scope):
    """Handle query with specific scope (private/public)"""
    status_msg = await send_status(msg, 'thinking', "Processing your question...")
    
    try:
        logger.info(f"Processing {scope} ask command for user {user_id}")
        query_embedding = get_embedding(question)
        
        if query_embedding is None:
            await status_msg.delete() if status_msg else None
            await send_status(msg, 'error', "Sorry, I couldn't process your question.")
            return
            
        # Search with appropriate scope
        if scope == 'private':
            await send_status(msg, 'searching', "Searching through your private content...")
            similar_blobs = db.search_similar_blobs(query_embedding, user_id, public_only=False)
            search_context = "MyBlob"
        else:
            await send_status(msg, 'searching', "Searching through public content...")
            similar_blobs = db.search_similar_blobs(query_embedding, user_id, public_only=True)
            search_context = "TheBlob"
            
        logger.info(f"Found {len(similar_blobs)} similar blobs in {search_context}")
        
        if not similar_blobs:
            await status_msg.delete() if status_msg else None
            await send_status(msg, 'error', f"I couldn't find any relevant information in {search_context}.")
            return
            
        await send_status(msg, 'processing', "Generating answer...")
        answer = query_database(question, similar_blobs, user_id)
        await status_msg.delete() if status_msg else None
        await send_status(msg, 'success', f"Q: {question}\n\nA: {answer}")
            
    except Exception as e:
        logger.error(f"Error in handle_scoped_query: {e}", exc_info=True)
        await status_msg.delete() if status_msg else None
        await send_status(msg, 'error', f"An error occurred: {e}")

async def store_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user_id = msg.from_user.id
    
    # Get the text after the command
    content = ' '.join(context.args) if context.args else ''
    
    if not content:
        await msg.reply_text("Please provide some text to store. Usage: /store your message here")
        return
        
    logger.info(f"Storing text content for user {user_id}")
    
    status_msg = await send_status(msg, 'storing', "Storing your content...")
    try:
        # Generate embedding for the content
        embedding = get_embedding(content)

        # Store in MyBlob with embedding
        blob_id = db.store_blob(user_id, 'text', content, embedding=embedding)
        
        # Generate and store AI summary
        logger.info(f"Generating AI summary for blob {blob_id}")
        summary = generate_summary(content, 'text')
        db.update_summary(blob_id, summary)
        
        keyboard = [
            [
                InlineKeyboardButton("Share to TheBlob", callback_data=f"share:{blob_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await send_status(msg, 'success', 
            f"Content stored in MyBlob with ID {blob_id}!\n"
            f"Here's the AI summary:\n{summary}\n\n"
            f"Would you like to share this blob with the public?",
            reply_markup=reply_markup
        )
        logger.info(f"Successfully processed and stored blob {blob_id}")
    except Exception as e:
        await status_msg.delete() if status_msg else None
        await send_status(msg, 'error', f"An error occurred: {e}")

async def reprocess_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user_id = msg.from_user.id
    
    # Only allow admin users to reprocess embeddings
    # You might want to add proper admin check here
    logger.info(f"Reprocess command received from user {user_id}")
    
    try:
        await msg.reply_text("Starting embedding reprocessing...")
        processed = db.reprocess_embeddings(get_embedding)
        await msg.reply_text(f"Reprocessing complete. Updated {processed} blobs with new embeddings.")
    except Exception as e:
        logger.error(f"Error during reprocessing: {e}")
        await msg.reply_text(f"An error occurred during reprocessing: {e}")

async def theblob_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show link to TheBlob website"""
    await update.message.reply_text(
        "🌐 Visit TheBlob website to see all public content:\n"
        "http://theblob.uniwork.com.ar:5000/",
        disable_web_page_preview=False  # Allow link preview
    )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    logger.info("Bot application initialized")

    # Add command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("store", store_command))
    app.add_handler(CommandHandler("share", share_command))
    app.add_handler(CommandHandler("unshare", unshare_command))  # Add this line
    app.add_handler(CommandHandler("list", list_blobs))
    app.add_handler(CommandHandler("ask", ask_command))
    app.add_handler(CommandHandler("reprocess", reprocess_command))
    app.add_handler(CommandHandler("theblob", theblob_command))
    
    # Add callback query handler for inline buttons
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Add message handlers for both text and media content
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.PHOTO | filters.Document.ALL) & ~filters.COMMAND,
        handle_message
    ))

    # Start the bot
    logger.info("Starting Personal Blob AI...")
    app.run_polling()

if __name__ == '__main__':
    main()