/**
 * @jest-environment jsdom
 */

var STORAGE_KEY = 'wms-theme';

/**
 * Load theme module fresh for each test.
 * @returns {Object} The theme module exports.
 */
function loadTheme() {
    jest.resetModules();
    return require('./theme');
}

beforeEach(function() {
    localStorage.clear();
    document.documentElement.classList.remove('dark');
    // Reset matchMedia to default (light)
    Object.defineProperty(window, 'matchMedia', {
        writable: true,
        value: jest.fn().mockImplementation(function(query) {
            return { matches: false, media: query };
        }),
    });
});

describe('theme', function() {
    test('reads saved theme from localStorage on init', function() {
        localStorage.setItem(STORAGE_KEY, 'dark');
        loadTheme();
        expect(document.documentElement.classList.contains('dark')).toBe(true);
    });

    test('defaults to light mode when no saved preference', function() {
        var theme = loadTheme();
        expect(theme.getTheme()).toBe('light');
        expect(document.documentElement.classList.contains('dark')).toBe(false);
    });

    test('toggling adds .dark class on <html>', function() {
        var theme = loadTheme();
        var result = theme.toggleTheme();
        expect(result).toBe('dark');
        expect(document.documentElement.classList.contains('dark')).toBe(true);
    });

    test('toggling removes .dark class on <html>', function() {
        localStorage.setItem(STORAGE_KEY, 'dark');
        var theme = loadTheme();
        var result = theme.toggleTheme();
        expect(result).toBe('light');
        expect(document.documentElement.classList.contains('dark')).toBe(false);
    });

    test('toggling persists preference to localStorage', function() {
        var theme = loadTheme();
        theme.toggleTheme();
        expect(localStorage.getItem(STORAGE_KEY)).toBe('dark');
        theme.toggleTheme();
        expect(localStorage.getItem(STORAGE_KEY)).toBe('light');
    });

    test('respects prefers-color-scheme dark when no saved preference', function() {
        Object.defineProperty(window, 'matchMedia', {
            writable: true,
            value: jest.fn().mockImplementation(function(query) {
                return { matches: query === '(prefers-color-scheme: dark)', media: query };
            }),
        });
        var theme = loadTheme();
        expect(theme.getTheme()).toBe('dark');
        expect(document.documentElement.classList.contains('dark')).toBe(true);
    });

    test('saved preference overrides prefers-color-scheme', function() {
        localStorage.setItem(STORAGE_KEY, 'light');
        Object.defineProperty(window, 'matchMedia', {
            writable: true,
            value: jest.fn().mockImplementation(function(query) {
                return { matches: query === '(prefers-color-scheme: dark)', media: query };
            }),
        });
        var theme = loadTheme();
        expect(theme.getTheme()).toBe('light');
        expect(document.documentElement.classList.contains('dark')).toBe(false);
    });
});
