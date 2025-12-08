/**
 * Item Search Page JavaScript
 * Handles search input focus and browse-by-bin toggle functionality
 * 
 * Dependencies: ui_utils.js (revealSection)
 */

document.addEventListener('DOMContentLoaded', function() {
    // Focus search input on page load
    const searchInput = document.getElementById('id_query');
    if (searchInput) {
        searchInput.focus();
    }

    // Browse by Bin toggle functionality
    const browseByBinBtn = document.getElementById('browse-by-bin-btn');
    const binFilterSection = document.getElementById('bin-filter-section');
    const binSelect = document.getElementById('bin_filter');
    const searchFieldGroup = document.getElementById('search-field-group');
    
    if (browseByBinBtn && binFilterSection) {
        browseByBinBtn.addEventListener('click', function() {
            // Hide the search bar
            if (searchFieldGroup) {
                searchFieldGroup.style.display = 'none';
            }
            revealSection(binFilterSection, browseByBinBtn, binSelect);
        });
    }

    // Navigate to bin detail page when a bin is selected
    if (binSelect) {
        binSelect.addEventListener('change', function() {
            const selectedOption = this.options[this.selectedIndex];
            const url = selectedOption.dataset.url;
            if (url) {
                window.location.href = url;
            }
        });
    }
});

/**
 * Show the bin filter section if a bin is already selected
 * Called from the template when selected_bin_id is present
 */
function showBinFilterSection() {
    const browseByBinBtn = document.getElementById('browse-by-bin-btn');
    const binFilterSection = document.getElementById('bin-filter-section');
    const searchFieldGroup = document.getElementById('search-field-group');
    
    if (browseByBinBtn && binFilterSection) {
        binFilterSection.style.display = 'block';
        browseByBinBtn.style.display = 'none';
    }
    if (searchFieldGroup) {
        searchFieldGroup.style.display = 'none';
    }
}
