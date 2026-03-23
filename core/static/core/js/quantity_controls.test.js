/**
 * Set up globals required by quantity_controls.js.
 */
function setupQuantityGlobals() {
  // quantity_logic.js expects these globals
  global.WMS_QUANTITY_NON_COUNT_STEP = 0.1;
  global.WMS_QUANTITY_DECIMAL_PLACES = 1;
  // Load quantity_logic first to set up WMSQuantityLogic
  require('./quantity_logic');
}

function setupQuantityDom() {
  document.body.innerHTML = [
    '<form><input name="csrfmiddlewaretoken" value="csrf-tok"></form>',
    '<div class="m3-item-card-wrapper" data-item-id="10" data-quantity="5" data-quantity-unit="count">',
    '  <div class="m3-quantity-controls">',
    '    <button class="qty-decrement" type="button">-</button>',
    '    <span class="qty-value" aria-valuenow="5">5</span>',
    '    <button class="qty-increment" type="button">+</button>',
    '  </div>',
    '</div>',
    '<div class="m3-item-card-wrapper" data-item-id="20" data-quantity="1.5" data-quantity-unit="kg">',
    '  <div class="m3-quantity-controls">',
    '    <button class="qty-decrement" type="button">-</button>',
    '    <span class="qty-value" aria-valuenow="1.5">1.5 kg</span>',
    '    <button class="qty-increment" type="button">+</button>',
    '  </div>',
    '</div>',
  ].join('\n');
}

function flushPromises() {
  return new Promise(function (resolve) {
    setTimeout(resolve, 0);
  });
}

describe('quantity_controls', function () {
  var mod;

  beforeEach(function () {
    jest.resetModules();
    setupQuantityGlobals();
    setupQuantityDom();
    global.WMS_UNIT_2_NAME = { count: 'count', kg: 'kg' };
    global.fetch = jest.fn(function () {
      return Promise.resolve({
        ok: true,
        json: function () { return Promise.resolve({ quantity: 6, formatted: '6' }); },
      });
    });
    mod = require('./quantity_controls');
  });

  afterEach(function () {
    delete global.fetch;
    delete global.WMS_UNIT_2_NAME;
    delete global.WMS_QUANTITY_NON_COUNT_STEP;
    delete global.WMS_QUANTITY_DECIMAL_PLACES;
    delete global.WMSQuantityLogic;
  });

  test('getPendingState returns new state and reuses for same itemId', function () {
    var s1 = mod.getPendingState(10);
    var s2 = mod.getPendingState(10);
    var s3 = mod.getPendingState(20);
    expect(s1).toBe(s2);
    expect(s1).not.toBe(s3);
  });

  test('updateUI updates text content and data attributes', function () {
    var wrapper = document.querySelector('[data-item-id="10"]');
    mod.updateUI(wrapper, 42, '42');

    expect(wrapper.getAttribute('data-quantity')).toBe('42');
    expect(wrapper.querySelector('.qty-value').textContent).toBe('42');
    expect(wrapper.querySelector('.qty-value').getAttribute('aria-valuenow')).toBe('42');
  });

  test('updateUI toggles qty-zero class at 0', function () {
    var wrapper = document.querySelector('[data-item-id="10"]');
    var controls = wrapper.querySelector('.m3-quantity-controls');

    mod.updateUI(wrapper, 0, '0');
    expect(controls.classList.contains('qty-zero')).toBe(true);

    mod.updateUI(wrapper, 3, '3');
    expect(controls.classList.contains('qty-zero')).toBe(false);
  });

  test('increment button fires API call', async function () {
    mod.initQuantityControls();
    var btn = document.querySelector('[data-item-id="10"] .qty-increment');
    btn.click();
    await flushPromises();

    expect(global.fetch).toHaveBeenCalledTimes(1);
    var callUrl = global.fetch.mock.calls[0][0];
    expect(callUrl).toBe('/api/item/10/quantity/');
  });

  test('decrement button fires API call', async function () {
    mod.initQuantityControls();
    var btn = document.querySelector('[data-item-id="10"] .qty-decrement');
    btn.click();
    await flushPromises();

    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  test('API error reverts optimistic UI', async function () {
    global.fetch = jest.fn(function () {
      return Promise.reject(new Error('Network error'));
    });
    global.showErrorSnackbar = jest.fn();

    mod.initQuantityControls();
    var wrapper = document.querySelector('[data-item-id="10"]');
    var btn = wrapper.querySelector('.qty-increment');
    btn.click();
    await flushPromises();

    // Should revert to original value
    expect(wrapper.getAttribute('data-quantity')).toBe('5');
    delete global.showErrorSnackbar;
  });

  test('click-to-edit creates input and saves on blur', async function () {
    global.fetch = jest.fn(function () {
      return Promise.resolve({
        ok: true,
        json: function () { return Promise.resolve({ quantity: 10, formatted: '10' }); },
      });
    });

    mod.initQuantityControls();
    var wrapper = document.querySelector('[data-item-id="10"]');
    var qtyValue = wrapper.querySelector('.qty-value');
    qtyValue.click();

    var input = wrapper.querySelector('.qty-input');
    expect(input).not.toBeNull();
    expect(input.type).toBe('number');

    // Change value and blur
    input.value = '10';
    input.dispatchEvent(new Event('blur'));
    await flushPromises();

    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  test('click-to-edit cancels on Escape', function () {
    mod.initQuantityControls();
    var wrapper = document.querySelector('[data-item-id="10"]');
    var qtyValue = wrapper.querySelector('.qty-value');
    qtyValue.click();

    var input = wrapper.querySelector('.qty-input');
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));

    // Input should be removed, original span restored
    expect(wrapper.querySelector('.qty-input')).toBeNull();
    expect(qtyValue.style.display).toBe('');
  });
});
