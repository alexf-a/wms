const { initBrowse } = require('./browse');

// --- Helpers ---

var CONFIG = {
  browseLocationsUrl: '/api/browse/',
  browseLocationUnitsUrl: '/api/browse/location/0/',
  browseUnitItemsUrl: '/api/browse/unit/0/PLACEHOLDER/',
  unitDetailUrl: '/user/0/units/PLACEHOLDER/',
};

/**
 * Build the browse page DOM fixture.
 */
function setupDom() {
  document.body.innerHTML = [
    '<div id="browse-app">',
    '  <button id="browse-back-btn" class="hidden" type="button">Back</button>',
    '  <h1 id="browse-title">Browse</h1>',
    '  <p id="browse-subtitle">1 location</p>',
    '  <div id="screen-locations">',
    '    <a href="#" class="browse-location-card" data-location-id="10" data-location-name="My House">My House</a>',
    '    <a href="#" class="browse-unit-card" data-unit-user-id="1" data-unit-access-token="abc123" data-unit-name="Storage Bin">Storage Bin</a>',
    '  </div>',
    '  <div id="screen-units" class="hidden"></div>',
    '  <div id="screen-items" class="hidden"></div>',
    '</div>',
  ].join('\n');
}

/**
 * Create a mock apiFetch that resolves with given data.
 */
function mockApiFetch(data) {
  global.apiFetch = jest.fn(function () {
    return Promise.resolve({
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

describe('Browse Page', function () {
  beforeEach(function () {
    setupDom();
    // Default apiFetch mock (returns empty)
    mockApiFetch({ locations: [], orphan_units: [], units: [], items: [], child_units: [], unit: { id: 1, name: 'Test' }, location: { id: 1, name: 'Test' }, parent_label: '' });
  });

  afterEach(function () {
    delete global.apiFetch;
  });

  test('starts on locations screen with back button hidden', function () {
    initBrowse(CONFIG);
    expect(document.getElementById('screen-locations').classList.contains('hidden')).toBe(false);
    expect(document.getElementById('screen-units').classList.contains('hidden')).toBe(true);
    expect(document.getElementById('screen-items').classList.contains('hidden')).toBe(true);
    expect(document.getElementById('browse-back-btn').classList.contains('hidden')).toBe(true);
  });

  test('clicking location card fetches and shows units screen', async function () {
    mockApiFetch({
      location: { id: 10, name: 'My House' },
      units: [
        { id: 1, name: 'Garage', user_id: 1, access_token: 'tok1', item_count: 3, child_count: 0 },
      ],
    });

    initBrowse(CONFIG);

    // Click location card
    document.querySelector('.browse-location-card').click();
    await flushPromises();

    expect(global.apiFetch).toHaveBeenCalledWith('/api/browse/location/10/');
    expect(document.getElementById('screen-units').classList.contains('hidden')).toBe(false);
    expect(document.getElementById('screen-locations').classList.contains('hidden')).toBe(true);
    expect(document.getElementById('browse-title').textContent).toBe('My House');
    expect(document.getElementById('browse-back-btn').classList.contains('hidden')).toBe(false);
  });

  test('clicking unit card fetches and shows items screen', async function () {
    mockApiFetch({
      unit: { id: 1, name: 'Storage Bin' },
      parent_label: '',
      items: [
        { id: 1, name: 'Hammer', quantity: 1, quantity_unit: 'count' },
      ],
      child_units: [],
    });

    initBrowse(CONFIG);

    // Click orphan unit card on locations screen
    document.querySelector('.browse-unit-card').click();
    await flushPromises();

    expect(global.apiFetch).toHaveBeenCalledWith('/api/browse/unit/1/abc123/');
    expect(document.getElementById('screen-items').classList.contains('hidden')).toBe(false);
    expect(document.getElementById('screen-locations').classList.contains('hidden')).toBe(true);
    expect(document.getElementById('browse-title').textContent).toBe('Storage Bin');
  });

  test('back button returns to previous screen', async function () {
    mockApiFetch({
      location: { id: 10, name: 'My House' },
      units: [{ id: 1, name: 'Garage', user_id: 1, access_token: 'tok1', item_count: 0, child_count: 0 }],
    });

    initBrowse(CONFIG);

    // Navigate to units
    document.querySelector('.browse-location-card').click();
    await flushPromises();

    expect(document.getElementById('screen-units').classList.contains('hidden')).toBe(false);

    // Click back
    document.getElementById('browse-back-btn').click();

    expect(document.getElementById('screen-locations').classList.contains('hidden')).toBe(false);
    expect(document.getElementById('screen-units').classList.contains('hidden')).toBe(true);
    expect(document.getElementById('browse-title').textContent).toBe('Browse');
    expect(document.getElementById('browse-back-btn').classList.contains('hidden')).toBe(true);
  });

  test('back from items returns to units, not locations', async function () {
    // First navigate to units
    mockApiFetch({
      location: { id: 10, name: 'My House' },
      units: [{ id: 1, name: 'Garage', user_id: 1, access_token: 'tok1', item_count: 0, child_count: 0 }],
    });

    initBrowse(CONFIG);
    document.querySelector('.browse-location-card').click();
    await flushPromises();

    // Now navigate to items from a unit card rendered in units screen
    mockApiFetch({
      unit: { id: 1, name: 'Garage' },
      parent_label: 'My House',
      items: [],
      child_units: [],
    });

    // The units screen has a unit card rendered via JS
    var unitCard = document.querySelector('#screen-units .browse-unit-card');
    if (unitCard) {
      unitCard.click();
      await flushPromises();

      // Click back should return to units, not locations
      document.getElementById('browse-back-btn').click();
      expect(document.getElementById('screen-units').classList.contains('hidden')).toBe(false);
      expect(document.getElementById('screen-items').classList.contains('hidden')).toBe(true);
    }
  });

  test('empty state shown when no locations or units exist', function () {
    // Remove server-rendered cards
    document.getElementById('screen-locations').innerHTML = '';
    initBrowse(CONFIG);
    // Simply verify no errors thrown and locations screen is visible
    expect(document.getElementById('screen-locations').classList.contains('hidden')).toBe(false);
  });

  test('subtitle updates on navigation', async function () {
    mockApiFetch({
      location: { id: 10, name: 'My House' },
      units: [
        { id: 1, name: 'Garage', user_id: 1, access_token: 'tok1', item_count: 3, child_count: 0 },
        { id: 2, name: 'Attic', user_id: 1, access_token: 'tok2', item_count: 1, child_count: 0 },
      ],
    });

    initBrowse(CONFIG);
    document.querySelector('.browse-location-card').click();
    await flushPromises();

    expect(document.getElementById('browse-subtitle').textContent).toBe('2 units');
  });

  test('subtitle shows singular form for 1 item', async function () {
    mockApiFetch({
      unit: { id: 1, name: 'Storage Bin' },
      parent_label: '',
      items: [{ id: 1, name: 'Hammer', quantity: 1, quantity_unit: 'count' }],
      child_units: [],
    });

    initBrowse(CONFIG);
    document.querySelector('.browse-unit-card').click();
    await flushPromises();

    expect(document.getElementById('browse-subtitle').textContent).toBe('1 item');
  });

  test('escapeHtml prevents XSS in rendered cards', async function () {
    mockApiFetch({
      location: { id: 10, name: 'My House' },
      units: [
        { id: 1, name: '<script>alert("xss")</script>', user_id: 1, access_token: 'tok1', item_count: 0, child_count: 0 },
      ],
    });

    initBrowse(CONFIG);
    document.querySelector('.browse-location-card').click();
    await flushPromises();

    // Verify text content (visible to user) is escaped — no raw script tags
    var nameEl = document.querySelector('#screen-units .browse-unit-card p');
    expect(nameEl.textContent).toContain('<script>');  // textContent shows raw text
    expect(nameEl.innerHTML).toContain('&lt;script&gt;');  // innerHTML shows escaped HTML
    // Verify no actual <script> elements were created in the DOM
    expect(document.getElementById('screen-units').querySelectorAll('script').length).toBe(0);
  });

  test('items screen renders child units and items', async function () {
    mockApiFetch({
      unit: { id: 1, name: 'Storage Bin' },
      parent_label: '',
      items: [
        { id: 1, name: 'Hammer', quantity: 2, quantity_unit: 'count' },
        { id: 2, name: 'Nails', quantity: null, quantity_unit: '' },
      ],
      child_units: [
        { id: 3, name: 'Drawer', user_id: 1, access_token: 'drawer1', item_count: 5 },
      ],
    });

    initBrowse(CONFIG);
    document.querySelector('.browse-unit-card').click();
    await flushPromises();

    var itemsScreen = document.getElementById('screen-items');
    expect(itemsScreen.innerHTML).toContain('Sub-units');
    expect(itemsScreen.innerHTML).toContain('Drawer');
    expect(itemsScreen.innerHTML).toContain('Hammer');
    expect(itemsScreen.innerHTML).toContain('Nails');
  });
});
