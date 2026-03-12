const { initOnboarding } = require('./onboarding');

// --- Helpers ---

var CONFIG = {
  createLocationUrl: '/api/locations/create/',
  createUnitUrl: '/api/units/create/',
  completeOnboardingUrl: '/api/onboarding/complete/',
};

/**
 * Build the onboarding wizard DOM fixture.
 */
function setupDom() {
  document.body.innerHTML = `
    <div id="onboarding-wizard">
      <div id="progress-bar" class="hidden">
        <div id="progress-step-1" class="bg-muted"></div>
        <div id="progress-step-2" class="bg-muted"></div>
        <p id="progress-label"></p>
      </div>

      <div class="onboarding-step" data-step="0">
        <button id="btn-get-started">Get Started</button>
      </div>

      <div class="onboarding-step hidden" data-step="1">
        <input type="text" id="location-name" />
        <input type="text" id="location-address" />
        <div id="location-error" class="hidden"></div>
        <button id="btn-location-next">Next</button>
        <button id="btn-location-skip">Skip for Now</button>
      </div>

      <div class="onboarding-step hidden" data-step="2">
        <input type="text" id="unit-name" />
        <div id="unit-error" class="hidden"></div>
        <span id="unit-location-hint" class="hidden">
          Inside <strong id="unit-location-name"></strong>
        </span>
        <button id="btn-unit-next">Next</button>
        <button id="btn-unit-back">Back</button>
        <button id="btn-unit-skip">Skip</button>
      </div>

      <div class="onboarding-step hidden" data-step="3">
        <a href="/add">Add an Item</a>
        <a href="/">Go to Home</a>
      </div>
    </div>
  `;
}

/**
 * Check if a step is the visible one (not hidden).
 */
function isStepVisible(stepIndex) {
  var steps = document.querySelectorAll('.onboarding-step');
  return !steps[stepIndex].classList.contains('hidden');
}

/**
 * Create a mock apiFetch that resolves with the given status and body.
 */
function mockApiFetchResponse(status, body) {
  return jest.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status: status,
    json: function () { return Promise.resolve(body); }
  });
}

// --- Tests ---

describe('Onboarding Wizard', function () {
  beforeEach(function () {
    setupDom();
    // Mock global apiFetch (loaded from fetch_utils.js in production)
    global.apiFetch = mockApiFetchResponse(200, { status: 'ok' });
  });

  afterEach(function () {
    document.body.innerHTML = '';
    delete global.apiFetch;
  });

  test('starts on step 0 (welcome)', function () {
    initOnboarding(CONFIG);

    expect(isStepVisible(0)).toBe(true);
    expect(isStepVisible(1)).toBe(false);
    expect(isStepVisible(2)).toBe(false);
    expect(isStepVisible(3)).toBe(false);
    expect(document.getElementById('progress-bar').classList.contains('hidden')).toBe(true);
  });

  test('Get Started advances to step 1', function () {
    initOnboarding(CONFIG);
    document.getElementById('btn-get-started').click();

    expect(isStepVisible(0)).toBe(false);
    expect(isStepVisible(1)).toBe(true);
    expect(document.getElementById('progress-bar').classList.contains('hidden')).toBe(false);
    expect(document.getElementById('progress-label').textContent).toBe('Step 1 of 2');
  });

  test('Skip location advances to step 2', function () {
    initOnboarding(CONFIG);
    document.getElementById('btn-get-started').click();
    document.getElementById('btn-location-skip').click();

    expect(isStepVisible(1)).toBe(false);
    expect(isStepVisible(2)).toBe(true);
    expect(document.getElementById('progress-label').textContent).toBe('Step 2 of 2');
  });

  test('Back on step 2 returns to step 1', function () {
    initOnboarding(CONFIG);
    document.getElementById('btn-get-started').click();
    document.getElementById('btn-location-skip').click();

    expect(isStepVisible(2)).toBe(true);

    document.getElementById('btn-unit-back').click();

    expect(isStepVisible(1)).toBe(true);
    expect(isStepVisible(2)).toBe(false);
    expect(document.getElementById('progress-label').textContent).toBe('Step 1 of 2');
  });

  test('Location next with empty name skips to step 2', function () {
    initOnboarding(CONFIG);
    document.getElementById('btn-get-started').click();

    // Leave location-name empty
    document.getElementById('location-name').value = '';
    document.getElementById('btn-location-next').click();

    expect(isStepVisible(2)).toBe(true);
    // apiFetch should NOT have been called
    expect(global.apiFetch).not.toHaveBeenCalled();
  });

  test('Create location success advances to step 2 with hint', async function () {
    global.apiFetch = mockApiFetchResponse(201, { id: 42, name: 'My House' });
    initOnboarding(CONFIG);

    document.getElementById('btn-get-started').click();
    document.getElementById('location-name').value = 'My House';
    document.getElementById('location-address').value = '123 Main St';
    document.getElementById('btn-location-next').click();

    // Wait for async
    await new Promise(function (r) { setTimeout(r, 0); });

    expect(isStepVisible(2)).toBe(true);
    expect(document.getElementById('unit-location-hint').classList.contains('hidden')).toBe(false);
    expect(document.getElementById('unit-location-name').textContent).toBe('My House');

    // Verify API call
    expect(global.apiFetch).toHaveBeenCalledWith(
      '/api/locations/create/',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ name: 'My House', address: '123 Main St' })
      })
    );
  });

  test('Create location error shows error message', async function () {
    global.apiFetch = mockApiFetchResponse(409, { error: 'A location named "Dup" already exists.' });
    initOnboarding(CONFIG);

    document.getElementById('btn-get-started').click();
    document.getElementById('location-name').value = 'Dup';
    document.getElementById('btn-location-next').click();

    await new Promise(function (r) { setTimeout(r, 0); });

    // Should stay on step 1
    expect(isStepVisible(1)).toBe(true);
    var errorEl = document.getElementById('location-error');
    expect(errorEl.classList.contains('hidden')).toBe(false);
    expect(errorEl.textContent).toContain('already exists');
  });

  test('Create unit success calls complete and shows step 3', async function () {
    // First call: create unit (201), second call: complete onboarding (200)
    global.apiFetch = jest.fn()
      .mockResolvedValueOnce({
        ok: true, status: 201,
        json: function () { return Promise.resolve({ id: 1, name: 'Shelf', access_token: 'abc123' }); }
      })
      .mockResolvedValueOnce({
        ok: true, status: 200,
        json: function () { return Promise.resolve({ status: 'ok' }); }
      });

    initOnboarding(CONFIG);
    // Navigate to step 2
    document.getElementById('btn-get-started').click();
    document.getElementById('btn-location-skip').click();

    document.getElementById('unit-name').value = 'Shelf';
    document.getElementById('btn-unit-next').click();

    await new Promise(function (r) { setTimeout(r, 0); });

    expect(isStepVisible(3)).toBe(true);
    expect(global.apiFetch).toHaveBeenCalledTimes(2);
    expect(global.apiFetch).toHaveBeenCalledWith(
      '/api/units/create/',
      expect.objectContaining({ method: 'POST' })
    );
    expect(global.apiFetch).toHaveBeenCalledWith(
      '/api/onboarding/complete/',
      expect.objectContaining({ method: 'POST' })
    );
  });

  test('Skip unit calls complete and shows step 3', async function () {
    initOnboarding(CONFIG);
    document.getElementById('btn-get-started').click();
    document.getElementById('btn-location-skip').click();
    document.getElementById('btn-unit-skip').click();

    await new Promise(function (r) { setTimeout(r, 0); });

    expect(isStepVisible(3)).toBe(true);
    expect(global.apiFetch).toHaveBeenCalledWith(
      '/api/onboarding/complete/',
      expect.objectContaining({ method: 'POST' })
    );
  });

  test('Unit next with empty name calls finish (skip)', async function () {
    initOnboarding(CONFIG);
    document.getElementById('btn-get-started').click();
    document.getElementById('btn-location-skip').click();

    document.getElementById('unit-name').value = '';
    document.getElementById('btn-unit-next').click();

    await new Promise(function (r) { setTimeout(r, 0); });

    expect(isStepVisible(3)).toBe(true);
    // Only the complete call should have been made (no unit create)
    expect(global.apiFetch).toHaveBeenCalledTimes(1);
    expect(global.apiFetch).toHaveBeenCalledWith(
      '/api/onboarding/complete/',
      expect.objectContaining({ method: 'POST' })
    );
  });

  test('Create unit sends location_id if location was created', async function () {
    // Location create response
    global.apiFetch = jest.fn()
      .mockResolvedValueOnce({
        ok: true, status: 201,
        json: function () { return Promise.resolve({ id: 99, name: 'House' }); }
      })
      .mockResolvedValueOnce({
        ok: true, status: 201,
        json: function () { return Promise.resolve({ id: 1, name: 'Shelf', access_token: 'tok' }); }
      })
      .mockResolvedValueOnce({
        ok: true, status: 200,
        json: function () { return Promise.resolve({ status: 'ok' }); }
      });

    initOnboarding(CONFIG);
    document.getElementById('btn-get-started').click();

    // Create location
    document.getElementById('location-name').value = 'House';
    document.getElementById('btn-location-next').click();
    await new Promise(function (r) { setTimeout(r, 0); });

    // Create unit
    document.getElementById('unit-name').value = 'Shelf';
    document.getElementById('btn-unit-next').click();
    await new Promise(function (r) { setTimeout(r, 0); });

    // Verify unit creation included location_id
    var unitCall = global.apiFetch.mock.calls[1];
    var unitBody = JSON.parse(unitCall[1].body);
    expect(unitBody.location_id).toBe(99);
  });

  test('Create unit error shows error message', async function () {
    global.apiFetch = mockApiFetchResponse(409, { error: 'A unit named "Dup" already exists.' });
    initOnboarding(CONFIG);

    document.getElementById('btn-get-started').click();
    document.getElementById('btn-location-skip').click();
    document.getElementById('unit-name').value = 'Dup';
    document.getElementById('btn-unit-next').click();

    await new Promise(function (r) { setTimeout(r, 0); });

    expect(isStepVisible(2)).toBe(true);
    var errorEl = document.getElementById('unit-error');
    expect(errorEl.classList.contains('hidden')).toBe(false);
    expect(errorEl.textContent).toContain('already exists');
  });

  test('Progress bar shows on steps 1-2, hidden on 0 and 3', async function () {
    initOnboarding(CONFIG);
    var bar = document.getElementById('progress-bar');

    // Step 0
    expect(bar.classList.contains('hidden')).toBe(true);

    // Step 1
    document.getElementById('btn-get-started').click();
    expect(bar.classList.contains('hidden')).toBe(false);
    expect(document.getElementById('progress-step-1').classList.contains('bg-primary')).toBe(true);
    expect(document.getElementById('progress-step-2').classList.contains('bg-muted')).toBe(true);

    // Step 2
    document.getElementById('btn-location-skip').click();
    expect(bar.classList.contains('hidden')).toBe(false);
    expect(document.getElementById('progress-step-2').classList.contains('bg-primary')).toBe(true);

    // Step 3
    document.getElementById('btn-unit-skip').click();
    await new Promise(function (r) { setTimeout(r, 0); });
    expect(bar.classList.contains('hidden')).toBe(true);
  });
});
