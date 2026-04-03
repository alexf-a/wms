/**
 * Build the sharing dialog DOM fixture.
 */
function setupSharingDom() {
  document.body.innerHTML = [
    '<dialog id="sharing-dialog">',
    '  <h2>Share Access</h2>',
    '  <p id="sharing-subtitle"></p>',
    '  <p id="sharing-error" class="hidden"></p>',
    '  <p id="sharing-success" class="hidden"></p>',
    '  <input type="email" id="sharing-email">',
    '  <select id="sharing-permission">',
    '    <option value="read">View</option>',
    '    <option value="write">Edit own</option>',
    '    <option value="write_all">Edit all</option>',
    '  </select>',
    '  <button id="sharing-invite-btn">Invite</button>',
    '  <div id="sharing-list">',
    '    <p id="sharing-empty" class="hidden">Not shared with anyone yet</p>',
    '  </div>',
    '  <button id="sharing-close-btn">Done</button>',
    '</dialog>',
  ].join('\n');

  // Stub dialog methods (jsdom doesn't support HTMLDialogElement)
  var dialog = document.getElementById('sharing-dialog');
  dialog.showModal = jest.fn();
  dialog.close = jest.fn();
}

function flushPromises() {
  return new Promise(function (resolve) {
    setTimeout(resolve, 0);
  });
}

describe('sharing dialog', function () {
  beforeEach(function () {
    jest.resetModules();
    setupSharingDom();
    global.apiFetch = jest.fn();
  });

  afterEach(function () {
    delete global.apiFetch;
    delete window.openUnitSharing;
    delete window.openLocationSharing;
  });

  function loadModule() {
    require('./sharing');
  }

  function mockApiFetchResponse(data, ok) {
    if (ok === undefined) ok = true;
    global.apiFetch.mockReturnValue(
      Promise.resolve({
        ok: ok,
        json: function () { return Promise.resolve(data); },
      })
    );
  }

  // --- open functions ---

  test('openUnitSharing opens dialog and sets subtitle', function () {
    loadModule();
    mockApiFetchResponse({ shares: [] });

    window.openUnitSharing(5, 'abc123', 'My Bin');

    expect(document.getElementById('sharing-subtitle').textContent).toBe('My Bin');
    var dialog = document.getElementById('sharing-dialog');
    expect(dialog.showModal).toHaveBeenCalled();
  });

  test('openUnitSharing calls loadShares with correct URL', async function () {
    loadModule();
    mockApiFetchResponse({ shares: [] });

    window.openUnitSharing(5, 'abc123', 'My Bin');
    await flushPromises();

    expect(global.apiFetch).toHaveBeenCalledWith('/api/units/5/abc123/sharing/');
  });

  test('openLocationSharing sets correct base URL', async function () {
    loadModule();
    mockApiFetchResponse({ shares: [] });

    window.openLocationSharing(42, 'My House');
    await flushPromises();

    expect(document.getElementById('sharing-subtitle').textContent).toBe('My House');
    expect(global.apiFetch).toHaveBeenCalledWith('/api/locations/42/sharing/');
  });

  // --- invite ---

  test('invite sends POST with email and permission', async function () {
    loadModule();
    // First call: loadShares; second call: invite
    global.apiFetch
      .mockReturnValueOnce(Promise.resolve({
        ok: true,
        json: function () { return Promise.resolve({ shares: [] }); },
      }))
      .mockReturnValueOnce(Promise.resolve({
        ok: true,
        json: function () { return Promise.resolve({ id: 1, email: 'bob@x.com', permission: 'read' }); },
      }));

    window.openUnitSharing(5, 'tok', 'Bin');
    await flushPromises();

    document.getElementById('sharing-email').value = 'bob@x.com';
    document.getElementById('sharing-permission').value = 'read';
    document.getElementById('sharing-invite-btn').click();
    await flushPromises();

    expect(global.apiFetch).toHaveBeenCalledWith(
      '/api/units/5/tok/sharing/add/',
      expect.objectContaining({ method: 'POST' })
    );
  });

  test('invite with empty email shows error', async function () {
    loadModule();
    mockApiFetchResponse({ shares: [] });

    window.openUnitSharing(5, 'tok', 'Bin');
    await flushPromises();

    document.getElementById('sharing-email').value = '';
    document.getElementById('sharing-invite-btn').click();

    var errorEl = document.getElementById('sharing-error');
    expect(errorEl.classList.contains('hidden')).toBe(false);
    expect(errorEl.textContent).toBe('Email is required');
    // Should not have made an invite API call (only the loadShares call)
    expect(global.apiFetch).toHaveBeenCalledTimes(1);
  });

  test('successful invite appends share row and shows success', async function () {
    loadModule();
    global.apiFetch
      .mockReturnValueOnce(Promise.resolve({
        ok: true,
        json: function () { return Promise.resolve({ shares: [] }); },
      }))
      .mockReturnValueOnce(Promise.resolve({
        ok: true,
        json: function () { return Promise.resolve({ id: 7, email: 'alice@x.com', permission: 'write' }); },
      }));

    window.openUnitSharing(5, 'tok', 'Bin');
    await flushPromises();

    document.getElementById('sharing-email').value = 'alice@x.com';
    document.getElementById('sharing-invite-btn').click();
    await flushPromises();

    var rows = document.querySelectorAll('[data-share-id]');
    expect(rows.length).toBe(1);
    expect(rows[0].getAttribute('data-share-id')).toBe('7');
    expect(document.getElementById('sharing-success').classList.contains('hidden')).toBe(false);
  });

  test('invite API error shows error message', async function () {
    loadModule();
    global.apiFetch
      .mockReturnValueOnce(Promise.resolve({
        ok: true,
        json: function () { return Promise.resolve({ shares: [] }); },
      }))
      .mockReturnValueOnce(Promise.resolve({
        ok: false,
        json: function () { return Promise.resolve({ error: 'User not found' }); },
      }));

    window.openUnitSharing(5, 'tok', 'Bin');
    await flushPromises();

    document.getElementById('sharing-email').value = 'nobody@x.com';
    document.getElementById('sharing-invite-btn').click();
    await flushPromises();

    var errorEl = document.getElementById('sharing-error');
    expect(errorEl.classList.contains('hidden')).toBe(false);
    expect(errorEl.textContent).toBe('User not found');
  });

  // --- renderShares ---

  test('loadShares renders share rows from API', async function () {
    loadModule();
    mockApiFetchResponse({
      shares: [
        { id: 1, email: 'a@x.com', permission: 'read' },
        { id: 2, email: 'b@x.com', permission: 'write' },
      ],
    });

    window.openUnitSharing(5, 'tok', 'Bin');
    await flushPromises();

    var rows = document.querySelectorAll('[data-share-id]');
    expect(rows.length).toBe(2);
    expect(document.getElementById('sharing-empty').classList.contains('hidden')).toBe(true);
  });

  test('empty shares shows empty state message', async function () {
    loadModule();
    mockApiFetchResponse({ shares: [] });

    window.openUnitSharing(5, 'tok', 'Bin');
    await flushPromises();

    expect(document.getElementById('sharing-empty').classList.contains('hidden')).toBe(false);
  });

  // --- removeAccess ---

  test('remove access calls API and removes row', async function () {
    loadModule();
    global.apiFetch
      .mockReturnValueOnce(Promise.resolve({
        ok: true,
        json: function () {
          return Promise.resolve({
            shares: [{ id: 3, email: 'c@x.com', permission: 'read' }],
          });
        },
      }))
      .mockReturnValueOnce(Promise.resolve({ ok: true }));

    window.openUnitSharing(5, 'tok', 'Bin');
    await flushPromises();

    // Click the remove button on the share row
    var removeBtn = document.querySelector('[data-share-id="3"] button');
    expect(removeBtn).not.toBeNull();
    removeBtn.click();
    await flushPromises();

    expect(global.apiFetch).toHaveBeenCalledWith(
      '/api/units/5/tok/sharing/3/remove/',
      expect.objectContaining({ method: 'POST' })
    );
    expect(document.querySelectorAll('[data-share-id]').length).toBe(0);
    expect(document.getElementById('sharing-empty').classList.contains('hidden')).toBe(false);
  });

  // --- updatePermission ---

  test('changing permission select calls update API', async function () {
    loadModule();
    global.apiFetch
      .mockReturnValueOnce(Promise.resolve({
        ok: true,
        json: function () {
          return Promise.resolve({
            shares: [{ id: 4, email: 'd@x.com', permission: 'read' }],
          });
        },
      }))
      .mockReturnValueOnce(Promise.resolve({ ok: true }));

    window.openUnitSharing(5, 'tok', 'Bin');
    await flushPromises();

    var select = document.querySelector('[data-share-id="4"] select');
    expect(select).not.toBeNull();
    select.value = 'write_all';
    select.dispatchEvent(new Event('change'));
    await flushPromises();

    expect(global.apiFetch).toHaveBeenCalledWith(
      '/api/units/5/tok/sharing/4/update/',
      expect.objectContaining({ method: 'POST' })
    );
  });

  // --- close ---

  test('close button closes dialog', function () {
    jest.useFakeTimers();
    loadModule();
    mockApiFetchResponse({ shares: [] });
    window.openUnitSharing(5, 'tok', 'Bin');

    document.getElementById('sharing-close-btn').click();
    jest.advanceTimersByTime(150);

    expect(document.getElementById('sharing-dialog').close).toHaveBeenCalled();
    jest.useRealTimers();
  });
});
