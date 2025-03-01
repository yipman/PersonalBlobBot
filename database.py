import sqlite3
from datetime import datetime
import os
from pathlib import Path
import logging
import numpy as np
from numpy.linalg import norm

logger = logging.getLogger(__name__)

class BlobDatabase:
    def __init__(self):
        # Use user's home directory for data storage
        self.data_dir = os.path.join(str(Path.home()), '.personalblobai')
        logger.info(f"Initializing database in directory: {self.data_dir}")
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Set up database path
        self.db_path = os.path.join(self.data_dir, 'blob_data.db')
        try:
            self.conn = sqlite3.connect(self.db_path)
            logger.info(f"Database connected successfully at: {self.db_path}")
            self.create_tables()
            self.migrate_database()  # Add this line
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            raise

    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()

    def create_tables(self):
        cursor = self.conn.cursor()
        
        # Create users table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Create blobs table with foreign key
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
        self.conn.commit()

    def migrate_database(self):
        """Handle database migrations"""
        cursor = self.conn.cursor()
        
        # Check if embedding column exists
        cursor.execute("PRAGMA table_info(blobs)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'embedding' not in columns:
            logger.info("Migrating database to add embedding column")
            try:
                cursor.execute("ALTER TABLE blobs ADD COLUMN embedding BLOB")
                self.conn.commit()
                logger.info("Successfully added embedding column")
            except sqlite3.Error as e:
                logger.error(f"Migration error: {e}")
                raise

    def ensure_user_exists(self, user_id, username=None, first_name=None, last_name=None):
        """Ensure user exists in database, create if not"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        if not cursor.fetchone():
            logger.info(f"Creating new user record for user_id: {user_id}")
            cursor.execute('''
            INSERT INTO users (user_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name))
            self.conn.commit()
        return user_id

    def store_blob(self, user_id, content_type, content, file_path="", is_public=False, embedding=None):
        logger.info(f"Storing new blob for user {user_id} of type {content_type}")
        try:
            if embedding is not None:
                embedding_bytes = embedding.tobytes()
                logger.debug(f"Embedding size: {len(embedding_bytes)} bytes")
            else:
                embedding_bytes = None
                logger.warning("No embedding provided for content")
                
            cursor = self.conn.cursor()
            cursor.execute('''
            INSERT INTO blobs (user_id, content_type, content, file_path, is_public, timestamp, embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, content_type, content, file_path, is_public, datetime.now(), embedding_bytes))
            blob_id = cursor.lastrowid
            self.conn.commit()
            logger.info(f"Successfully stored blob with ID {blob_id}")
            return blob_id
        except Exception as e:
            logger.error(f"Error storing blob: {e}")
            raise

    def update_summary(self, blob_id, summary):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE blobs SET ai_summary = ? WHERE id = ?', (summary, blob_id))
        self.conn.commit()

    def get_user_blobs(self, user_id, is_public=None):
        """Get blobs for specific user"""
        cursor = self.conn.cursor()
        if is_public is None:
            # Get user's private blobs and all public blobs
            cursor.execute('''
            SELECT b.*, u.username 
            FROM blobs b
            LEFT JOIN users u ON b.user_id = u.user_id
            WHERE b.user_id = ? OR b.is_public = 1
            ORDER BY b.timestamp DESC
            ''', (user_id,))
        else:
            # Get only public or private blobs
            cursor.execute('''
            SELECT b.*, u.username 
            FROM blobs b
            LEFT JOIN users u ON b.user_id = u.user_id
            WHERE (b.user_id = ? OR b.is_public = 1) AND b.is_public = ?
            ORDER BY b.timestamp DESC
            ''', (user_id, is_public))
        return cursor.fetchall()

    def get_blob_by_id(self, blob_id, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM blobs WHERE id = ? AND (user_id = ? OR is_public = 1)', 
                      (blob_id, user_id))
        return cursor.fetchone()

    def update_publicity(self, blob_id, is_public, user_id):
        logger.info(f"Updating publicity for blob {blob_id} to {is_public} by user {user_id}")
        cursor = self.conn.cursor()
        cursor.execute('''
        UPDATE blobs 
        SET is_public = ? 
        WHERE id = ? AND user_id = ?
        ''', (is_public, blob_id, user_id))
        
        if cursor.rowcount == 0:
            logger.warning(f"Failed to update blob {blob_id} - not found or unauthorized")
            raise ValueError("Blob not found or you don't have permission to modify it")
        
        self.conn.commit()
        logger.info(f"Successfully updated blob {blob_id} publicity")
        return True

    def update_embedding(self, blob_id, embedding):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE blobs SET embedding = ? WHERE id = ?', 
                      (embedding.tobytes(), blob_id))
        self.conn.commit()

    def search_similar_blobs(self, query_embedding, user_id, limit=5, public_only=False):
        """Search for similar blobs with scope control"""
        if query_embedding is None:
            logger.warning("Received null query embedding")
            return []
            
        cursor = self.conn.cursor()
        
        if public_only:
            # Search all public blobs
            query = '''
            SELECT b.id, b.content, b.content_type, b.ai_summary, b.embedding, b.is_public, u.username, b.user_id
            FROM blobs b
            LEFT JOIN users u ON b.user_id = u.user_id
            WHERE b.is_public = 1 AND b.embedding IS NOT NULL
            '''
            cursor.execute(query)
        else:
            # Search only user's private blobs
            query = '''
            SELECT b.id, b.content, b.content_type, b.ai_summary, b.embedding, b.is_public, u.username, b.user_id
            FROM blobs b
            LEFT JOIN users u ON b.user_id = u.user_id
            WHERE b.user_id = ? AND b.embedding IS NOT NULL
            '''
            cursor.execute(query, (user_id,))
        
        results = []
        for row in cursor.fetchall():
            try:
                if row[4] is None:  # embedding
                    continue
                    
                blob_embedding = np.frombuffer(row[4], dtype=np.float32)
                if blob_embedding.size == 0:
                    continue
                    
                similarity = np.dot(query_embedding, blob_embedding) / (
                    norm(query_embedding) * norm(blob_embedding) + 1e-9
                )
                results.append((similarity, row))
                logger.debug(f"Similarity score for blob {row[0]} (owned by {row[6]}): {similarity}")
            except Exception as e:
                logger.error(f"Error processing blob {row[0]}: {e}")
                continue
        
        # Sort by similarity and return top results
        results.sort(reverse=True, key=lambda x: x[0])
        return [(r[1][0], r[1][1], r[1][2], r[1][3], r[0]) for r in results[:limit]]

    def get_blobs_without_embeddings(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT id, content, content_type FROM blobs WHERE embedding IS NULL')
        return cursor.fetchall()

    def reprocess_embeddings(self, get_embedding_func):
        """Reprocess all blobs without embeddings"""
        logger.info("Starting embedding reprocessing")
        blobs = self.get_blobs_without_embeddings()
        
        if not blobs:
            logger.info("No blobs found that need embedding reprocessing")
            return 0
            
        processed = 0
        for blob_id, content, content_type in blobs:
            try:
                logger.info(f"Processing embedding for blob {blob_id}")
                embedding = get_embedding_func(content)
                
                if embedding is not None:
                    self.update_embedding(blob_id, embedding)
                    processed += 1
                    logger.info(f"Successfully updated embedding for blob {blob_id}")
                else:
                    logger.warning(f"Failed to generate embedding for blob {blob_id}")
                    
            except Exception as e:
                logger.error(f"Error processing blob {blob_id}: {e}")
                continue
                
        logger.info(f"Completed embedding reprocessing. Updated {processed} blobs")
        return processed
