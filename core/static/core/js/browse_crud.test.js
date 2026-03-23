const { initBrowseCrud } = require('./browse_crud');

// --- Helpers ---

var CONFIG = {
  createLocationUrl: '/api/locations/create/',
  updateLocationUrl: '/api/locations/0/update/',
  deleteLocationUrl: '/api/locations/0/delete/',
  createUnitUrl: '/api/units/create/',
  unitDetailJsonUrl: '/api/units/0/PLACEHOLDER/detail/',
  updateUnitUrl: '/api/units/0/PLACEHOLDER/update/',
  deleteUnitUrl: '/api/units/0/PLACEHOLDER/delete/',
  containerOptionsUrl: '/api/container-options/',
};

/**
 * Build a full browse+crud DOM fixture with dialogs and cards.
 */
function setupDom() {
  document.body.innerHTML = [
    '<div id="browse-app">',
    '  <button id="browse-back-btn" class="hidden" type="button">Back</button>',
    '  <h1 id="browse-title">Browse</h1>',
    '  <p id="browse-subtitle">1 location</p>',
    '  <button id="browse-create-location-btn" type="button">+ Location</button>',
    '  <button id="browse-create-unit-btn" type="button">+ Unit</button>',
    '  <div id="screen-locations">',
    '    <a href="#" class="browse-location-card" data-location-id="10" data-location-name="My House">',
    '      <button type="button" class="entity-menu-btn"',
    '              data-entity-type="location"',
    '              data-entity-id="10"',
    '              data-entity-name="My House"',
    '              data-entity-address="123 Main St">Menu</button>',
    '      My House',
    '    </a>',
    '    <a href="#" class="browse-unit-card" data-unit-user-id="1" data-unit-access-token="abc123" data-unit-name="Storage Bin">',
    '      <button type="button" class="entity-menu-btn"',
    '              data-entity-type="unit"',
    '              data-entity-user-id="1"',
    '              data-entity-access-token="abc123"',
    '              data-entity-name="Storage Bin">Menu</button>',
    '      Storage Bin',
    '    </a>',
    '  </div>',
    '  <div id="screen-units" class="hidden"></div>',
    '  <div id="screen-items" class="hidden"></div>',
    '</div>',

    // Create Location Dialog
    '<dialog id="create-location-dialog">',
    '  <input type="text" id="create-location-name">',
    '  <input type="text" id="create-location-address">',
    '  <p id="create-location-error" class="hidden"></p>',
    '  <button id="create-location-submit" type="button">Create</button>',
    '  <button id="create-location-cancel" type="button">Cancel</button>',
    '</dialog>',

    // Create Unit Dialog
    '<dialog id="create-unit-dialog">',
    '  <input type="text" id="create-unit-name">',
    '  <select id="create-unit-container"><option value="">No container</option></select>',
    '  <p id="create-unit-error" class="hidden"></p>',
    '  <button id="create-unit-submit" type="button">Create</button>',
    '  <button id="create-unit-cancel" type="button">Cancel</button>',
    '</dialog>',

    // Edit Location Dialog
    '<dialog id="edit-location-dialog">',
    '  <input type="hidden" id="edit-location-id">',
    '  <input type="text" id="edit-location-name">',
    '  <input type="text" id="edit-location-address">',
    '  <p id="edit-location-error" class="hidden"></p>',
    '  <button id="edit-location-submit" type="button">Save</button>',
    '  <button id="edit-location-cancel" type="button">Cancel</button>',
    '</dialog>',

    // Edit Unit Dialog
    '<dialog id="edit-unit-dialog">',
    '  <input type="hidden" id="edit-unit-user-id">',
    '  <input type="hidden" id="edit-unit-access-token">',
    '  <input type="text" id="edit-unit-name">',
    '  <textarea id="edit-unit-description"></textarea>',
    '  <select id="edit-unit-container"><option value="">No container</option></select>',
    '  <input type="number" id="edit-unit-length">',
    '  <input type="number" id="edit-unit-width">',
    '  <input type="number" id="edit-unit-height">',
    '  <select id="edit-unit-dimensions-unit"><option value="">—</option><option value="in">in</option><option value="cm">cm</option><option value="ft">ft</option><option value="m">m</option></select>',
    '  <p id="edit-unit-error" class="hidden"></p>',
    '  <button id="edit-unit-submit" type="button">Save</button>',
    '  <button id="edit-unit-cancel" type="button">Cancel</button>',
    '</dialog>',

    // Delete Location Dialog
    '<dialog id="delete-location-dialog">',
    '  <input type="hidden" id="delete-location-id">',
    '  <strong id="delete-location-name"></strong>',
    '  <button id="delete-location-submit" type="button">Delete</button>',
    '  <button id="delete-location-cancel" type="button">Cancel</button>',
    '</dialog>',

    // Delete Unit Dialog
    '<dialog id="delete-unit-dialog">',
    '  <input type="hidden" id="delete-unit-user-id">',
    '  <input type="hidden" id="delete-unit-access-token">',
    '  <strong id="delete-unit-name"></strong>',
    '  <p id="delete-unit-warning"></p>',
    '  <button id="delete-unit-submit" type="button">Delete</button>',
    '  <button id="delete-unit-cancel" type="button">Cancel</button>',
    '</dialog>',
  ].join('\n');
}

/**
 * Create a mock apiFetch that resolves with given data and status.
 */
function mockApiFetch(data, ok) {
  if (ok === undefined) ok = true;
  global.apiFetch = jest.fn(function () {
    return Promise.resolve({
      ok: ok,
      json: function () {
        return Promise.resolve(data);
      },
    });
  });
}

/**
 * Flush all pending promises (microtask queue).
 */
function flushPromises() {
  return new Promise(function (resolve) {
    setTimeout(resolve, 0);
  });
}

// --- Tests ---

describe('Browse CRUD', function () {
  beforeEach(function () {
    setupDom();
    // Stub showModal / close on all <dialog> elements (jsdom does not support HTMLDialogElement)
    document.querySelectorAll('dialog').forEach(function (d) {
      d.showModal = jest.fn(function () { d.setAttribute('open', ''); });
      d.close = jest.fn(function () { d.removeAttribute('open'); });
    });
    // Default apiFetch mock
    mockApiFetch({});
  });

  afterEach(function () {
    delete global.apiFetch;
  });

  // --- Create Location ---

  test('create location dialog opens with empty fields', function () {
    var api = initBrowseCrud(CONFIG);
    api.openCreateLocationDialog();

    var dialog = document.getElementById('create-location-dialog');
    expect(dialog.showModal).toHaveBeenCalled();
    expect(document.getElementById('create-location-name').value).toBe('');
    expect(document.getElementById('create-location-address').value).toBe('');
    expect(document.getElementById('create-location-error').classList.contains('hidden')).toBe(true);
  });

  test('create location submit posts name and address', async function () {
    mockApiFetch({}, true);
    var api = initBrowseCrud(CONFIG);
    api.openCreateLocationDialog();

    document.getElementById('create-location-name').value = 'Warehouse';
    document.getElementById('create-location-address').value = '456 Oak Ave';

    document.getElementById('create-location-submit').click();
    await flushPromises();

    expect(global.apiFetch).toHaveBeenCalledWith('/api/locations/create/', expect.objectContaining({
      method: 'POST',
    }));

    // Verify the body sent
    var callArgs = global.apiFetch.mock.calls[0];
    var body = JSON.parse(callArgs[1].body);
    expect(body.name).toBe('Warehouse');
    expect(body.address).toBe('456 Oak Ave');
  });

  test('create location shows error when name is empty', function () {
    var api = initBrowseCrud(CONFIG);
    api.openCreateLocationDialog();

    document.getElementById('create-location-name').value = '   ';
    document.getElementById('create-location-submit').click();

    var errorEl = document.getElementById('create-location-error');
    expect(errorEl.classList.contains('hidden')).toBe(false);
    expect(errorEl.textContent).toBe('Name is required.');
  });

  // --- Create Unit ---

  test('create unit dialog fetches container options and opens', async function () {
    mockApiFetch({
      locations: [{ id: 1, name: 'Warehouse' }],
      units: [{ id: 2, name: 'Shelf A' }],
    });

    var api = initBrowseCrud(CONFIG);
    api.openCreateUnitDialog(null);
    await flushPromises();

    expect(global.apiFetch).toHaveBeenCalledWith('/api/container-options/');
    var dialog = document.getElementById('create-unit-dialog');
    expect(dialog.showModal).toHaveBeenCalled();

    // Verify container select was populated with optgroups
    var select = document.getElementById('create-unit-container');
    var optgroups = select.querySelectorAll('optgroup');
    expect(optgroups.length).toBe(2);
    expect(optgroups[0].label).toBe('Locations');
    expect(optgroups[1].label).toBe('Units');
  });

  test('create unit dialog pre-selects location when provided', async function () {
    mockApiFetch({
      locations: [{ id: 5, name: 'Office' }],
      units: [],
    });

    var api = initBrowseCrud(CONFIG);
    api.openCreateUnitDialog(5);
    await flushPromises();

    var select = document.getElementById('create-unit-container');
    expect(select.value).toBe('location:5');
  });

  // --- Edit Location ---

  test('edit location dialog populates form fields', function () {
    var api = initBrowseCrud(CONFIG);
    api.openEditLocationDialog(10, 'My House', '123 Main St');

    expect(document.getElementById('edit-location-id').value).toBe('10');
    expect(document.getElementById('edit-location-name').value).toBe('My House');
    expect(document.getElementById('edit-location-address').value).toBe('123 Main St');
    var dialog = document.getElementById('edit-location-dialog');
    expect(dialog.showModal).toHaveBeenCalled();
  });

  // --- Edit Unit ---

  test('edit unit dialog fetches detail and populates form', async function () {
    // First call returns unit detail, second populates container options
    var callCount = 0;
    global.apiFetch = jest.fn(function () {
      callCount++;
      if (callCount === 1) {
        // Unit detail
        return Promise.resolve({
          json: function () {
            return Promise.resolve({
              id: 7,
              name: 'Garage Shelf',
              description: 'Top shelf',
              location_id: 3,
              parent_unit_id: null,
              length: 24,
              width: 12,
              height: 8,
              dimensions_unit: 'in',
            });
          },
        });
      }
      // Container options
      return Promise.resolve({
        json: function () {
          return Promise.resolve({
            locations: [{ id: 3, name: 'Garage' }],
            units: [],
          });
        },
      });
    });

    var api = initBrowseCrud(CONFIG);
    api.openEditUnitDialog(1, 'tok123');
    await flushPromises();

    // Verify detail was fetched with correct URL
    expect(global.apiFetch.mock.calls[0][0]).toBe('/api/units/1/tok123/detail/');

    // Verify form fields populated
    expect(document.getElementById('edit-unit-user-id').value).toBe('1');
    expect(document.getElementById('edit-unit-access-token').value).toBe('tok123');
    expect(document.getElementById('edit-unit-name').value).toBe('Garage Shelf');
    expect(document.getElementById('edit-unit-description').value).toBe('Top shelf');
    expect(document.getElementById('edit-unit-length').value).toBe('24');
    expect(document.getElementById('edit-unit-width').value).toBe('12');
    expect(document.getElementById('edit-unit-height').value).toBe('8');
    expect(document.getElementById('edit-unit-dimensions-unit').value).toBe('in');
  });

  // --- Delete Location ---

  test('delete location dialog shows name and sets hidden id', function () {
    var api = initBrowseCrud(CONFIG);
    api.openDeleteLocationDialog(10, 'My House');

    expect(document.getElementById('delete-location-id').value).toBe('10');
    expect(document.getElementById('delete-location-name').textContent).toBe('My House');
    var dialog = document.getElementById('delete-location-dialog');
    expect(dialog.showModal).toHaveBeenCalled();
  });

  // --- Delete Unit ---

  test('delete unit dialog shows name and fetches warning', async function () {
    // First call is unit detail, used to build warning
    global.apiFetch = jest.fn(function () {
      return Promise.resolve({
        json: function () {
          return Promise.resolve({ id: 7, name: 'Storage Bin' });
        },
      });
    });

    // Attach a mock browse API so the warning path works
    var browseApp = document.getElementById('browse-app');
    browseApp._browseApi = {
      refreshCurrentScreen: jest.fn(),
      getCurrentContext: function () { return { screen: 'locations' }; },
    };

    var api = initBrowseCrud(CONFIG);
    api.openDeleteUnitDialog(1, 'abc123', 'Storage Bin');

    expect(document.getElementById('delete-unit-user-id').value).toBe('1');
    expect(document.getElementById('delete-unit-access-token').value).toBe('abc123');
    expect(document.getElementById('delete-unit-name').textContent).toBe('Storage Bin');

    await flushPromises();

    // Warning should be updated from "Loading details..."
    var warning = document.getElementById('delete-unit-warning').textContent;
    expect(warning).not.toBe('Loading details...');
    expect(warning).toContain('permanently deleted');
  });

  // --- Entity Menu ---

  test('entity menu toggles on click and closes on outside click', function () {
    initBrowseCrud(CONFIG);

    var menuBtn = document.querySelector('.entity-menu-btn[data-entity-type="location"]');
    menuBtn.click();

    // Menu should be created
    var menu = document.querySelector('.entity-menu');
    expect(menu).not.toBeNull();
    expect(menu.innerHTML).toContain('Edit');
    expect(menu.innerHTML).toContain('Delete');

    // Click outside should close menu
    document.body.click();
    var menuAfter = document.querySelector('.entity-menu');
    expect(menuAfter).toBeNull();
  });

  // --- Dialog close ---

  test('cancel button closes dialog with animation', function () {
    jest.useFakeTimers();
    var api = initBrowseCrud(CONFIG);
    api.openCreateLocationDialog();

    var dialog = document.getElementById('create-location-dialog');
    expect(dialog.hasAttribute('open')).toBe(true);

    document.getElementById('create-location-cancel').click();

    // Closing class should be applied
    expect(dialog.classList.contains('dialog--closing')).toBe(true);

    // After animation duration, dialog.close() is called
    jest.advanceTimersByTime(150);
    expect(dialog.close).toHaveBeenCalled();
    expect(dialog.classList.contains('dialog--closing')).toBe(false);
    jest.useRealTimers();
  });

  // --- parseContainerValue ---

  test('parseContainerValue parses location and unit values', function () {
    var api = initBrowseCrud(CONFIG);

    var empty = api.parseContainerValue('');
    expect(empty.location_id).toBeNull();
    expect(empty.parent_unit_id).toBeNull();

    var loc = api.parseContainerValue('location:5');
    expect(loc.location_id).toBe(5);
    expect(loc.parent_unit_id).toBeNull();

    var unit = api.parseContainerValue('unit:3');
    expect(unit.location_id).toBeNull();
    expect(unit.parent_unit_id).toBe(3);
  });

  // --- Submit functions ---

  test('submitCreateLocation posts name and address', async function () {
    var browseApp = document.getElementById('browse-app');
    browseApp._browseApi = { refreshCurrentScreen: jest.fn(), getCurrentContext: function () { return { screen: 'locations' }; } };
    mockApiFetch({}, true);

    var api = initBrowseCrud(CONFIG);
    api.openCreateLocationDialog();

    document.getElementById('create-location-name').value = 'New Loc';
    document.getElementById('create-location-address').value = '789 Elm St';
    document.getElementById('create-location-submit').click();
    await flushPromises();

    var callArgs = global.apiFetch.mock.calls[0];
    var body = JSON.parse(callArgs[1].body);
    expect(body.name).toBe('New Loc');
    expect(body.address).toBe('789 Elm St');
  });

  test('submitCreateLocation shows error on API failure', async function () {
    mockApiFetch({ error: 'Name already taken' }, false);

    var api = initBrowseCrud(CONFIG);
    api.openCreateLocationDialog();

    document.getElementById('create-location-name').value = 'Dup';
    document.getElementById('create-location-submit').click();
    await flushPromises();

    var errorEl = document.getElementById('create-location-error');
    expect(errorEl.classList.contains('hidden')).toBe(false);
    expect(errorEl.textContent).toBe('Name already taken');
  });

  test('submitCreateUnit posts name and container', async function () {
    // First call: container options; second call: create unit
    var callCount = 0;
    global.apiFetch = jest.fn(function () {
      callCount++;
      if (callCount === 1) {
        return Promise.resolve({
          json: function () { return Promise.resolve({ locations: [{ id: 1, name: 'Loc' }], units: [] }); },
        });
      }
      return Promise.resolve({ ok: true, json: function () { return Promise.resolve({}); } });
    });

    var browseApp = document.getElementById('browse-app');
    browseApp._browseApi = { refreshCurrentScreen: jest.fn(), getCurrentContext: function () { return { screen: 'locations' }; } };

    var api = initBrowseCrud(CONFIG);
    api.openCreateUnitDialog(null);
    await flushPromises();

    document.getElementById('create-unit-name').value = 'New Unit';
    document.getElementById('create-unit-container').value = 'location:1';
    document.getElementById('create-unit-submit').click();
    await flushPromises();

    var createCall = global.apiFetch.mock.calls[1];
    expect(createCall[0]).toBe('/api/units/create/');
    var body = JSON.parse(createCall[1].body);
    expect(body.name).toBe('New Unit');
    expect(body.location_id).toBe(1);
  });

  test('submitEditLocation posts updated name', async function () {
    mockApiFetch({}, true);
    var browseApp = document.getElementById('browse-app');
    browseApp._browseApi = { refreshCurrentScreen: jest.fn(), getCurrentContext: function () { return { screen: 'locations' }; } };

    var api = initBrowseCrud(CONFIG);
    api.openEditLocationDialog(10, 'My House', '123 Main St');

    document.getElementById('edit-location-name').value = 'Updated House';
    document.getElementById('edit-location-address').value = '456 Oak Ave';
    document.getElementById('edit-location-submit').click();
    await flushPromises();

    var callArgs = global.apiFetch.mock.calls[0];
    expect(callArgs[0]).toBe('/api/locations/10/update/');
    var body = JSON.parse(callArgs[1].body);
    expect(body.name).toBe('Updated House');
    expect(body.address).toBe('456 Oak Ave');
  });

  test('submitDeleteLocation posts to correct URL', async function () {
    mockApiFetch({}, true);
    var browseApp = document.getElementById('browse-app');
    browseApp._browseApi = { refreshCurrentScreen: jest.fn(), getCurrentContext: function () { return { screen: 'locations' }; } };

    var api = initBrowseCrud(CONFIG);
    api.openDeleteLocationDialog(10, 'My House');

    document.getElementById('delete-location-submit').click();
    await flushPromises();

    expect(global.apiFetch).toHaveBeenCalledWith('/api/locations/10/delete/', expect.objectContaining({ method: 'POST' }));
  });

  test('submitDeleteUnit posts with correct URL', async function () {
    // First call: unit detail for warning; second call: delete
    var callCount = 0;
    global.apiFetch = jest.fn(function () {
      callCount++;
      if (callCount <= 1) {
        return Promise.resolve({ json: function () { return Promise.resolve({ id: 7 }); } });
      }
      return Promise.resolve({ ok: true, json: function () { return Promise.resolve({}); } });
    });

    var browseApp = document.getElementById('browse-app');
    browseApp._browseApi = { refreshCurrentScreen: jest.fn(), getCurrentContext: function () { return { screen: 'locations' }; } };

    var api = initBrowseCrud(CONFIG);
    api.openDeleteUnitDialog(1, 'abc123', 'Storage Bin');
    await flushPromises();

    document.getElementById('delete-unit-submit').click();
    await flushPromises();

    var deleteCall = global.apiFetch.mock.calls[1];
    expect(deleteCall[0]).toBe('/api/units/1/abc123/delete/');
    expect(deleteCall[1].method).toBe('POST');
  });
});
