/**
 * Item Search Page JavaScript
 * Handles search input focus and browse-by-unit toggle functionality
 * 
 * Dependencies: ui_utils.js (revealSection)
 */

document.addEventListener('DOMContentLoaded', function() {
    // Focus search input on page load
    const searchInput = document.getElementById('id_query');
    if (searchInput) {
        searchInput.focus();
    }

    // Browse by Unit toggle functionality
    const browseByUnitBtn = document.getElementById('browse-by-unit-btn');
    const unitFilterSection = document.getElementById('unit-filter-section');
    const unitSelect = document.getElementById('unit_filter');
    const searchFieldGroup = document.getElementById('search-field-group');
    
    if (browseByUnitBtn && unitFilterSection) {
        browseByUnitBtn.addEventListener('click', function() {
            // Hide the search bar
            if (searchFieldGroup) {
                searchFieldGroup.style.display = 'none';
            }
            revealSection(unitFilterSection, browseByUnitBtn, unitSelect);
        });
    }

    // Navigate to unit detail page when a unit is selected
    if (unitSelect) {
        unitSelect.addEventListener('change', function() {
            const selectedOption = this.options[this.selectedIndex];
            const url = selectedOption.dataset.url;
            if (url) {
                window.location.href = url;
            }
        });
    }
});

/**
 * Show the unit filter section if a unit is already selected
 * Called from the template when selected_unit_id is present
 */
function showUnitFilterSection() {
    const browseByUnitBtn = document.getElementById('browse-by-unit-btn');
    const unitFilterSection = document.getElementById('unit-filter-section');
    const searchFieldGroup = document.getElementById('search-field-group');
    
    if (browseByUnitBtn && unitFilterSection) {
        unitFilterSection.style.display = 'block';
        browseByUnitBtn.style.display = 'none';
    }
    if (searchFieldGroup) {
        searchFieldGroup.style.display = 'none';
    }
}
