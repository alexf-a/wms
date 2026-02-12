/**
 * Add Items Flow JavaScript
 * Handles image upload, AI feature extraction, and form management
 * 
 * Dependencies: ui_utils.js (revealSection, showErrorSnackbar)
 */

// Image compression settings - reduces server memory usage
const MAX_IMAGE_DIMENSION = 1024;  // Max width or height in pixels
const JPEG_QUALITY = 0.85;         // 0.0 to 1.0 - balance between size and quality

/**
 * Resize and compress an image file using canvas.
 * This dramatically reduces memory usage on the server (4032x3024 -> 1024x768).
 * 
 * @param {File} file - The original image file
 * @returns {Promise<Blob>} - Compressed JPEG blob
 */
async function compressImage(file) {
    return new Promise((resolve, reject) => {
        const img = new Image();
        const objectUrl = URL.createObjectURL(file);

        img.onload = () => {
            // Revoke the temporary object URL used to load the image into the
            // Image element; we keep the preview URL management separate.
            URL.revokeObjectURL(objectUrl);

            // Calculate new dimensions maintaining aspect ratio
            let { width, height } = img;
            const originalSize = `${width}x${height}`;

            if (width > MAX_IMAGE_DIMENSION || height > MAX_IMAGE_DIMENSION) {
                if (width > height) {
                    height = Math.round(height * (MAX_IMAGE_DIMENSION / width));
                    width = MAX_IMAGE_DIMENSION;
                } else {
                    width = Math.round(width * (MAX_IMAGE_DIMENSION / height));
                    height = MAX_IMAGE_DIMENSION;
                }
            }

            // Create canvas and draw resized image
            const canvas = document.createElement('canvas');
            canvas.width = width;
            canvas.height = height;

            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0, width, height);

            // Convert to JPEG blob
            canvas.toBlob(
                (blob) => {
                    if (blob) {
                        console.log(`[AddItems] Image compressed: ${originalSize} -> ${width}x${height}, ${(file.size/1024).toFixed(0)}KB -> ${(blob.size/1024).toFixed(0)}KB`);
                        resolve(blob);
                    } else {
                        reject(new Error('Canvas toBlob failed'));
                    }
                },
                'image/jpeg',
                JPEG_QUALITY
            );
        };

        img.onerror = () => {
            URL.revokeObjectURL(objectUrl);
            reject(new Error('Failed to load image for compression'));
        };

        img.src = objectUrl;
    });
}

document.addEventListener('DOMContentLoaded', function() {
    // Always log initialization regardless of debug mode
    console.log('[AddItems] Initializing add_items_flow.js');
    console.log('[AddItems] Referrer:', document.referrer);
    
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

    // Log element availability
    console.log('[AddItems] Elements found:', {
        heroInput: !!heroInput,
        skipBtn: !!skipBtn,
        formSection: !!formSection,
        nameField: !!nameField
    });

    let currentObjectUrl = null;
    let isProcessing = false;
    let lastFileTimestamp = 0;
    
    /**
     * Revoke and clear the in-memory object URL used for the preview image.
     * Ensures browser memory is released when previews are changed or removed.
     *
     * @returns {void}
     */
    const cleanupObjectUrl = () => {
        if (currentObjectUrl) {
            URL.revokeObjectURL(currentObjectUrl);
            currentObjectUrl = null;
        }
    };

    /**
     * Process the selected image file: compress, preview, upload to AI API,
     * and populate the form with returned values.
     *
     * @param {File} file - The selected image file from the input element.
     * @returns {Promise<void>} Resolves when processing and UI updates complete.
     */
    async function processImageFile(file) {
        debugLog('[AddItems] processImageFile called', file ? file.name : 'no file');
        
        // Prevent duplicate processing using timestamp-based debounce
        const now = Date.now();
        if (isProcessing || (now - lastFileTimestamp) < 500) {
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

            debugLog('[AddItems] Compressing image before upload...');
            
            // Compress image client-side to reduce server memory usage
            // This resizes large photos (e.g., 4032x3024) to max 1024px dimension
            let fileBlob;
            try {
                fileBlob = await compressImage(file);
            } catch (compressError) {
                console.warn('[AddItems] Compression failed, using original:', compressError);
                // Fallback to original file if compression fails
                fileBlob = file;
            }

            // Create FormData with the blob
            const formData = new FormData();
            formData.append('image', fileBlob, file.name || 'image.jpg');
            
            // Debug: log formData contents
            for (let [key, value] of formData.entries()) {
                debugLog('[AddItems] FormData entry:', key, value instanceof Blob ? `Blob(${value.size})` : value);
            }

            // Get CSRF token
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
            if (!csrfToken) {
                console.error('[AddItems] CSRF token not found');
                throw new Error('CSRF token not found');
            }
            console.log('[AddItems] CSRF token found, making API call...');

            const response = await fetch('/api/extract-item-features/', {
                method: 'POST',
                body: formData,
                credentials: 'same-origin',
                headers: {
                    'X-CSRFToken': csrfToken.value
                }
            });

            console.log('[AddItems] API response status:', response.status);

            if (response.ok) {
                const data = await response.json();
                console.log('[AddItems] API success:', data);
                nameField.value = data.name || '';
                descField.value = data.description || '';
            } else {
                const errorData = await response.json().catch(() => ({}));
                console.error('[AddItems] API error:', response.status, errorData);
                // Show error in snackbar if available
                if (errorData.error && typeof showErrorSnackbar === 'function') {
                    showErrorSnackbar(errorData.error);
                }
            }
        } catch (error) {
            console.error('[AddItems] Exception during fetch:', error);
        } finally {
            // Hide loading, show form
            loadingIndicator.style.display = 'none';
            formCard.style.display = 'block';
            isProcessing = false;
        }
    }

    /**
     * Handle a file input `change` event and begin processing the selected file.
     *
     * @param {Event} e - The input `change` event containing the FileList.
     * @returns {void}
     */
    function handleImageSelect(e) {
        const files = e.target.files;
        if (files && files.length > 0 && files[0]) {
            processImageFile(files[0]);
        }
    }

    // Use 'change' event which is most reliable across browsers
    heroInput.addEventListener('change', handleImageSelect);

    // Handle skip button - uses shared revealSection utility
    skipBtn.addEventListener('click', function() {
        formCard.style.display = 'block';
        imagePreviewContainer.style.display = 'none';
        revealSection(formSection, null, null, { scrollBlock: 'start' });
    });

    if (itemForm) {
        itemForm.addEventListener('submit', () => {
            cleanupObjectUrl();
        });
    }

    window.addEventListener('pagehide', cleanupObjectUrl);
    window.addEventListener('beforeunload', cleanupObjectUrl);

});
