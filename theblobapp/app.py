from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from database import BlobDatabase
import database_extension
from database_copier import DatabaseCopier
import atexit
from datetime import datetime, timedelta
from collections import defaultdict
import logging

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'  # Required for SocketIO
socketio = SocketIO(app)
db = BlobDatabase()

# Ensure tables exist in main database
db.create_tables()

# Initialize database copier with shorter interval
db_copier = DatabaseCopier(db.db_path, update_interval=30)
db_copier.start()
db.set_copy_path(db_copier.get_copy_path())

@atexit.register
def cleanup():
    db_copier.stop()

@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    public_blobs = db.get_public_blobs(page=page)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(blobs=public_blobs)
    return render_template('index.html', blobs=public_blobs)

@app.route('/search')
def search():
    query = request.args.get('q', '')
    results = db.search_blobs(query) if query else []
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(blobs=results)
    return render_template('search.html', blobs=results, query=query)

@app.route('/blob/<int:blob_id>')
def view_blob(blob_id):
    try:
        blob = db.get_public_blob_by_id(blob_id)
        if blob is None:
            logger.warning(f"Blob {blob_id} not found or is private")
            return render_template('404.html', 
                message="This blob might be private or doesn't exist"), 404
            
        similar_blobs = db.get_similar_blobs(blob_id, limit=3)
        return render_template('blob.html', blob=blob, similar_blobs=similar_blobs)
    except Exception as e:
        logger.error(f"Error viewing blob {blob_id}: {e}", exc_info=True)
        return render_template('error.html', 
            message="Unable to load this blob. Please try again later."), 500

@app.route('/timeline')
def timeline():
    days = request.args.get('days', 7, type=int)
    blobs = db.get_public_blobs_by_date(days=days)
    grouped_blobs = defaultdict(list)
    for blob in blobs:
        date = datetime.strptime(blob['timestamp'], '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
        grouped_blobs[date].append(blob)
    return render_template('timeline.html', grouped_blobs=dict(grouped_blobs))

@socketio.on('connect')
def handle_connect():
    emit('status', {'status': 'connected'})

@socketio.on('request_update')
def handle_update_request():
    latest_blobs = db.get_latest_blobs(limit=5)
    emit('new_blobs', {'blobs': latest_blobs})

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('error.html', message="Internal server error"), 500

# Add context processor for error handling
@app.context_processor
def utility_processor():
    def format_error_message(error):
        if isinstance(error, dict):
            return error.get('message', 'An unexpected error occurred')
        return str(error)
    return dict(format_error_message=format_error_message)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', debug=True)