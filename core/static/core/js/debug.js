/**
 * WMS Debug Utility
 * Provides conditional logging based on DEBUG mode
 * 
 * Usage:
 *   debugLog('message', 'optional', 'args');
 *   debugError('error message', error);
 */

// Get DEBUG flag from data attribute on html element
const WMS_DEBUG = document.documentElement.dataset.debug === 'true';

/**
 * Log a debug message (only in DEBUG mode)
 * @param {...*} args - Arguments to log
 */
function debugLog(...args) {
    if (WMS_DEBUG) {
        console.log(...args);
    }
}

/**
 * Log an error message (only in DEBUG mode)
 * @param {...*} args - Arguments to log
 */
function debugError(...args) {
    if (WMS_DEBUG) {
        console.error(...args);
    }
}

/**
 * Log a warning message (only in DEBUG mode)
 * @param {...*} args - Arguments to log
 */
function debugWarn(...args) {
    if (WMS_DEBUG) {
        console.warn(...args);
    }
}

/**
 * Always log an error message (regardless of DEBUG mode)
 * Use this for errors that must be logged in production
 * @param {...*} args - Arguments to log
 */
function errorLog(...args) {
    console.error(...args);
}
