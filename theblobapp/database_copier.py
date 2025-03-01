import shutil
import os
import time
import threading
import logging
import sqlite3
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class DatabaseCopier:
    def __init__(self, source_path, update_interval=30):  # Changed default to 30 seconds
        self.source_path = source_path
        self.update_interval = update_interval
        self.data_dir = os.path.join(str(Path.home()), '.personalblobai')
        self.copy_path = os.path.join(self.data_dir, 'blob_data_copy.db')
        self._stop_event = threading.Event()
        self._copy_thread = None
        self._init_copy_database()
        
    def start(self):
        """Start the background copying process"""
        self._stop_event.clear()
        self._copy_thread = threading.Thread(target=self._copy_loop, daemon=True)
        self._copy_thread.start()
        logger.info("Database copier started")
        
    def stop(self):
        """Stop the background copying process"""
        if self._copy_thread:
            self._stop_event.set()
            self._copy_thread.join()
            logger.info("Database copier stopped")
            
    def _copy_loop(self):
        """Main copy loop that runs in background"""
        while not self._stop_event.is_set():
            try:
                self._copy_database()
                # Sleep for the update interval or until stopped
                self._stop_event.wait(self.update_interval)
            except Exception as e:
                logger.error(f"Error copying database: {e}")
                # Wait a bit before retrying on error
                time.sleep(60)
                
    def _init_copy_database(self):
        """Initialize the copy database with required schema"""
        try:
            # Create a new connection to the copy database
            with sqlite3.connect(self.copy_path) as conn:
                cursor = conn.cursor()
                
                # Create the same schema as the main database
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )''')
                
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS blobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    content_type TEXT,
                    content TEXT,
                    file_path TEXT,
                    is_public BOOLEAN DEFAULT FALSE,
                    timestamp DATETIME,
                    ai_summary TEXT,
                    embedding BLOB,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )''')
                
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS blob_likes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    blob_id INTEGER,
                    user_id INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (blob_id) REFERENCES blobs(id),
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    UNIQUE(blob_id, user_id)
                )''')
                
                conn.commit()
                logger.info("Copy database initialized with schema")
                
        except Exception as e:
            logger.error(f"Error initializing copy database: {e}")
            raise
            
    def _copy_database(self):
        """Create a copy of the database"""
        try:
            # First verify the copy database has correct schema
            with sqlite3.connect(self.copy_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                existing_tables = {row[0] for row in cursor.fetchall()}
                
                if not all(table in existing_tables for table in ['users', 'blobs', 'blob_likes']):
                    self._init_copy_database()
            
            # Now perform the copy
            shutil.copy2(self.source_path, self.copy_path)
            logger.info(f"Database copied successfully at {datetime.now()}")
            
        except Exception as e:
            logger.error(f"Failed to copy database: {e}")
            # If copy fails, ensure we at least have a working schema
            self._init_copy_database()
            
    def get_copy_path(self):
        """Get the path to the copied database"""
        return self.copy_path
