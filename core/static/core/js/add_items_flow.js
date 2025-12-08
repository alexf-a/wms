document.addEventListener('DOMContentLoaded', function() {
    console.log('[AddItems] Script loaded v3');
    
    const heroInput = document.getElementById('hero-image-input');
    const skipBtn = document.getElementById('skip-to-manual');
    const formSection = document.getElementById('form-section');
    const imagePreviewContainer = document.getElementById('image-preview-container');
    const previewImage = document.getElementById('preview-image');
    const loadingIndicator = document.getElementById('loading-indicator');
    const formCard = document.getElementById('form-card');
    const itemForm = document.getElementById('item-form');
    const nameField = document.getElementById('id_name');
    const descField = document.getElementById('id_description');

    let currentObjectUrl = null;
    let isProcessing = false;
    let lastFileTimestamp = 0;
    
    const cleanupObjectUrl = () => {
        if (currentObjectUrl) {
            URL.revokeObjectURL(currentObjectUrl);
            currentObjectUrl = null;
        }
    };

    // Process the selected image file
    async function processImageFile(file) {
        console.log('[AddItems] processImageFile called', file ? file.name : 'no file');
        
        // Prevent duplicate processing using timestamp-based debounce
        const now = Date.now();
        if (isProcessing || (now - lastFileTimestamp) < 500) {
            console.log('[AddItems] Debounced, skipping');
            return;
        }
        lastFileTimestamp = now;
        isProcessing = true;

        try {
            // Show the form section with animation
            formSection.style.display = 'block';
            formSection.classList.add('slide-in');

            // Smooth scroll to form (with slight delay for DOM update)
            setTimeout(() => {
                formSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }, 100);

            // Show loading indicator
            loadingIndicator.style.display = 'block';
            formCard.style.display = 'none';

            // Show preview
            cleanupObjectUrl();
            currentObjectUrl = URL.createObjectURL(file);
            previewImage.src = currentObjectUrl;
            imagePreviewContainer.style.display = 'block';

            console.log('[AddItems] Reading file as ArrayBuffer...');
            
            // Read the file as blob to ensure it's fully loaded before sending
            // This helps with iOS Safari/Chrome which may have async file access
            const fileBlob = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => {
                    console.log('[AddItems] FileReader loaded, size:', reader.result.byteLength);
                    const blob = new Blob([reader.result], { type: file.type || 'image/jpeg' });
                    resolve(blob);
                };
                reader.onerror = (err) => {
                    console.error('[AddItems] FileReader error:', err);
                    reject(err);
                };
                reader.readAsArrayBuffer(file);
            });

            console.log('[AddItems] Blob created, size:', fileBlob.size, 'type:', fileBlob.type);

            // Create FormData with the blob
            const formData = new FormData();
            formData.append('image', fileBlob, file.name || 'image.jpg');
            
            // Debug: log formData contents
            for (let [key, value] of formData.entries()) {
                console.log('[AddItems] FormData entry:', key, value instanceof Blob ? `Blob(${value.size})` : value);
            }

            // Get CSRF token
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
            if (!csrfToken) {
                console.error('CSRF token not found');
                throw new Error('CSRF token not found');
            }

            const response = await fetch('/api/extract-item-features/', {
                method: 'POST',
                body: formData,
                credentials: 'same-origin',
                headers: {
                    'X-CSRFToken': csrfToken.value
                }
            });

            if (response.ok) {
                const data = await response.json();
                nameField.value = data.name || '';
                descField.value = data.description || '';
            } else {
                const errorData = await response.json().catch(() => ({}));
                console.error('API error:', response.status, errorData);
                // Show error in snackbar if available
                if (errorData.error && typeof showErrorSnackbar === 'function') {
                    showErrorSnackbar(errorData.error);
                }
            }
        } catch (error) {
            console.error('Error extracting features:', error);
        } finally {
            // Hide loading, show form
            loadingIndicator.style.display = 'none';
            formCard.style.display = 'block';
            isProcessing = false;
        }
    }

    // Handle image selection - works for both camera and file upload
    function handleImageSelect(e) {
        const files = e.target.files;
        if (files && files.length > 0 && files[0]) {
            processImageFile(files[0]);
        }
    }

    // Use 'change' event which is most reliable across browsers
    heroInput.addEventListener('change', handleImageSelect);

    // Handle skip button
    skipBtn.addEventListener('click', function() {
        formSection.style.display = 'block';
        formSection.classList.add('slide-in');
        formCard.style.display = 'block';
        imagePreviewContainer.style.display = 'none';

        setTimeout(() => {
            formSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
    });

    if (itemForm) {
        itemForm.addEventListener('submit', () => {
            cleanupObjectUrl();
        });
    }

    window.addEventListener('pagehide', cleanupObjectUrl);
    window.addEventListener('beforeunload', cleanupObjectUrl);
});
