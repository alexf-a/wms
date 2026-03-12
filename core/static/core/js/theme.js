/**
 * Theme toggle module.
 * Reads/writes dark mode preference to localStorage and toggles the `.dark`
 * class on the document element. Respects `prefers-color-scheme` when no
 * saved preference exists.
 */

/** @type {string} localStorage key for theme preference */
var STORAGE_KEY = 'wms-theme';

/**
 * Get the current effective theme.
 * Priority: localStorage > prefers-color-scheme > 'light'.
 * @returns {'light'|'dark'} The current theme.
 */
function getTheme() {
    var saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'dark' || saved === 'light') return saved;
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        return 'dark';
    }
    return 'light';
}

/**
 * Apply the given theme to the document element.
 * @param {'light'|'dark'} theme - The theme to apply.
 * @returns {void}
 */
function applyTheme(theme) {
    if (theme === 'dark') {
        document.documentElement.classList.add('dark');
    } else {
        document.documentElement.classList.remove('dark');
    }
}

/**
 * Toggle between light and dark themes.
 * Saves the new preference to localStorage.
 * @returns {'light'|'dark'} The new active theme.
 */
function toggleTheme() {
    var current = document.documentElement.classList.contains('dark') ? 'dark' : 'light';
    var next = current === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    localStorage.setItem(STORAGE_KEY, next);
    return next;
}

/**
 * Initialize theme on page load.
 * Applies saved or system preference immediately.
 * @returns {void}
 */
function initTheme() {
    applyTheme(getTheme());
}

// Apply immediately (before DOMContentLoaded) to prevent flash of wrong theme
initTheme();

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { getTheme: getTheme, applyTheme: applyTheme, toggleTheme: toggleTheme, initTheme: initTheme, STORAGE_KEY: STORAGE_KEY };
}
