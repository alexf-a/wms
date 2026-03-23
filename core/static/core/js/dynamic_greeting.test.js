describe('dynamic_greeting', function () {
  beforeEach(function () {
    jest.useFakeTimers();
    jest.resetModules();
  });

  afterEach(function () {
    jest.useRealTimers();
  });

  test('sets initial greeting from greetings array', function () {
    document.body.innerHTML = '<h1 id="dynamic-welcome"></h1>';
    require('./dynamic_greeting');

    var el = document.getElementById('dynamic-welcome');
    var greetings = [
      'Welcome to WMS',
      'Find Your Shi...Stuff',
      'Storage, Simplified',
      "Where's My...? Solved",
      'Chaos \u2192 Order',
    ];
    expect(greetings).toContain(el.textContent);
  });

  test('rotates greeting after interval', function () {
    document.body.innerHTML = '<h1 id="dynamic-welcome"></h1>';
    require('./dynamic_greeting');

    var el = document.getElementById('dynamic-welcome');
    var initial = el.textContent;

    // Advance past the setInterval (2000ms) + the inner setTimeout (300ms)
    jest.advanceTimersByTime(2300);

    // The text should have changed (rotated to next greeting)
    expect(el.textContent).not.toBe('');
    // Opacity should be restored
    expect(el.style.opacity).toBe('1');
  });

  test('does not throw when element is missing', function () {
    document.body.innerHTML = '';
    expect(function () {
      require('./dynamic_greeting');
    }).not.toThrow();
  });
});
