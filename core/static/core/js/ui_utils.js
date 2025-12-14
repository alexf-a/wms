/**
 * WMS Shared UI Utilities
 * Common UI patterns and components used across pages
 */

/**
 * Reveal a hidden section with slide-in animation and smooth scroll
 * @param {HTMLElement} section - The section element to reveal
 * @param {HTMLElement} triggerBtn - The button that triggered the reveal (will be hidden)
 * @param {HTMLElement} [focusElement] - Optional element to focus after reveal
 * @param {Object} [options] - Optional configuration
 * @param {string} [options.scrollBlock='center'] - Scroll block alignment
 * @param {number} [options.focusDelay=300] - Delay before focusing element (ms)
 */
function revealSection(section, triggerBtn, focusElement, options = {}) {
    const { scrollBlock = 'center', focusDelay = 300 } = options;
    
    if (!section) return;
    
    section.style.display = 'block';
    section.classList.add('slide-in');
    
    if (triggerBtn) {
        triggerBtn.style.display = 'none';
    }
    
    // Smooth scroll to section
    setTimeout(() => {
        section.scrollIntoView({ behavior: 'smooth', block: scrollBlock });
    }, 100);
    
    // Focus element if provided
    if (focusElement) {
        setTimeout(() => focusElement.focus(), focusDelay);
    }
}

/**
 * Show an error message in a Material 3 snackbar
 * @param {string} message - The error message to display
 * @param {Object} [options] - Optional configuration
 * @param {number} [options.duration=6000] - Auto-dismiss duration in ms
 * @param {string} [options.snackbarId='error-snackbar'] - ID of the snackbar element
 */
function showErrorSnackbar(message, options = {}) {
    const { duration = 6000, snackbarId = 'error-snackbar' } = options;
    
    const snackbar = document.getElementById(snackbarId);
    const snackbarText = document.getElementById(`${snackbarId}-text`);
    const dismissBtn = document.getElementById(`${snackbarId}-dismiss`);
    
    if (snackbar && snackbarText) {
        snackbarText.textContent = message;
        snackbar.classList.add('m3-snackbar--visible');
        
        // Auto-dismiss after duration
        const timeout = setTimeout(() => {
            snackbar.classList.remove('m3-snackbar--visible');
        }, duration);
        
        // Manual dismiss
        if (dismissBtn) {
            dismissBtn.onclick = () => {
                clearTimeout(timeout);
                snackbar.classList.remove('m3-snackbar--visible');
            };
        }
    }
}

/**
 * Show form section and display errors (for server-side validation errors)
 * @param {string} formSectionId - ID of the form section element
 * @param {string} formCardId - ID of the form card element
 */
function showFormSectionWithErrors(formSectionId, formCardId) {
    const formSection = document.getElementById(formSectionId);
    const formCard = document.getElementById(formCardId);
    
    if (formSection) formSection.style.display = 'block';
    if (formCard) formCard.style.display = 'block';
}
