/**
 * Browse CRUD — dialog management for create/edit/delete of Locations and Units.
 *
 * Works alongside browse.js: reads the browse API from the DOM to refresh
 * the current screen after mutations. Uses apiFetch() from fetch_utils.js
 * for CSRF-safe requests.
 *
 * When loaded via <script> tag with data-* attributes, auto-initializes.
 * When loaded via require() (tests), exports initBrowseCrud(config) for manual init.
 */

/**
 * Initialize browse CRUD dialog management.
 *
 * @param {Object} config - URL templates for API endpoints.
 * @param {string} config.createLocationUrl - URL for creating a location.
 * @param {string} config.updateLocationUrl - URL template for updating a location (contains '/0/' placeholder).
 * @param {string} config.deleteLocationUrl - URL template for deleting a location (contains '/0/' placeholder).
 * @param {string} config.createUnitUrl - URL for creating a unit.
 * @param {string} config.unitDetailJsonUrl - URL template for unit detail JSON (contains '/0/' and '/PLACEHOLDER/').
 * @param {string} config.updateUnitUrl - URL template for updating a unit (contains '/0/' and '/PLACEHOLDER/').
 * @param {string} config.deleteUnitUrl - URL template for deleting a unit (contains '/0/' and '/PLACEHOLDER/').
 * @param {string} config.containerOptionsUrl - URL for fetching container options.
 * @returns {Object} Public API for testing.
 */
function initBrowseCrud(config) {
  'use strict';

  var CLOSING_DURATION = 150;

  // --- DOM refs ---
  var browseApp = document.getElementById('browse-app');

  var createLocationDialog = document.getElementById('create-location-dialog');
  var createUnitDialog = document.getElementById('create-unit-dialog');
  var editLocationDialog = document.getElementById('edit-location-dialog');
  var editUnitDialog = document.getElementById('edit-unit-dialog');
  var deleteLocationDialog = document.getElementById('delete-location-dialog');
  var deleteUnitDialog = document.getElementById('delete-unit-dialog');

  // --- Helpers ---

  /**
   * Get the browse API stored on the browse-app element.
   *
   * @returns {Object|null} The browse API object, or null if not available.
   */
  function getBrowseApi() {
    return browseApp ? browseApp._browseApi : null;
  }

  /**
   * Refresh the current browse screen after a mutation.
   */
  function refreshScreen() {
    var api = getBrowseApi();
    if (api && typeof api.refreshCurrentScreen === 'function') {
      api.refreshCurrentScreen();
    }
  }

  /**
   * Open a dialog with showModal().
   *
   * @param {HTMLDialogElement} dialog - The dialog element to open.
   */
  function openDialog(dialog) {
    if (!dialog) return;
    dialog.showModal();
  }

  /**
   * Close a dialog with closing animation.
   *
   * @param {HTMLDialogElement} dialog - The dialog element to close.
   */
  function closeDialog(dialog) {
    if (!dialog) return;
    dialog.classList.add('dialog--closing');
    setTimeout(function () {
      dialog.classList.remove('dialog--closing');
      dialog.close();
    }, CLOSING_DURATION);
  }

  /**
   * Show an error message in a dialog's error element.
   *
   * @param {HTMLElement} el - The error paragraph element.
   * @param {string} msg - The error message to display.
   */
  function showError(el, msg) {
    if (!el) return;
    el.textContent = msg;
    el.classList.remove('hidden');
  }

  /**
   * Hide a dialog's error element.
   *
   * @param {HTMLElement} el - The error paragraph element.
   */
  function hideError(el) {
    if (!el) return;
    el.textContent = '';
    el.classList.add('hidden');
  }

  /**
   * Populate a container <select> with locations and units from the API.
   *
   * @param {HTMLSelectElement} select - The select element to populate.
   * @param {number|null} excludeUnitId - Unit ID to exclude from list (for edit dialog).
   * @param {string} selectedValue - The value to pre-select (e.g. 'location:5' or 'unit:3').
   * @returns {Promise<void>}
   */
  function populateContainerSelect(select, excludeUnitId, selectedValue) {
    var url = config.containerOptionsUrl;
    if (excludeUnitId) {
      url += '?exclude_unit=' + excludeUnitId;
    }
    return apiFetch(url).then(function (res) {
      return res.json();
    }).then(function (data) {
      // Clear existing options except the first "no container" option
      while (select.options.length > 1) {
        select.remove(1);
      }

      // Add location optgroup
      if (data.locations.length > 0) {
        var locGroup = document.createElement('optgroup');
        locGroup.label = 'Locations';
        for (var i = 0; i < data.locations.length; i++) {
          var opt = document.createElement('option');
          opt.value = 'location:' + data.locations[i].id;
          opt.textContent = data.locations[i].name;
          locGroup.appendChild(opt);
        }
        select.appendChild(locGroup);
      }

      // Add unit optgroup
      if (data.units.length > 0) {
        var unitGroup = document.createElement('optgroup');
        unitGroup.label = 'Units';
        for (var j = 0; j < data.units.length; j++) {
          var uopt = document.createElement('option');
          uopt.value = 'unit:' + data.units[j].id;
          uopt.textContent = data.units[j].name;
          unitGroup.appendChild(uopt);
        }
        select.appendChild(unitGroup);
      }

      // Set selected value
      if (selectedValue) {
        select.value = selectedValue;
      }
    });
  }

  /**
   * Parse a container select value into location_id and parent_unit_id.
   *
   * @param {string} value - The select value (e.g. 'location:5', 'unit:3', or '').
   * @returns {Object} Object with location_id and parent_unit_id (both nullable).
   */
  function parseContainerValue(value) {
    var result = { location_id: null, parent_unit_id: null };
    if (!value) return result;
    var parts = value.split(':');
    if (parts[0] === 'location') {
      result.location_id = parseInt(parts[1], 10);
    } else if (parts[0] === 'unit') {
      result.parent_unit_id = parseInt(parts[1], 10);
    }
    return result;
  }

  // --- Create Location ---

  /**
   * Open the create location dialog with empty fields.
   */
  function openCreateLocationDialog() {
    document.getElementById('create-location-name').value = '';
    document.getElementById('create-location-address').value = '';
    hideError(document.getElementById('create-location-error'));
    openDialog(createLocationDialog);
    document.getElementById('create-location-name').focus();
  }

  /**
   * Submit the create location form.
   */
  function submitCreateLocation() {
    var name = document.getElementById('create-location-name').value.trim();
    var address = document.getElementById('create-location-address').value.trim();
    var errorEl = document.getElementById('create-location-error');

    if (!name) {
      showError(errorEl, 'Name is required.');
      return;
    }

    var body = { name: name };
    if (address) body.address = address;

    apiFetch(config.createLocationUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(function (res) {
      if (res.ok) {
        closeDialog(createLocationDialog);
        refreshScreen();
      } else {
        return res.json().then(function (data) {
          showError(errorEl, data.error || 'Failed to create location.');
        });
      }
    }).catch(function () {
      showError(errorEl, 'Network error. Please try again.');
    });
  }

  // --- Create Unit ---

  /**
   * Open the create unit dialog. Fetches container options and optionally pre-selects a location.
   *
   * @param {number|null} defaultLocationId - Location ID to pre-select in container picker.
   */
  function openCreateUnitDialog(defaultLocationId) {
    document.getElementById('create-unit-name').value = '';
    hideError(document.getElementById('create-unit-error'));

    var select = document.getElementById('create-unit-container');
    var preselect = defaultLocationId ? 'location:' + defaultLocationId : '';
    populateContainerSelect(select, null, preselect).then(function () {
      openDialog(createUnitDialog);
      document.getElementById('create-unit-name').focus();
    });
  }

  /**
   * Submit the create unit form.
   */
  function submitCreateUnit() {
    var name = document.getElementById('create-unit-name').value.trim();
    var containerValue = document.getElementById('create-unit-container').value;
    var errorEl = document.getElementById('create-unit-error');

    if (!name) {
      showError(errorEl, 'Name is required.');
      return;
    }

    var container = parseContainerValue(containerValue);
    var body = { name: name };
    if (container.location_id) body.location_id = container.location_id;

    apiFetch(config.createUnitUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(function (res) {
      if (res.ok) {
        closeDialog(createUnitDialog);
        refreshScreen();
      } else {
        return res.json().then(function (data) {
          showError(errorEl, data.error || 'Failed to create unit.');
        });
      }
    }).catch(function () {
      showError(errorEl, 'Network error. Please try again.');
    });
  }

  // --- Edit Location ---

  /**
   * Open the edit location dialog with pre-populated fields.
   *
   * @param {number} id - The location ID.
   * @param {string} name - The current location name.
   * @param {string} address - The current location address.
   */
  function openEditLocationDialog(id, name, address) {
    document.getElementById('edit-location-id').value = id;
    document.getElementById('edit-location-name').value = name || '';
    document.getElementById('edit-location-address').value = address || '';
    hideError(document.getElementById('edit-location-error'));
    openDialog(editLocationDialog);
    document.getElementById('edit-location-name').focus();
  }

  /**
   * Submit the edit location form.
   */
  function submitEditLocation() {
    var id = document.getElementById('edit-location-id').value;
    var name = document.getElementById('edit-location-name').value.trim();
    var address = document.getElementById('edit-location-address').value.trim();
    var errorEl = document.getElementById('edit-location-error');

    if (!name) {
      showError(errorEl, 'Name is required.');
      return;
    }

    var url = config.updateLocationUrl.replace('/0/', '/' + id + '/');
    var body = { name: name };
    if (address) body.address = address;

    apiFetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(function (res) {
      if (res.ok) {
        closeDialog(editLocationDialog);
        refreshScreen();
      } else {
        return res.json().then(function (data) {
          showError(errorEl, data.error || 'Failed to update location.');
        });
      }
    }).catch(function () {
      showError(errorEl, 'Network error. Please try again.');
    });
  }

  // --- Edit Unit ---

  /**
   * Open the edit unit dialog. Fetches unit detail and container options.
   *
   * @param {number} userId - The unit owner's user ID.
   * @param {string} accessToken - The unit's access token.
   */
  function openEditUnitDialog(userId, accessToken) {
    hideError(document.getElementById('edit-unit-error'));

    var detailUrl = config.unitDetailJsonUrl
      .replace('/0/', '/' + userId + '/')
      .replace('/PLACEHOLDER/', '/' + accessToken + '/');

    apiFetch(detailUrl).then(function (res) {
      return res.json();
    }).then(function (data) {
      document.getElementById('edit-unit-user-id').value = userId;
      document.getElementById('edit-unit-access-token').value = accessToken;
      document.getElementById('edit-unit-name').value = data.name || '';
      document.getElementById('edit-unit-description').value = data.description || '';

      // Dimensions
      document.getElementById('edit-unit-length').value = data.length != null ? data.length : '';
      document.getElementById('edit-unit-width').value = data.width != null ? data.width : '';
      document.getElementById('edit-unit-height').value = data.height != null ? data.height : '';
      document.getElementById('edit-unit-dimensions-unit').value = data.dimensions_unit || '';

      // Container select
      var select = document.getElementById('edit-unit-container');
      var selectedContainer = '';
      if (data.location_id) {
        selectedContainer = 'location:' + data.location_id;
      } else if (data.parent_unit_id) {
        selectedContainer = 'unit:' + data.parent_unit_id;
      }
      return populateContainerSelect(select, data.id, selectedContainer);
    }).then(function () {
      openDialog(editUnitDialog);
      document.getElementById('edit-unit-name').focus();
    });
  }

  /**
   * Submit the edit unit form.
   */
  function submitEditUnit() {
    var userId = document.getElementById('edit-unit-user-id').value;
    var accessToken = document.getElementById('edit-unit-access-token').value;
    var name = document.getElementById('edit-unit-name').value.trim();
    var description = document.getElementById('edit-unit-description').value.trim();
    var containerValue = document.getElementById('edit-unit-container').value;
    var errorEl = document.getElementById('edit-unit-error');

    if (!name) {
      showError(errorEl, 'Name is required.');
      return;
    }

    var container = parseContainerValue(containerValue);
    var body = { name: name };
    if (description) body.description = description;
    if (container.location_id) body.location_id = container.location_id;
    if (container.parent_unit_id) body.parent_unit_id = container.parent_unit_id;

    // Dimensions
    var length = document.getElementById('edit-unit-length').value;
    var width = document.getElementById('edit-unit-width').value;
    var height = document.getElementById('edit-unit-height').value;
    var dimUnit = document.getElementById('edit-unit-dimensions-unit').value;

    if (length || width || height || dimUnit) {
      body.length = parseFloat(length) || null;
      body.width = parseFloat(width) || null;
      body.height = parseFloat(height) || null;
      body.dimensions_unit = dimUnit || null;
    }

    var url = config.updateUnitUrl
      .replace('/0/', '/' + userId + '/')
      .replace('/PLACEHOLDER/', '/' + accessToken + '/');

    apiFetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(function (res) {
      if (res.ok) {
        closeDialog(editUnitDialog);
        refreshScreen();
      } else {
        return res.json().then(function (data) {
          showError(errorEl, data.error || 'Failed to update unit.');
        });
      }
    }).catch(function () {
      showError(errorEl, 'Network error. Please try again.');
    });
  }

  // --- Delete Location ---

  /**
   * Open the delete location confirmation dialog.
   *
   * @param {number} id - The location ID.
   * @param {string} name - The location name to display.
   */
  function openDeleteLocationDialog(id, name) {
    document.getElementById('delete-location-id').value = id;
    document.getElementById('delete-location-name').textContent = name;
    openDialog(deleteLocationDialog);
  }

  /**
   * Submit the delete location request.
   */
  function submitDeleteLocation() {
    var id = document.getElementById('delete-location-id').value;
    var url = config.deleteLocationUrl.replace('/0/', '/' + id + '/');

    apiFetch(url, { method: 'POST' }).then(function (res) {
      if (res.ok) {
        closeDialog(deleteLocationDialog);
        refreshScreen();
      }
    });
  }

  // --- Delete Unit ---

  /**
   * Open the delete unit confirmation dialog. Fetches item count for the warning.
   *
   * @param {number} userId - The unit owner's user ID.
   * @param {string} accessToken - The unit's access token.
   * @param {string} name - The unit name to display.
   */
  function openDeleteUnitDialog(userId, accessToken, name) {
    document.getElementById('delete-unit-user-id').value = userId;
    document.getElementById('delete-unit-access-token').value = accessToken;
    document.getElementById('delete-unit-name').textContent = name;
    document.getElementById('delete-unit-warning').textContent = 'Loading details...';
    openDialog(deleteUnitDialog);

    // Fetch unit items to get counts for the warning
    var detailUrl = config.unitDetailJsonUrl
      .replace('/0/', '/' + userId + '/')
      .replace('/PLACEHOLDER/', '/' + accessToken + '/');

    apiFetch(detailUrl).then(function (res) {
      return res.json();
    }).then(function () {
      // We fetched detail, but we need the browse unit items API for item/child counts
      // Use the browse API context to build the URL
      var browseApi = getBrowseApi();
      if (!browseApi) return;
      // Build a simple warning without the item count
      document.getElementById('delete-unit-warning').textContent =
        'All items in this unit will be permanently deleted. Any sub-units will become standalone. This action cannot be undone.';
    }).catch(function () {
      document.getElementById('delete-unit-warning').textContent =
        'All items in this unit will be permanently deleted. This action cannot be undone.';
    });
  }

  /**
   * Submit the delete unit request.
   */
  function submitDeleteUnit() {
    var userId = document.getElementById('delete-unit-user-id').value;
    var accessToken = document.getElementById('delete-unit-access-token').value;
    var url = config.deleteUnitUrl
      .replace('/0/', '/' + userId + '/')
      .replace('/PLACEHOLDER/', '/' + accessToken + '/');

    apiFetch(url, { method: 'POST' }).then(function (res) {
      if (res.ok) {
        closeDialog(deleteUnitDialog);
        refreshScreen();
      }
    });
  }

  // --- Entity Menu ---

  var activeMenu = null;

  /**
   * Create and position an entity menu dropdown next to a button.
   *
   * @param {HTMLElement} btn - The entity menu button that was clicked.
   */
  function toggleEntityMenu(btn) {
    closeAllMenus();

    var entityType = btn.dataset.entityType;
    var menu = document.createElement('div');
    menu.className = 'entity-menu absolute z-50 rounded-md border border-border bg-card py-1 shadow-lg';
    menu.style.minWidth = '120px';

    if (entityType === 'location') {
      menu.innerHTML =
        '<button type="button" class="entity-menu-action w-full px-4 py-2 text-left text-sm text-foreground hover:bg-accent" data-action="edit">Edit</button>' +
        '<button type="button" class="entity-menu-action w-full px-4 py-2 text-left text-sm text-destructive hover:bg-destructive/10" data-action="delete">Delete</button>';
    } else {
      menu.innerHTML =
        '<button type="button" class="entity-menu-action w-full px-4 py-2 text-left text-sm text-foreground hover:bg-accent" data-action="edit">Edit</button>' +
        '<button type="button" class="entity-menu-action w-full px-4 py-2 text-left text-sm text-destructive hover:bg-destructive/10" data-action="delete">Delete</button>';
    }

    // Position the menu
    var card = btn.closest('.browse-location-card, .browse-unit-card');
    if (card) {
      card.style.position = 'relative';
    }
    menu.style.position = 'absolute';
    menu.style.right = '0';
    menu.style.top = btn.offsetTop + btn.offsetHeight + 'px';

    // Handle menu action clicks
    menu.addEventListener('click', function (e) {
      var actionBtn = e.target.closest('.entity-menu-action');
      if (!actionBtn) return;
      e.stopPropagation();
      var action = actionBtn.dataset.action;

      if (entityType === 'location') {
        var locationId = btn.dataset.entityId;
        var locationName = btn.dataset.entityName;
        var locationAddress = btn.dataset.entityAddress || '';
        if (action === 'edit') {
          openEditLocationDialog(locationId, locationName, locationAddress);
        } else if (action === 'delete') {
          openDeleteLocationDialog(locationId, locationName);
        }
      } else if (entityType === 'unit') {
        var userId = btn.dataset.entityUserId;
        var accessToken = btn.dataset.entityAccessToken;
        var unitName = btn.dataset.entityName;
        if (action === 'edit') {
          openEditUnitDialog(userId, accessToken);
        } else if (action === 'delete') {
          openDeleteUnitDialog(userId, accessToken, unitName);
        }
      }

      closeAllMenus();
    });

    // Insert menu into the card
    if (card) {
      card.appendChild(menu);
    } else {
      btn.parentNode.appendChild(menu);
    }
    activeMenu = menu;
  }

  /**
   * Close all open entity menus.
   */
  function closeAllMenus() {
    if (activeMenu) {
      activeMenu.remove();
      activeMenu = null;
    }
  }

  // --- Event Delegation ---

  // Entity menu buttons (works for both server-rendered and JS-rendered cards)
  document.addEventListener('click', function (e) {
    var menuBtn = e.target.closest('.entity-menu-btn');
    if (menuBtn) {
      e.preventDefault();
      e.stopPropagation();
      toggleEntityMenu(menuBtn);
      return;
    }

    // Close menus when clicking outside
    if (activeMenu && !e.target.closest('.entity-menu')) {
      closeAllMenus();
    }
  });

  // Create buttons
  var createLocationBtn = document.getElementById('browse-create-location-btn');
  if (createLocationBtn) {
    createLocationBtn.addEventListener('click', function (e) {
      e.preventDefault();
      openCreateLocationDialog();
    });
  }

  var createUnitBtn = document.getElementById('browse-create-unit-btn');
  if (createUnitBtn) {
    createUnitBtn.addEventListener('click', function (e) {
      e.preventDefault();
      var api = getBrowseApi();
      var ctx = api ? api.getCurrentContext() : {};
      openCreateUnitDialog(ctx.locationId || null);
    });
  }

  // Dialog submit buttons
  if (createLocationDialog) {
    document.getElementById('create-location-submit').addEventListener('click', submitCreateLocation);
    document.getElementById('create-location-cancel').addEventListener('click', function () { closeDialog(createLocationDialog); });
  }
  if (createUnitDialog) {
    document.getElementById('create-unit-submit').addEventListener('click', submitCreateUnit);
    document.getElementById('create-unit-cancel').addEventListener('click', function () { closeDialog(createUnitDialog); });
  }
  if (editLocationDialog) {
    document.getElementById('edit-location-submit').addEventListener('click', submitEditLocation);
    document.getElementById('edit-location-cancel').addEventListener('click', function () { closeDialog(editLocationDialog); });
  }
  if (editUnitDialog) {
    document.getElementById('edit-unit-submit').addEventListener('click', submitEditUnit);
    document.getElementById('edit-unit-cancel').addEventListener('click', function () { closeDialog(editUnitDialog); });
  }
  if (deleteLocationDialog) {
    document.getElementById('delete-location-submit').addEventListener('click', submitDeleteLocation);
    document.getElementById('delete-location-cancel').addEventListener('click', function () { closeDialog(deleteLocationDialog); });
  }
  if (deleteUnitDialog) {
    document.getElementById('delete-unit-submit').addEventListener('click', submitDeleteUnit);
    document.getElementById('delete-unit-cancel').addEventListener('click', function () { closeDialog(deleteUnitDialog); });
  }

  // Close dialogs on backdrop click
  [createLocationDialog, createUnitDialog, editLocationDialog, editUnitDialog, deleteLocationDialog, deleteUnitDialog].forEach(function (dialog) {
    if (!dialog) return;
    dialog.addEventListener('click', function (e) {
      if (e.target === dialog) {
        closeDialog(dialog);
      }
    });
  });

  // Return public API for testing
  return {
    openCreateLocationDialog: openCreateLocationDialog,
    openCreateUnitDialog: openCreateUnitDialog,
    openEditLocationDialog: openEditLocationDialog,
    openEditUnitDialog: openEditUnitDialog,
    openDeleteLocationDialog: openDeleteLocationDialog,
    openDeleteUnitDialog: openDeleteUnitDialog,
    closeAllMenus: closeAllMenus,
    parseContainerValue: parseContainerValue,
  };
}

// Auto-initialize when loaded via <script> tag with data attributes
if (typeof document !== 'undefined' && document.currentScript) {
  var crudScriptTag = document.currentScript;
  initBrowseCrud({
    createLocationUrl: crudScriptTag.getAttribute('data-create-location-url'),
    updateLocationUrl: crudScriptTag.getAttribute('data-update-location-url'),
    deleteLocationUrl: crudScriptTag.getAttribute('data-delete-location-url'),
    createUnitUrl: crudScriptTag.getAttribute('data-create-unit-url'),
    unitDetailJsonUrl: crudScriptTag.getAttribute('data-unit-detail-json-url'),
    updateUnitUrl: crudScriptTag.getAttribute('data-update-unit-url'),
    deleteUnitUrl: crudScriptTag.getAttribute('data-delete-unit-url'),
    containerOptionsUrl: crudScriptTag.getAttribute('data-container-options-url'),
  });
}

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { initBrowseCrud: initBrowseCrud };
}
