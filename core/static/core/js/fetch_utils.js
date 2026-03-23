/**
 * fetch_utils.js — thin wrapper around fetch() with CSRF token injection.
 *
 * Provides:
 *   apiFetch(url, options) — fetch() wrapper that auto-injects the
 *       X-CSRFToken header for non-GET requests.
 *
 * The CSRF token is read from the first <input name="csrfmiddlewaretoken">
 * on the page (Django's {% csrf_token %} tag), or from the `csrftoken` cookie
 * as a fallback.
 */

/**
 * Read the CSRF token from the page.
 * @returns {string}
 */
function _getCSRFToken() {
    // 1. Hidden input (preferred — always present when {% csrf_token %} is used)
    var input = document.querySelector('[name=csrfmiddlewaretoken]');
    if (input) return input.value;

    // 2. Cookie fallback
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? match[1] : '';
}

/**
 * Wrapper around fetch() that automatically adds Django's CSRF token
 * for mutating requests.
 *
 * @param {string} url
 * @param {RequestInit} [options={}]
 * @returns {Promise<Response>}
 */
async function apiFetch(url, options) {
    options = options || {};
    var method = (options.method || 'GET').toUpperCase();

    // Inject CSRF header for non-safe methods
    if (method !== 'GET' && method !== 'HEAD') {
        options.headers = Object.assign(
            { 'X-CSRFToken': _getCSRFToken() },
            options.headers || {}
        );
    }

    // Always send cookies
    if (!options.credentials) {
        options.credentials = 'same-origin';
    }

    return fetch(url, options);
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { _getCSRFToken: _getCSRFToken, apiFetch: apiFetch };
}
