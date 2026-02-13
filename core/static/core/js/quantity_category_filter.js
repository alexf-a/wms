/**
 * Quantity Category Filter JavaScript
 * Filters quantity unit options based on selected quantity category.
 */

/**
 * Initialize quantity category filter functionality.
 * Filters the quantity_unit dropdown based on selected quantity_category.
 *
 * @returns {void}
 */
function initQuantityCategoryFilter() {
    const categoryRadios = document.querySelectorAll('input[name="quantity_category"]');
    const quantityUnitSelect = document.getElementById('id_quantity_unit');

    if (!categoryRadios.length || !quantityUnitSelect) {
        return;
    }

    const placeholderOption = quantityUnitSelect.querySelector('option:not([data-category])');
    const allCategoryOptions = Array.from(quantityUnitSelect.querySelectorAll('option[data-category]'));

    /**
     * Filter quantity unit options based on selected category.
     *
    * Rebuilds the dropdown options to include only units that match the
    * selected category.
     *
     * @param {string} category - The selected category (e.g., "count", "mass").
     * @returns {void}
     */
    function filterQuantityUnits(category) {
        const currentValue = quantityUnitSelect.value;

        allCategoryOptions.forEach(option => {
            option.remove();
        });

        const matchingOptions = category
            ? allCategoryOptions.filter((option) => option.getAttribute('data-category') === category)
            : [];

        matchingOptions.forEach((option) => {
            quantityUnitSelect.appendChild(option);
        });

        if (placeholderOption) {
            quantityUnitSelect.insertBefore(placeholderOption, quantityUnitSelect.firstChild);
        }

        const currentValueStillVisible = matchingOptions.some((option) => option.value === currentValue);
        if (!currentValueStillVisible) {
            quantityUnitSelect.value = '';
        }
    }

    /**
     * Handle category radio changes and apply unit filtering.
     *
     * @param {Event} event - Change event from a quantity category radio input.
     * @returns {void}
     */
    function handleCategoryChange(event) {
        const target = event.target;
        if (!(target instanceof HTMLInputElement)) {
            return;
        }
        filterQuantityUnits(target.value);
    }

    categoryRadios.forEach(radio => {
        radio.addEventListener('change', handleCategoryChange);
    });

    const checkedRadio = document.querySelector('input[name="quantity_category"]:checked');
    if (checkedRadio) {
        filterQuantityUnits(checkedRadio.value);
    } else {
        filterQuantityUnits('');
    }
}

/**
 * Initialize quantity category filtering after the document is ready.
 *
 * @returns {void}
 */
function initQuantityCategoryFilterOnReady() {
    initQuantityCategoryFilter();
}

document.addEventListener('DOMContentLoaded', initQuantityCategoryFilterOnReady);

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initQuantityCategoryFilter,
        initQuantityCategoryFilterOnReady,
    };
}
