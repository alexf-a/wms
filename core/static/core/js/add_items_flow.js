document.addEventListener('DOMContentLoaded', function() {
    const heroInput = document.getElementById('hero-image-input');
    const heroUploadBtn = document.getElementById('hero-upload-btn');
    const skipBtn = document.getElementById('skip-to-manual');
    const formSection = document.getElementById('form-section');
    const imagePreviewContainer = document.getElementById('image-preview-container');
    const previewImage = document.getElementById('preview-image');
    const changeImageBtn = document.getElementById('change-image-btn');
    const loadingIndicator = document.getElementById('loading-indicator');
    const formCard = document.getElementById('form-card');
    const itemForm = document.getElementById('item-form');
    const nameField = document.getElementById('id_name');
    const descField = document.getElementById('id_description');

    let currentObjectUrl = null;
    const cleanupObjectUrl = () => {
        if (currentObjectUrl) {
            URL.revokeObjectURL(currentObjectUrl);
            currentObjectUrl = null;
        }
    };

    // Trigger file input when hero button is clicked
    heroUploadBtn.addEventListener('click', function() {
        heroInput.click();
    });

    // Handle image selection
    heroInput.addEventListener('change', async function(e) {
        if (e.target.files && e.target.files[0]) {
            const file = e.target.files[0];

            // Show the form section with animation
            formSection.style.display = 'block';
            formSection.classList.add('slide-in');

            // Smooth scroll to form
            setTimeout(() => {
                formSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }, 100);

            // Show loading indicator
            loadingIndicator.style.display = 'block';

            // Show preview
            cleanupObjectUrl();
            currentObjectUrl = URL.createObjectURL(file);
            previewImage.src = currentObjectUrl;
            imagePreviewContainer.style.display = 'block';

            // Call AI generation API
            try {
                const formData = new FormData();
                formData.append('image', file);

                const response = await fetch('/api/extract-item-features/', {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                    }
                });

                if (response.ok) {
                    const data = await response.json();
                    nameField.value = data.name || '';
                    descField.value = data.description || '';
                }
            } catch (error) {
                console.error('Error extracting features:', error);
            } finally {
                // Hide loading, show form
                loadingIndicator.style.display = 'none';
                formCard.style.display = 'block';
            }
        }
    });

    // Handle skip button
    skipBtn.addEventListener('click', function() {
        formSection.style.display = 'block';
        formSection.classList.add('slide-in');
        formCard.style.display = 'block';

        // Smooth scroll to form
        setTimeout(() => {
            formSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
    });

    // Handle change image button
    changeImageBtn.addEventListener('click', function() {
        heroInput.click();
    });

    if (itemForm) {
        itemForm.addEventListener('submit', () => {
            cleanupObjectUrl();
        });
    }

    window.addEventListener('pagehide', cleanupObjectUrl);
    window.addEventListener('beforeunload', cleanupObjectUrl);
});
