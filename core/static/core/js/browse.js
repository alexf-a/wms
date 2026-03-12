/**
 * Browse page — client-side drill-down navigation.
 *
 * 2-screen state machine: locations → units.
 * Screen 1 (locations) is server-rendered; screen 2 populated via API.
 * Clicking a unit navigates to the unit detail page.
 *
 * When loaded via <script> tag with data-* attributes, auto-initializes.
 * When loaded via require() (tests), exports initBrowse(config) for manual init.
 */

/**
 * Initialize the browse page drill-down navigation.
 *
 * @param {Object} config - URL templates for API endpoints.
 * @param {string} config.browseLocationsUrl - URL for the locations list API.
 * @param {string} config.browseLocationUnitsUrl - URL template for location units API (contains '/0/' placeholder).
 * @param {string} config.unitDetailUrl - URL template for unit detail page (contains '/0/' and '/PLACEHOLDER/' placeholders).
 * @returns {Object} Public API with navigateToLocationUnits, navigateBack, refreshCurrentScreen, getCurrentContext, escapeHtml, escapeAttr.
 */
function initBrowse(config) {
  'use strict';

  // --- State ---
  var currentScreen = 'locations';
  var navigationStack = [];
  var originalSubtitle = '';
  var currentLocationId = null;
  var currentLocationName = null;

  // --- DOM refs ---
  var screenLocations = document.getElementById('screen-locations');
  var screenUnits = document.getElementById('screen-units');
  var browseTitle = document.getElementById('browse-title');
  var browseSubtitle = document.getElementById('browse-subtitle');
  var backBtn = document.getElementById('browse-back-btn');

  // Save original subtitle for restoring on back navigation
  if (browseSubtitle) {
    originalSubtitle = browseSubtitle.textContent;
  }

  // --- Utilities ---

  /**
   * Escape a string for safe insertion into HTML content.
   *
   * @param {string} str - The raw string to escape.
   * @returns {string} HTML-escaped string.
   */
  function escapeHtml(str) {
    if (!str) return '';
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  /**
   * Escape a string for safe insertion into HTML attribute values.
   *
   * @param {string} str - The raw string to escape.
   * @returns {string} Attribute-safe escaped string.
   */
  function escapeAttr(str) {
    return escapeHtml(str).replace(/"/g, '&quot;');
  }

  /**
   * Return the singular or plural form of a word based on count.
   *
   * @param {number} count - The number to check.
   * @param {string} singular - The singular form.
   * @param {string} [plural] - The plural form (defaults to singular + 's').
   * @returns {string} The appropriate word form.
   */
  function pluralize(count, singular, plural) {
    return count === 1 ? singular : (plural || singular + 's');
  }

  // --- Screen management ---

  /**
   * Show a screen and hide all others. Updates back button and title for locations screen.
   *
   * @param {string} name - Screen to show: 'locations' or 'units'.
   */
  function showScreen(name) {
    currentScreen = name;
    screenLocations.classList.add('hidden');
    screenUnits.classList.add('hidden');

    if (name === 'locations') {
      screenLocations.classList.remove('hidden');
      backBtn.classList.add('hidden');
      browseTitle.textContent = 'Browse';
      browseSubtitle.textContent = originalSubtitle;
    } else if (name === 'units') {
      screenUnits.classList.remove('hidden');
      backBtn.classList.remove('hidden');
    }
  }

  // --- Card rendering ---

  /**
   * Render an HTML card for a unit with icon, name, item count, and chevron.
   *
   * @param {Object} unit - Unit data from the API.
   * @param {number} unit.user_id - Owner user ID.
   * @param {string} unit.access_token - Unit access token.
   * @param {string} unit.name - Unit display name.
   * @param {number} unit.item_count - Number of items in the unit.
   * @returns {string} HTML string for the unit card.
   */
  function renderUnitCard(unit) {
    return (
      '<a href="#" class="browse-unit-card relative flex items-center gap-3 rounded-lg border border-border bg-card p-4 no-underline hover:border-primary/50 transition-colors"' +
      ' data-unit-user-id="' + escapeAttr(String(unit.user_id)) + '"' +
      ' data-unit-access-token="' + escapeAttr(unit.access_token) + '"' +
      ' data-unit-name="' + escapeAttr(unit.name) + '">' +
      '<div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">' +
      '<svg class="h-5 w-5 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
      '<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>' +
      '<polyline points="3.27 6.96 12 12.01 20.73 6.96"/>' +
      '<line x1="12" y1="22.08" x2="12" y2="12"/>' +
      '</svg></div>' +
      '<div class="min-w-0 flex-1">' +
      '<p class="truncate text-sm font-medium text-foreground">' + escapeHtml(unit.name) + '</p>' +
      '</div>' +
      '<span class="shrink-0 text-xs text-muted-foreground">' +
      unit.item_count + ' ' + pluralize(unit.item_count, 'item') +
      '</span>' +
      '<button type="button" class="entity-menu-btn shrink-0 rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"' +
      ' data-entity-type="unit"' +
      ' data-entity-user-id="' + escapeAttr(String(unit.user_id)) + '"' +
      ' data-entity-access-token="' + escapeAttr(unit.access_token) + '"' +
      ' data-entity-name="' + escapeAttr(unit.name) + '"' +
      ' aria-label="Unit options">' +
      '<svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
      '<circle cx="12" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/>' +
      '</svg></button>' +
      '<svg class="h-4 w-4 shrink-0 text-muted-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>' +
      '</a>'
    );
  }

  /**
   * Render an empty state placeholder with icon and message.
   *
   * @param {string} message - The message to display.
   * @returns {string} HTML string for the empty state.
   */
  function renderEmptyState(message) {
    return (
      '<div class="py-12 text-center">' +
      '<svg class="mx-auto h-12 w-12 text-muted-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">' +
      '<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>' +
      '</svg>' +
      '<p class="mt-4 text-sm text-muted-foreground">' + escapeHtml(message) + '</p>' +
      '</div>'
    );
  }

  // --- Screen rendering ---

  /**
   * Populate the units screen with unit cards or an empty state.
   *
   * @param {Array<Object>} units - Array of unit objects from the API.
   */
  function renderUnitsScreen(units) {
    var html = '';
    if (units.length === 0) {
      html = renderEmptyState('No units in this location');
    } else {
      for (var i = 0; i < units.length; i++) {
        html += renderUnitCard(units[i]);
      }
    }
    screenUnits.innerHTML = html;
  }

  // --- Navigation ---

  /**
   * Fetch units for a location and navigate to the units screen.
   *
   * @param {string} locationId - The location ID to fetch units for.
   * @param {string} locationName - The location name to display in the title.
   */
  function navigateToLocationUnits(locationId, locationName) {
    navigationStack.push({ screen: 'locations' });
    currentLocationId = locationId;
    currentLocationName = locationName;
    browseTitle.textContent = locationName;
    browseSubtitle.textContent = 'Loading...';

    var url = config.browseLocationUnitsUrl.replace('/0/', '/' + locationId + '/');
    apiFetch(url).then(function (res) {
      return res.json();
    }).then(function (data) {
      browseSubtitle.textContent = data.units.length + ' ' + pluralize(data.units.length, 'unit');
      renderUnitsScreen(data.units);
      showScreen('units');
    }).catch(function () {
      browseSubtitle.textContent = 'Failed to load';
    });
  }

  /**
   * Navigate to a unit's detail page.
   *
   * @param {string} userId - The unit owner's user ID.
   * @param {string} accessToken - The unit's access token.
   */
  function navigateToUnit(userId, accessToken) {
    var url = config.unitDetailUrl
      .replace('/0/', '/' + userId + '/')
      .replace('/PLACEHOLDER/', '/' + accessToken + '/');
    window.location.href = url;
  }

  /**
   * Navigate back to the previous screen in the navigation stack.
   */
  function navigateBack() {
    if (navigationStack.length === 0) return;
    var prev = navigationStack.pop();
    if (prev.screen === 'locations') {
      currentLocationId = null;
      currentLocationName = null;
    }
    showScreen(prev.screen);
  }

  /**
   * Re-fetch and re-render the current screen. Used by browse_crud.js after mutations.
   * Screen 1 (locations, server-rendered): triggers a full page reload.
   * Screen 2 (units): re-calls navigateToLocationUnits with stored context.
   */
  function refreshCurrentScreen() {
    if (currentScreen === 'locations') {
      window.location.reload();
    } else if (currentScreen === 'units' && currentLocationId) {
      navigationStack.pop();
      navigateToLocationUnits(currentLocationId, currentLocationName);
    }
  }

  /**
   * Return the current navigation context for use by browse_crud.js.
   *
   * @returns {Object} Context with screen, locationId, locationName.
   */
  function getCurrentContext() {
    return {
      screen: currentScreen,
      locationId: currentLocationId,
      locationName: currentLocationName,
    };
  }

  // --- Event delegation ---

  /**
   * Attach click event delegation for location and unit cards within a container.
   *
   * @param {HTMLElement} container - The container element to listen on.
   */
  function handleCardClick(container) {
    container.addEventListener('click', function (e) {
      // Don't navigate when clicking entity menu buttons
      if (e.target.closest('.entity-menu-btn')) {
        e.preventDefault();
        return;
      }

      var locationCard = e.target.closest('.browse-location-card');
      if (locationCard) {
        e.preventDefault();
        navigateToLocationUnits(
          locationCard.dataset.locationId,
          locationCard.dataset.locationName
        );
        return;
      }

      var unitCard = e.target.closest('.browse-unit-card');
      if (unitCard) {
        e.preventDefault();
        navigateToUnit(
          unitCard.dataset.unitUserId,
          unitCard.dataset.unitAccessToken
        );
      }
    });
  }

  // Location screen: server-rendered cards
  handleCardClick(screenLocations);
  // Units screen: JS-rendered cards
  handleCardClick(screenUnits);

  // Back button
  backBtn.addEventListener('click', navigateBack);

  // Initialize on locations screen
  showScreen('locations');

  // Return public API for testing
  return {
    navigateToLocationUnits: navigateToLocationUnits,
    navigateToUnit: navigateToUnit,
    navigateBack: navigateBack,
    refreshCurrentScreen: refreshCurrentScreen,
    getCurrentContext: getCurrentContext,
    escapeHtml: escapeHtml,
    escapeAttr: escapeAttr,
  };
}

// Auto-initialize when loaded via <script> tag with data attributes
if (typeof document !== 'undefined' && document.currentScript) {
  var scriptTag = document.currentScript;
  var browseApi = initBrowse({
    browseLocationsUrl: scriptTag.getAttribute('data-browse-locations-url'),
    browseLocationUnitsUrl: scriptTag.getAttribute('data-browse-location-units-url'),
    unitDetailUrl: scriptTag.getAttribute('data-unit-detail-url'),
  });
  var browseApp = document.getElementById('browse-app');
  if (browseApp) {
    browseApp._browseApi = browseApi;
  }
}

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { initBrowse: initBrowse };
}
