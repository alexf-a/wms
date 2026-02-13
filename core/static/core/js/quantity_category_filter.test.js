const {
    initQuantityCategoryFilter,
} = require('./quantity_category_filter');

/**
 * Build DOM fixture for quantity category filtering tests.
 *
 * @param {string} [checkedCategory=''] - Optional pre-checked radio value.
 * @returns {HTMLSelectElement} Quantity unit select element.
 */
function setupDom(checkedCategory = '') {
    document.body.innerHTML = `
        <div>
            <input type="radio" name="quantity_category" value="count" ${checkedCategory === 'count' ? 'checked' : ''}>
            <input type="radio" name="quantity_category" value="mass" ${checkedCategory === 'mass' ? 'checked' : ''}>
            <input type="radio" name="quantity_category" value="volume" ${checkedCategory === 'volume' ? 'checked' : ''}>
            <input type="radio" name="quantity_category" value="length" ${checkedCategory === 'length' ? 'checked' : ''}>

            <select id="id_quantity_unit">
                <option value="">Select...</option>
                <option value="count" data-category="count">Count</option>
                <option value="mg" data-category="mass">Milligrams</option>
                <option value="kg" data-category="mass">Kilograms</option>
                <option value="mL" data-category="volume">Milliliters</option>
                <option value="L" data-category="volume">Liters</option>
                <option value="cm" data-category="length">Centimeters</option>
            </select>
        </div>
    `;

    return document.getElementById('id_quantity_unit');
}

/**
 * Get select option values in order.
 *
 * @param {HTMLSelectElement} select - Unit select element.
 * @returns {string[]} Option values in DOM order.
 */
function getOptionValues(select) {
    return Array.from(select.options).map((option) => option.value);
}

/**
 * Trigger a category change event.
 *
 * @param {string} category - Radio category value to select.
 * @returns {void}
 */
function changeCategory(category) {
    const radio = document.querySelector(`input[name="quantity_category"][value="${category}"]`);
    radio.checked = true;
    radio.dispatchEvent(new Event('change', { bubbles: true }));
}

describe('quantity category filter', () => {
    afterEach(() => {
        document.body.innerHTML = '';
    });

    test('initializes safely when radios are missing', () => {
        document.body.innerHTML = '<select id="id_quantity_unit"><option value="">Select...</option></select>';
        expect(() => initQuantityCategoryFilter()).not.toThrow();
    });

    test('initializes safely when select is missing', () => {
        document.body.innerHTML = '<input type="radio" name="quantity_category" value="mass">';
        expect(() => initQuantityCategoryFilter()).not.toThrow();
    });

    test('shows only placeholder when no category is pre-selected', () => {
        const select = setupDom();

        initQuantityCategoryFilter();

        expect(getOptionValues(select)).toEqual(['']);
    });

    test('filters to mass units when mass is selected', () => {
        const select = setupDom();

        initQuantityCategoryFilter();
        changeCategory('mass');

        expect(getOptionValues(select)).toEqual(['', 'mg', 'kg']);
    });

    test('filters to count unit when count is selected', () => {
        const select = setupDom();

        initQuantityCategoryFilter();
        changeCategory('count');

        expect(getOptionValues(select)).toEqual(['', 'count']);
    });

    test('resets selected value when switching to incompatible category', () => {
        const select = setupDom('mass');

        initQuantityCategoryFilter();
        select.value = 'kg';
        expect(select.value).toBe('kg');

        changeCategory('volume');

        expect(getOptionValues(select)).toEqual(['', 'mL', 'L']);
        expect(select.value).toBe('');
    });

    test('keeps selected value when switching within same category', () => {
        const select = setupDom('mass');

        initQuantityCategoryFilter();
        select.value = 'kg';

        changeCategory('mass');

        expect(getOptionValues(select)).toEqual(['', 'mg', 'kg']);
        expect(select.value).toBe('kg');
    });

    test('applies pre-checked category during initialization', () => {
        const select = setupDom('volume');

        initQuantityCategoryFilter();

        expect(getOptionValues(select)).toEqual(['', 'mL', 'L']);
    });
});
