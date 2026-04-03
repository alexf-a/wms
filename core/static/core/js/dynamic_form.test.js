describe('dynamic_form', function () {
  beforeEach(function () {
    jest.resetModules();
  });

  /**
   * Require the module after DOM setup (runs on DOMContentLoaded).
   */
  function loadAndInit() {
    require('./dynamic_form');
    document.dispatchEvent(new Event('DOMContentLoaded'));
  }

  function buildForm(stepsHtml, attrs) {
    attrs = attrs || '';
    document.body.innerHTML =
      '<form data-dynamic-form ' + attrs + '>' + stepsHtml + '</form>';
  }

  // --- Step navigation ---

  test('only initial step is visible on load', function () {
    buildForm([
      '<div class="dynamic-field" data-step="1"><input type="text" name="a"></div>',
      '<div class="dynamic-field" data-step="2" style="display:none"><input type="text" name="b"></div>',
      '<div class="dynamic-field" data-step="3" style="display:none"><input type="text" name="c"></div>',
    ].join(''));
    loadAndInit();

    var step1 = document.querySelector('[data-step="1"]');
    var step2 = document.querySelector('[data-step="2"]');
    expect(step1.style.display).not.toBe('none');
    expect(step2.style.display).toBe('none');
  });

  test('next button advances to next step when input has value', function () {
    buildForm([
      '<div class="dynamic-field" data-step="1">',
      '  <input type="text" name="a">',
      '  <button class="next-btn" type="button">Next</button>',
      '</div>',
      '<div class="dynamic-field" data-step="2" style="display:none">',
      '  <input type="text" name="b">',
      '</div>',
    ].join(''));
    loadAndInit();

    // Type value into step 1 input
    var input = document.querySelector('[data-step="1"] input');
    input.value = 'hello';
    input.dispatchEvent(new Event('input'));

    // Click next
    document.querySelector('.next-btn').click();

    var step2 = document.querySelector('[data-step="2"]');
    expect(step2.style.display).not.toBe('none');
  });

  test('Enter key on input advances to next step', function () {
    buildForm([
      '<div class="dynamic-field" data-step="1">',
      '  <input type="text" name="a">',
      '  <button class="next-btn" type="button">Next</button>',
      '</div>',
      '<div class="dynamic-field" data-step="2" style="display:none">',
      '  <input type="text" name="b">',
      '</div>',
    ].join(''));
    loadAndInit();

    var input = document.querySelector('[data-step="1"] input');
    input.value = 'test';
    input.dispatchEvent(new Event('input'));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));

    var step2 = document.querySelector('[data-step="2"]');
    expect(step2.style.display).not.toBe('none');
  });

  test('next button hidden when input is empty', function () {
    buildForm([
      '<div class="dynamic-field" data-step="1">',
      '  <input type="text" name="a">',
      '  <button class="next-btn" type="button" style="display:flex">Next</button>',
      '</div>',
      '<div class="dynamic-field" data-step="2" style="display:none">',
      '  <input type="text" name="b">',
      '</div>',
    ].join(''));
    loadAndInit();

    var nextBtn = document.querySelector('.next-btn');
    expect(nextBtn.style.display).toBe('none');
  });

  test('next button shown for optional steps regardless of value', function () {
    buildForm([
      '<div class="dynamic-field" data-step="1" data-optional>',
      '  <input type="text" name="a">',
      '  <button class="next-btn" type="button">Next</button>',
      '</div>',
      '<div class="dynamic-field" data-step="2" style="display:none">',
      '  <input type="text" name="b">',
      '</div>',
    ].join(''));
    loadAndInit();

    var nextBtn = document.querySelector('.next-btn');
    expect(nextBtn.style.display).not.toBe('none');
  });

  // --- Skip button ---

  test('skip button jumps to target step', function () {
    buildForm([
      '<div class="dynamic-field" data-step="1">',
      '  <input type="text" name="a">',
      '  <button class="skip-btn" data-skip-to="3" type="button">Skip</button>',
      '</div>',
      '<div class="dynamic-field" data-step="2" style="display:none">',
      '  <input type="text" name="b">',
      '</div>',
      '<div class="dynamic-field" data-step="3" style="display:none">',
      '  <input type="text" name="c">',
      '</div>',
    ].join(''));
    loadAndInit();

    document.querySelector('.skip-btn').click();

    expect(document.querySelector('[data-step="3"]').style.display).not.toBe('none');
  });

  // --- Conditional steps ---

  test('conditional step visibility toggles based on data-show-if', function () {
    buildForm([
      '<div class="dynamic-field" data-step="1">',
      '  <select name="type"><option value="">--</option><option value="special">Special</option></select>',
      '  <button class="next-btn" type="button">Next</button>',
      '</div>',
      '<div class="dynamic-field" data-step="2" data-show-if="type=special" style="display:none">',
      '  <input type="text" name="detail">',
      '</div>',
    ].join(''));
    loadAndInit();

    var condEl = document.querySelector('[data-step="2"]');
    // Initially hidden via conditional
    expect(condEl.classList.contains('conditional-hidden')).toBe(true);

    // Select 'special'
    var select = document.querySelector('select[name="type"]');
    select.value = 'special';
    select.dispatchEvent(new Event('change'));

    expect(condEl.classList.contains('conditional-hidden')).toBe(false);
  });

  // --- Select input ---

  test('select with value shows next button', function () {
    buildForm([
      '<div class="dynamic-field" data-step="1">',
      '  <select name="category"><option value="">--</option><option value="A">A</option></select>',
      '  <button class="next-btn" type="button">Next</button>',
      '</div>',
      '<div class="dynamic-field" data-step="2" style="display:none">',
      '  <input type="text" name="b">',
      '</div>',
    ].join(''));
    loadAndInit();

    var nextBtn = document.querySelector('.next-btn');
    expect(nextBtn.style.display).toBe('none');

    var select = document.querySelector('select[name="category"]');
    select.value = 'A';
    select.dispatchEvent(new Event('change'));

    expect(nextBtn.style.display).not.toBe('none');
  });

  // --- No form ---

  test('does not throw when no dynamic forms exist', function () {
    document.body.innerHTML = '<div>No forms here</div>';
    expect(function () {
      loadAndInit();
    }).not.toThrow();
  });
});
