from database import BlobDatabase
import numpy as np
from numpy.linalg import norm
import logging

logger = logging.getLogger(__name__)

def get_public_blobs(self, page=1, per_page=10):
    """Get paginated public blobs"""
    offset = (page - 1) * per_page
    with self.get_read_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
        SELECT 
            b.id, b.content_type, b.content, b.file_path, 
            b.timestamp, b.ai_summary, u.username, u.first_name,
            (SELECT COUNT(*) FROM blob_likes WHERE blob_id = b.id) as likes_count
        FROM blobs b
        LEFT JOIN users u ON b.user_id = u.user_id
        WHERE b.is_public = 1
        ORDER BY b.timestamp DESC
        LIMIT ? OFFSET ?
        ''', (per_page, offset))
        rows = cursor.fetchall()
        return self.rows_to_dicts(cursor, rows)

def get_public_blob_by_id(self, blob_id):
    """Get a specific public blob"""
    with self.get_read_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
        SELECT 
            b.id,
            b.content_type,
            b.content,
            b.file_path,
            b.timestamp,
            b.ai_summary,
            b.embedding,
            u.username,
            u.first_name,
            (SELECT COUNT(*) FROM blob_likes WHERE blob_id = b.id) as likes_count
        FROM blobs b
        LEFT JOIN users u ON b.user_id = u.user_id
        WHERE b.id = ? AND b.is_public = 1
        ''', (blob_id,))
        row = cursor.fetchone()
        return self.row_to_dict(cursor, row)

def search_blobs(self, query):
    """Search blobs by content or summary"""
    with self.get_read_connection() as conn:
        cursor = conn.cursor()
        query = f"%{query}%"
        cursor.execute('''
        SELECT DISTINCT b.*, u.username, u.first_name
        FROM blobs b
        LEFT JOIN users u ON b.user_id = u.user_id
        WHERE b.is_public = 1 
        AND (b.content LIKE ? OR b.ai_summary LIKE ?)
        ORDER BY b.timestamp DESC
        ''', (query, query))
        return self.rows_to_dicts(cursor, cursor.fetchall())

def get_similar_blobs(self, blob_id, limit=3):
    """Get similar blobs based on embedding similarity"""
    # First get the source blob's embedding
    source_blob = self.get_public_blob_by_id(blob_id)
    if not source_blob or not source_blob.get('embedding'):
        return []

    with self.get_read_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
        SELECT 
            b.id,
            b.content_type,
            b.content,
            b.file_path,
            b.timestamp,
            b.ai_summary,
            b.embedding,
            u.username,
            u.first_name
        FROM blobs b
        LEFT JOIN users u ON b.user_id = u.user_id
        WHERE b.is_public = 1 
        AND b.id != ? 
        AND b.embedding IS NOT NULL
        ''', (blob_id,))
        
        results = []
        source_embedding = np.frombuffer(source_blob['embedding'], dtype=np.float32)
        
        for row in cursor:
            blob_dict = self.row_to_dict(cursor, row)
            if not blob_dict['embedding']:
                continue
                
            try:
                target_embedding = np.frombuffer(blob_dict['embedding'], dtype=np.float32)
                similarity = np.dot(source_embedding, target_embedding) / (
                    norm(source_embedding) * norm(target_embedding) + 1e-9
                )
                results.append((similarity, blob_dict))
            except Exception as e:
                logger.error(f"Error calculating similarity for blob {blob_dict['id']}: {e}")
                continue
        
        # Sort by similarity and return top results
        results.sort(reverse=True, key=lambda x: x[0])
        return [r[1] for r in results[:limit]]

# Add these methods to BlobDatabase
BlobDatabase.get_public_blobs = get_public_blobs
BlobDatabase.get_public_blob_by_id = get_public_blob_by_id
BlobDatabase.get_similar_blobs = get_similar_blobs
BlobDatabase.search_blobs = search_blobs
