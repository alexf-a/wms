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

    /**
     * Filter quantity unit options based on selected category.
     *
     * Hides and disables options that don't match the provided category so the
     * user can only select units relevant to the chosen measurement type.
     *
     * @param {string} category - The selected category (e.g., "count", "mass").
     * @returns {void}
     */
    function filterQuantityUnits(category) {
        const options = quantityUnitSelect.querySelectorAll('option[data-category]');
        const currentValue = quantityUnitSelect.value;
        let currentValueVisible = false;

        if (!category) {
            options.forEach(option => {
                option.hidden = true;
                option.disabled = true;
            });
            if (currentValue) {
                quantityUnitSelect.value = '';
            }
            return;
        }

        options.forEach(option => {
            const optionCategory = option.getAttribute('data-category');
            const isVisible = optionCategory === category;
            option.hidden = !isVisible;
            option.disabled = !isVisible;

            if (isVisible && option.value === currentValue) {
                currentValueVisible = true;
            }
        });

        if (!currentValueVisible && currentValue) {
            quantityUnitSelect.value = '';
        }
    }

    categoryRadios.forEach(radio => {
        radio.addEventListener('change', (e) => {
            filterQuantityUnits(e.target.value);
        });
    });

    const checkedRadio = document.querySelector('input[name="quantity_category"]:checked');
    if (checkedRadio) {
        filterQuantityUnits(checkedRadio.value);
    } else {
        filterQuantityUnits('');
    }
}

document.addEventListener('DOMContentLoaded', function() {
    initQuantityCategoryFilter();
});
