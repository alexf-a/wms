/**
 * Quantity Controls JavaScript
 * Handles quick quantity updates for items with +/- buttons, click-to-edit, and long-press
 * 
 * Dependencies: ui_utils.js (showErrorSnackbar)
 */

// Sequence tracking for parallel requests (prevents UI resets from stale responses)
// Map: itemId -> {nextSeq, lastAppliedSeq, pendingCount}
const itemPendingState = new Map();
const quantityLogic = window.WMSQuantityLogic;

if (!quantityLogic) {
    throw new Error('WMSQuantityLogic is required. Ensure quantity_logic.js is loaded first.');
}

/**
 * Get or initialize pending state for an item.
 * 
 * @param {number} itemId - The database ID of the item
 * @returns {Object} State object with {nextSeq, lastAppliedSeq, pendingCount}
 */
function getPendingState(itemId) {
    if (!itemPendingState.has(itemId)) {
        itemPendingState.set(itemId, quantityLogic.createPendingState());
    }
    return itemPendingState.get(itemId);
}

/**
 * Update item quantity via AJAX.
 * 
 * Triggered by: enqueueRequest() callback functions from user interactions
 * 
 * Results:
 * - Sends POST request to /api/item/{itemId}/quantity/
 * - Returns server response with updated quantity and formatted string
 * - Throws error if request fails or CSRF token missing
 * 
 * Side effects:
 * - Makes HTTP POST request to backend
 * - Does NOT modify DOM (caller must handle UI updates)
 * 
 * @param {number} itemId - The database ID of the item to update
 * @param {string} action - Action type: 'increment', 'decrement', or 'set'
 * @param {number|null} value - New value for 'set' action, null for increment/decrement
 * @param {HTMLElement} wrapper - Item card wrapper (used for context, not modified)
 * @param {number} previousQuantity - Previous quantity (used for context, not modified)
 * @returns {Promise<Object>} Response data: {quantity: number, formatted: string}
 * @throws {Error} If CSRF token not found or request fails
 */
async function updateQuantity(itemId, action, value, wrapper, previousQuantity) {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
    if (!csrfToken) {
        throw new Error('CSRF token not found');
    }

    const formData = new FormData();
    formData.append('action', action);
    if (value !== null) {
        formData.append('value', value);
    }

    const response = await fetch(`/api/item/${itemId}/quantity/`, {
        method: 'POST',
        body: formData,
        credentials: 'same-origin',
        headers: {
            'X-CSRFToken': csrfToken.value
        }
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || 'Failed to update quantity');
    }

    return await response.json();
}

/**
 * Update the UI with new quantity value.
 * 
 * Triggered by: 
 * - handleQuantityButton() for optimistic updates and server response
 * - handleQuantityValueClick() callback after successful save
 * 
 * Results:
 * - Updates .qty-value text and aria-valuenow attribute
 * - Updates data-quantity attribute on wrapper
 * - Toggles .qty-zero CSS class based on quantity value
 * 
 * Side effects:
 * - Modifies DOM: text content, attributes, and CSS classes
 * - Triggers CSS transitions via class changes
 * 
 * @param {HTMLElement} wrapper - The .m3-item-card-wrapper element to update
 * @param {number} quantity - The new numeric quantity value
 * @param {string} formatted - The formatted display string (e.g., "5.5 kg")
 * @returns {void}
 */
function updateUI(wrapper, quantity, formatted) {
    const qtyValue = wrapper.querySelector('.qty-value');
    const controls = wrapper.querySelector('.m3-quantity-controls');
    
    if (qtyValue) {
        qtyValue.textContent = formatted;
        qtyValue.setAttribute('aria-valuenow', quantity);
    }
    
    wrapper.setAttribute('data-quantity', quantity);
    
    // Toggle zero state styling
    if (controls) {
        if (quantity === 0) {
            controls.classList.add('qty-zero');
        } else {
            controls.classList.remove('qty-zero');
        }
    }
}

/**
 * Handle increment/decrement button clicks.
 * 
 * Triggered by:
 * - User clicking .qty-increment or .qty-decrement buttons
 * - setupLongPress() during long-press repeat cycles
 * 
 * Results:
 * - Calculates new quantity (step: 1 for count, 0.1 for others)
 * - Performs optimistic UI update immediately
 * - Queues AJAX request for server sync
 * - Reverts UI on error, shows error snackbar
 * 
 * Side effects:
 * - Modifies DOM via updateUI() (optimistic update)
 * - Enqueues async API request
 * - May display error snackbar
 * - Prevents event bubbling to parent <a> tag
 * 
 * Dependencies:
 * - window.WMS_UNIT_2_NAME for unit display names
 * - showErrorSnackbar() from ui_utils.js (optional)
 * 
 * @param {Event} e - Click or synthetic event with currentTarget property
 * @returns {void}
 */
function handleQuantityButton(e) {
    e.preventDefault();
    e.stopPropagation();
    
    const button = e.currentTarget;
    const wrapper = button.closest('.m3-item-card-wrapper');
    if (!wrapper) return;
    
    const itemId = parseInt(wrapper.getAttribute('data-item-id'));
    const currentQuantity = parseFloat(wrapper.getAttribute('data-quantity'));
    const action = button.classList.contains('qty-increment') ? 'increment' : 'decrement';
    
    // Get or initialize sequence state for this item
    const state = getPendingState(itemId);
    const requestSeq = quantityLogic.recordRequest(state);
    
    // Optimistic UI update
    const quantityUnit = wrapper.getAttribute('data-quantity-unit');
    const newQuantity = quantityLogic.calculateOptimisticQuantity(currentQuantity, action, quantityUnit);
    
    // Update UI immediately (optimistic)
    const formatted = quantityLogic.formatQuantity(newQuantity, quantityUnit, window.WMS_UNIT_2_NAME);
    updateUI(wrapper, newQuantity, formatted);
    
    // Fire parallel request immediately (no queue)
    (async () => {
        try {
            const data = await updateQuantity(itemId, action, null, wrapper, currentQuantity);
            
            // Only apply response if this is the final pending request
            const { shouldApply } = quantityLogic.resolveRequest(state, requestSeq);
            if (shouldApply) {
                // Final response - update UI with server value
                updateUI(wrapper, data.quantity, data.formatted);
            }
        } catch (error) {
            console.error('[QuantityControls] Update failed:', error);
            quantityLogic.resolveRequest(state, requestSeq);
            
            // Only show error/revert if no more pending requests
            if (quantityLogic.shouldApplyServerResponse(state)) {
                // Revert to last known server value
                const prevFormatted = quantityLogic.formatQuantity(
                    currentQuantity,
                    quantityUnit,
                    window.WMS_UNIT_2_NAME,
                );
                updateUI(wrapper, currentQuantity, prevFormatted);
                
                // Show error snackbar
                if (typeof showErrorSnackbar === 'function') {
                    showErrorSnackbar(error.message || 'Failed to update quantity');
                }
            }
            // Otherwise, let subsequent requests resolve the state
        }
    })();
}

/**
 * Handle click on quantity value to enable inline editing.
 * 
 * Triggered by: User clicking .qty-value span element
 * 
 * Results:
 * - Hides .qty-value span
 * - Creates and inserts <input type="number"> for editing
 * - Auto-focuses and selects input value
 * - Saves on blur/Enter, cancels on Escape
 * - Validates input (must be number >= 0)
 * - Queues API request if value changed
 * 
 * Side effects:
 * - Modifies DOM: hides span, adds input element
 * - Attaches blur and keydown event listeners to input
 * - Enqueues async API request (if value changes)
 * - Prevents event bubbling to parent <a> tag
 * 
 * @param {Event} e - Click event from .qty-value element
 * @returns {void}
 */
function handleQuantityValueClick(e) {
    e.preventDefault();
    e.stopPropagation();
    
    const qtyValue = e.currentTarget;
    const wrapper = qtyValue.closest('.m3-item-card-wrapper');
    if (!wrapper) return;
    
    const itemId = parseInt(wrapper.getAttribute('data-item-id'));
    const currentQuantity = parseFloat(wrapper.getAttribute('data-quantity'));
    const quantityUnit = wrapper.getAttribute('data-quantity-unit');
    const step = quantityLogic.getStepSize(quantityUnit);
    
    // Create input element
    const input = document.createElement('input');
    input.type = 'number';
    input.className = 'qty-input';
    // Format input value to show correct decimal places
    input.value = quantityUnit === 'count'
        ? Math.round(currentQuantity)
        : currentQuantity.toFixed(quantityLogic.decimalPlaces);
    input.min = '0';
    input.step = step.toString();
    
    // Replace span with input
    qtyValue.style.display = 'none';
    qtyValue.parentElement.insertBefore(input, qtyValue);
    input.focus();
    input.select();
    
    // Save on blur or Enter
    const saveValue = async () => {
        const newValue = parseFloat(input.value);
        
        if (isNaN(newValue) || newValue < 0) {
            // Invalid input - restore original
            input.remove();
            qtyValue.style.display = '';
            return;
        }
        
        // Restore span
        input.remove();
        qtyValue.style.display = '';
        
        // If value unchanged, do nothing
        if (newValue === currentQuantity) {
            return;
        }
        
        // Reset sequence state - 'set' establishes new baseline
        const state = getPendingState(itemId);
        quantityLogic.resetStateForSet(state);
        
        // Fire the update request
        (async () => {
            try {
                const data = await updateQuantity(itemId, 'set', newValue, wrapper, currentQuantity);
                state.pendingCount = Math.max(0, state.pendingCount - 1);
                updateUI(wrapper, data.quantity, data.formatted);
            } catch (error) {
                console.error('[QuantityControls] Set value failed:', error);
                state.pendingCount = Math.max(0, state.pendingCount - 1);
                // Show error snackbar
                if (typeof showErrorSnackbar === 'function') {
                    showErrorSnackbar(error.message || 'Failed to update quantity');
                }
            }
        })();
    };
    
    input.addEventListener('blur', saveValue);
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            input.blur();
        } else if (e.key === 'Escape') {
            input.value = currentQuantity;
            input.blur();
        }
    });
}

/**
 * Set up long-press behavior for rapid quantity updates.
 * 
 * Triggered by: initQuantityControls() during initialization for each +/- button
 * 
 * Results:
 * - Attaches mousedown/up/leave and touchstart/end/cancel event listeners
 * - Starts repeat after 500ms hold
 * - Repeats every 200ms initially, accelerates to 50ms after 1 second
 * - Each repeat triggers handleQuantityButton()
 * 
 * Side effects:
 * - Attaches 6 event listeners to button (mouse and touch events)
 * - Creates closures with timer state (longPressTimer, repeatTimer, repeatCount)
 * - Repeatedly calls handleQuantityButton() during hold
 * 
 * Implementation notes:
 * - Uses closure to maintain timer state per button
 * - Prevents default to avoid unwanted browser behaviors
 * - Cleans up timers on release to prevent memory leaks
 * 
 * @param {HTMLElement} button - The .qty-increment or .qty-decrement button element
 * @returns {void}
 */
function setupLongPress(button) {
    let longPressTimer = null;
    let repeatTimer = null;
    let repeatCount = 0;
    let didRepeat = false;
    
    const startLongPress = (e) => {
        e.preventDefault();
        didRepeat = false;
        
        // Initial delay before repeat starts
        longPressTimer = setTimeout(() => {
            repeatCount = 0;
            didRepeat = true;
            
            const repeat = () => {
                repeatCount++;
                // Trigger click
                handleQuantityButton({ 
                    currentTarget: button, 
                    preventDefault: () => {}, 
                    stopPropagation: () => {} 
                });
                
                // Accelerate after 1 second (5 clicks at 200ms = 1s)
                const interval = repeatCount > 5 ? 50 : 200;
                repeatTimer = setTimeout(repeat, interval);
            };
            
            repeat();
        }, 500); // Start repeating after 500ms hold
    };
    
    const stopLongPress = (e) => {
        const wasQuickTap = !didRepeat;
        
        if (longPressTimer) {
            clearTimeout(longPressTimer);
            longPressTimer = null;
        }
        if (repeatTimer) {
            clearTimeout(repeatTimer);
            repeatTimer = null;
        }
        repeatCount = 0;
        didRepeat = false;
        
        // If this was a quick tap on touch (not a long-press), manually trigger the click handler
        // since preventDefault() in touchstart blocked the synthetic click event
        if (e && e.type === 'touchend' && wasQuickTap) {
            handleQuantityButton({ 
                currentTarget: button, 
                preventDefault: () => {}, 
                stopPropagation: () => {} 
            });
        }
    };
    
    // Mouse events
    button.addEventListener('mousedown', startLongPress);
    button.addEventListener('mouseup', stopLongPress);
    button.addEventListener('mouseleave', stopLongPress);
    
    // Touch events
    button.addEventListener('touchstart', startLongPress);
    button.addEventListener('touchend', stopLongPress);
    button.addEventListener('touchcancel', stopLongPress);
}

/**
 * Initialize quantity controls for all items on the page.
 * 
 * Triggered by:
 * - Auto-initialization when DOM is ready (via DOMContentLoaded or immediate)
 * - Can be called manually via window.initQuantityControls()
 * 
 * Results:
 * - Finds all .qty-increment and .qty-decrement buttons
 * - Attaches click handlers and long-press behavior to each
 * - Finds all .qty-value spans and attaches click-to-edit handlers
 * - Logs initialization messages to console
 * 
 * Side effects:
 * - Attaches multiple event listeners to DOM elements
 * - Logs to console
 * 
 * Prerequisites:
 * - DOM must be loaded
 * - Elements with classes .qty-increment, .qty-decrement, .qty-value must exist
 * - window.WMS_UNIT_2_NAME should be defined (for unit display names)
 * 
 * @returns {void}
 */
function initQuantityControls() {
    console.log('[QuantityControls] Initializing...');
    
    // Attach click handlers to all +/- buttons
    document.querySelectorAll('.qty-increment, .qty-decrement').forEach(button => {
        button.addEventListener('click', handleQuantityButton);
        setupLongPress(button);
    });
    
    // Attach click handler to quantity values for inline editing
    document.querySelectorAll('.qty-value').forEach(qtyValue => {
        qtyValue.addEventListener('click', handleQuantityValueClick);
    });
    
    console.log('[QuantityControls] Initialized');
}

// Auto-initialize when DOM is ready
if (typeof window !== 'undefined') {
    // Export for manual use if needed
    window.initQuantityControls = initQuantityControls;
    
    // Auto-initialize
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initQuantityControls);
    } else {
        // DOM already loaded
        initQuantityControls();
    }
}
