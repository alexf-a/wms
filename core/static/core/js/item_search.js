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
    
    if (browseByBinBtn && binFilterSection) {
        browseByBinBtn.addEventListener('click', function() {
            revealSection(binFilterSection, browseByBinBtn, binSelect);
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
    
    if (browseByBinBtn && binFilterSection) {
        binFilterSection.style.display = 'block';
        browseByBinBtn.style.display = 'none';
    }
}
