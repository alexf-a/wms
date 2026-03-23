describe('debug utilities', function () {
  var originalLog, originalError, originalWarn;

  beforeEach(function () {
    originalLog = console.log;
    originalError = console.error;
    originalWarn = console.warn;
    console.log = jest.fn();
    console.error = jest.fn();
    console.warn = jest.fn();
  });

  afterEach(function () {
    console.log = originalLog;
    console.error = originalError;
    console.warn = originalWarn;
    delete document.documentElement.dataset.debug;
    jest.resetModules();
  });

  function loadModule(debugFlag) {
    if (debugFlag) {
      document.documentElement.dataset.debug = 'true';
    } else {
      delete document.documentElement.dataset.debug;
    }
    return require('./debug');
  }

  test('debugLog logs when WMS_DEBUG is true', function () {
    var mod = loadModule(true);
    mod.debugLog('hello', 123);
    expect(console.log).toHaveBeenCalledWith('hello', 123);
  });

  test('debugLog is silent when WMS_DEBUG is false', function () {
    var mod = loadModule(false);
    mod.debugLog('hidden');
    expect(console.log).not.toHaveBeenCalled();
  });

  test('debugError logs when WMS_DEBUG is true', function () {
    var mod = loadModule(true);
    mod.debugError('err');
    expect(console.error).toHaveBeenCalledWith('err');
  });

  test('debugWarn logs when WMS_DEBUG is true', function () {
    var mod = loadModule(true);
    mod.debugWarn('warn');
    expect(console.warn).toHaveBeenCalledWith('warn');
  });

  test('errorLog always logs regardless of debug flag', function () {
    var mod = loadModule(false);
    mod.errorLog('always');
    expect(console.error).toHaveBeenCalledWith('always');
  });
});
