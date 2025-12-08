document.addEventListener('DOMContentLoaded', function() {
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
    
    const cleanupObjectUrl = () => {
        if (currentObjectUrl) {
            URL.revokeObjectURL(currentObjectUrl);
            currentObjectUrl = null;
        }
    };

    // Process the selected image file
    async function processImageFile(file) {
        // Prevent duplicate processing
        if (isProcessing) return;
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

            // Call AI generation API
            const formData = new FormData();
            formData.append('image', file);

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

    // Handle image selection via native label click
    function handleImageSelect(e) {
        const files = e.target.files;
        if (files && files.length > 0 && files[0]) {
            processImageFile(files[0]);
        }
    }

    heroInput.addEventListener('change', handleImageSelect);
    heroInput.addEventListener('input', handleImageSelect);

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
