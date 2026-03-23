var fetchUtils;

beforeEach(function () {
  document.body.innerHTML = '';
  // Clear csrftoken cookie (setting empty value with expired date)
  document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT';
  global.fetch = jest.fn(function () {
    return Promise.resolve({ ok: true });
  });
  jest.resetModules();
  fetchUtils = require('./fetch_utils');
});

afterEach(function () {
  delete global.fetch;
});

describe('_getCSRFToken', function () {
  test('reads token from hidden input', function () {
    document.body.innerHTML = '<input name="csrfmiddlewaretoken" value="abc123">';
    expect(fetchUtils._getCSRFToken()).toBe('abc123');
  });

  test('falls back to csrftoken cookie', function () {
    document.cookie = 'csrftoken=cookie456';
    expect(fetchUtils._getCSRFToken()).toBe('cookie456');
  });

  test('returns empty string when neither exists', function () {
    expect(fetchUtils._getCSRFToken()).toBe('');
  });
});

describe('apiFetch', function () {
  test('injects X-CSRFToken header for POST', async function () {
    document.body.innerHTML = '<input name="csrfmiddlewaretoken" value="tok">';
    await fetchUtils.apiFetch('/api/test/', { method: 'POST' });

    expect(global.fetch).toHaveBeenCalledWith('/api/test/', expect.objectContaining({
      method: 'POST',
      headers: expect.objectContaining({ 'X-CSRFToken': 'tok' }),
    }));
  });

  test('does not inject CSRF header for GET', async function () {
    document.body.innerHTML = '<input name="csrfmiddlewaretoken" value="tok">';
    await fetchUtils.apiFetch('/api/test/');

    var callOpts = global.fetch.mock.calls[0][1];
    expect(callOpts.headers).toBeUndefined();
  });

  test('sets credentials to same-origin', async function () {
    await fetchUtils.apiFetch('/api/test/');
    var callOpts = global.fetch.mock.calls[0][1];
    expect(callOpts.credentials).toBe('same-origin');
  });

  test('preserves existing credentials option', async function () {
    await fetchUtils.apiFetch('/api/test/', { credentials: 'include' });
    var callOpts = global.fetch.mock.calls[0][1];
    expect(callOpts.credentials).toBe('include');
  });

  test('merges custom headers with CSRF', async function () {
    document.body.innerHTML = '<input name="csrfmiddlewaretoken" value="tok">';
    await fetchUtils.apiFetch('/api/test/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });

    var callOpts = global.fetch.mock.calls[0][1];
    expect(callOpts.headers['X-CSRFToken']).toBe('tok');
    expect(callOpts.headers['Content-Type']).toBe('application/json');
  });

  test('custom header overrides CSRF if explicitly set', async function () {
    document.body.innerHTML = '<input name="csrfmiddlewaretoken" value="tok">';
    await fetchUtils.apiFetch('/api/test/', {
      method: 'POST',
      headers: { 'X-CSRFToken': 'custom' },
    });

    var callOpts = global.fetch.mock.calls[0][1];
    expect(callOpts.headers['X-CSRFToken']).toBe('custom');
  });
});
