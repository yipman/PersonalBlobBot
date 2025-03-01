const socket = io();
let currentPage = 1;
let loading = false;

// Initialize infinite scroll
window.addEventListener('scroll', () => {
    if ((window.innerHeight + window.scrollY) >= document.body.offsetHeight - 1000) {
        loadMoreBlobs();
    }
});

// Handle real-time updates
socket.on('connect', () => {
    console.log('Connected to WebSocket');
    setInterval(() => {
        socket.emit('request_update');
    }, 30000);
});

socket.on('new_blobs', (data) => {
    if (data.blobs.length > 0) {
        updateFeed(data.blobs);
    }
});

// Search functionality
const searchInput = document.getElementById('search');
if (searchInput) {
    searchInput.addEventListener('input', debounce(handleSearch, 500));
}

// ...Add rest of the JavaScript code...
