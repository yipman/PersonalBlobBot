import logging
import warnings
import sys
import io
import os
from pathlib import Path
from queue import Queue
from kokoro import KPipeline
import soundfile as sf

logger = logging.getLogger(__name__)

class AudioGenerator:
    def __init__(self):
        self._initialized = False
        self._init()
        
    def _init(self):
        if self._initialized:
            return
            
        try:
            # Configure warnings and encoding
            warnings.filterwarnings("ignore", category=UserWarning, module="torch.nn.modules.rnn")
            warnings.filterwarnings("ignore", category=FutureWarning, module="torch.nn.utils.weight_norm")

            # Force UTF-8 encoding
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
            
            # Set environment variables
            os.environ['PYTHONUTF8'] = '1'
            os.environ['PYTHONIOENCODING'] = 'utf-8'

            # Monkey-patch builtins.open to force utf-8 encoding for .json files
            import builtins
            original_open = builtins.open
            def open_utf8(*args, **kwargs):
                if 'encoding' not in kwargs and args and isinstance(args[0], str) and args[0].endswith('.json'):
                    kwargs['encoding'] = 'utf-8'
                return original_open(*args, **kwargs)
            builtins.open = open_utf8

            # Initialize directories
            self.audio_dir = os.path.join(str(Path.home()), '.personalblobai', 'audio')
            os.makedirs(self.audio_dir, exist_ok=True)
            
            # Initialize pipeline with only supported parameters
            logger.info("Initializing Kokoro TTS Pipeline...")
            self.pipeline = KPipeline(lang_code='a')  # Removed encoding parameter
            self.audio_queue = Queue()

            # Restore the original open function to avoid side effects
            builtins.open = original_open
            
            self._initialized = True
            logger.info("Kokoro TTS Pipeline initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Kokoro: {e}")
            raise

    def generate_audio(self, text, user_id):
        """Generate audio from text and return file paths"""
        if not self._initialized:
            self._init()
            
        try:
            # Create user-specific directory
            user_audio_dir = os.path.join(self.audio_dir, str(user_id))
            os.makedirs(user_audio_dir, exist_ok=True)
            
            # Clean text and split into much larger chunks (2000 chars)
            text = text.encode('utf-8', errors='ignore').decode('utf-8')
            
            # Split on sentences to avoid cutting words
            sentences = text.replace('\n', '. ').split('. ')
            chunks = []
            current_chunk = []
            current_length = 0
            
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                    
                # If adding this sentence would exceed chunk size, save current chunk
                if current_length + len(sentence) > 4000 and current_chunk:
                    chunks.append('. '.join(current_chunk) + '.')
                    current_chunk = []
                    current_length = 0
                
                current_chunk.append(sentence)
                current_length += len(sentence) + 2  # +2 for '. '
            
            # Add remaining sentences
            if current_chunk:
                chunks.append('. '.join(current_chunk) + '.')
            
            logger.info(f"Split text into {len(chunks)} chunks for audio generation")
            
            audio_files = []
            for i, chunk in enumerate(chunks):
                try:
                    generator = self.pipeline(
                        chunk,
                        voice='af_sky',
                        speed=1
                    )
                    
                    for _, _, audio in generator:
                        if audio is not None:
                            file_path = os.path.join(user_audio_dir, f'audio_{i}.wav')
                            sf.write(file_path, audio, 24000)
                            audio_files.append(file_path)
                            break
                except Exception as chunk_error:
                    logger.error(f"Error processing chunk {i}: {chunk_error}")
                    continue
            
            return audio_files if audio_files else None
            
        except Exception as e:
            logger.error(f"Error generating audio: {e}")
            return None
