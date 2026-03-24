describe('add_items_flow', function () {
  var mod;

  beforeEach(function () {
    jest.resetModules();

    // Set up the full DOM expected by initAddItemsFlow
    document.body.innerHTML = [
      '<form id="item-form">',
      '  <input name="csrfmiddlewaretoken" value="csrf-tok">',
      '  <input type="file" id="hero-image-input" accept="image/*">',
      '  <button id="skip-to-manual" type="button">Skip</button>',
      '  <div id="form-section" style="display:none">',
      '    <div id="image-preview-container" style="display:none">',
      '      <img id="preview-image" src="">',
      '    </div>',
      '    <div id="loading-indicator" style="display:none"></div>',
      '    <div id="form-card" style="display:none">',
      '      <input id="id_name" type="text">',
      '      <textarea id="id_description"></textarea>',
      '    </div>',
      '  </div>',
      '</form>',
    ].join('\n');

    // Stub scrollIntoView (not available in jsdom)
    document.getElementById('form-section').scrollIntoView = jest.fn();

    // Mock globals that templates normally provide
    global.debugLog = jest.fn();
    global.revealSection = jest.fn(function (section) {
      section.style.display = 'block';
    });
    global.showErrorSnackbar = jest.fn();
    global.fetch = jest.fn();

    // Mock URL.createObjectURL / revokeObjectURL
    global.URL.createObjectURL = jest.fn(function () { return 'blob:fake-url'; });
    global.URL.revokeObjectURL = jest.fn();

    mod = require('./add_items_flow');
    // The module registers on DOMContentLoaded but in jsdom readyState is already 'complete',
    // so we need to call initAddItemsFlow manually.
    mod.initAddItemsFlow();
  });

  afterEach(function () {
    delete global.debugLog;
    delete global.revealSection;
    delete global.showErrorSnackbar;
    delete global.fetch;
  });

  // --- compressImage ---

  test('compressImage resolves with a blob', async function () {
    var mockBlob = new Blob(['test'], { type: 'image/jpeg' });
    var mockCtx = { drawImage: jest.fn() };
    var mockCanvas = {
      width: 0,
      height: 0,
      getContext: jest.fn(function () { return mockCtx; }),
      toBlob: jest.fn(function (cb) { cb(mockBlob); }),
    };

    var origCreate = document.createElement.bind(document);
    jest.spyOn(document, 'createElement').mockImplementation(function (tag) {
      if (tag === 'canvas') return mockCanvas;
      return origCreate(tag);
    });

    var origImage = global.Image;
    global.Image = function () {
      var img = {};
      setTimeout(function () {
        img.width = 800;
        img.height = 600;
        if (img.onload) img.onload();
      }, 0);
      return img;
    };

    var file = new File(['data'], 'test.jpg', { type: 'image/jpeg' });
    var result = await mod.compressImage(file);
    expect(result).toBe(mockBlob);

    global.Image = origImage;
    document.createElement.mockRestore();
  });

  // --- initAddItemsFlow ---

  test('skip button shows form and hides preview', function () {
    document.getElementById('skip-to-manual').click();

    expect(document.getElementById('form-card').style.display).toBe('block');
    expect(document.getElementById('image-preview-container').style.display).toBe('none');
    expect(global.revealSection).toHaveBeenCalled();
  });

  test('image upload triggers API call', async function () {
    global.fetch.mockReturnValue(Promise.resolve({
      ok: true,
      status: 200,
      json: function () { return Promise.resolve({ name: 'Widget', description: 'A thing' }); },
    }));

    var file = new File(['data'], 'photo.jpg', { type: 'image/jpeg' });

    var mockBlob = new Blob(['compressed'], { type: 'image/jpeg' });
    var mockCtx = { drawImage: jest.fn() };
    var mockCanvas = {
      width: 0, height: 0,
      getContext: jest.fn(function () { return mockCtx; }),
      toBlob: jest.fn(function (cb) { cb(mockBlob); }),
    };
    var origCreate = document.createElement.bind(document);
    jest.spyOn(document, 'createElement').mockImplementation(function (tag) {
      if (tag === 'canvas') return mockCanvas;
      return origCreate(tag);
    });

    var origImage = global.Image;
    global.Image = function () {
      var img = {};
      setTimeout(function () {
        img.width = 500;
        img.height = 400;
        if (img.onload) img.onload();
      }, 0);
      return img;
    };

    var input = document.getElementById('hero-image-input');
    Object.defineProperty(input, 'files', {
      value: [file],
      writable: false,
    });
    input.dispatchEvent(new Event('change'));

    // Wait for async processing (compression + fetch)
    await new Promise(function (r) { setTimeout(r, 50); });

    var apiCalls = global.fetch.mock.calls.filter(function (c) {
      return c[0] === '/api/extract-item-features/';
    });
    expect(apiCalls.length).toBe(1);

    global.Image = origImage;
    document.createElement.mockRestore();
  });

  test('API error shows snackbar', async function () {
    global.fetch.mockReturnValue(Promise.resolve({
      ok: false,
      status: 400,
      json: function () { return Promise.resolve({ error: 'Bad image' }); },
    }));

    var file = new File(['data'], 'bad.jpg', { type: 'image/jpeg' });
    var mockBlob = new Blob(['compressed'], { type: 'image/jpeg' });
    var mockCtx = { drawImage: jest.fn() };
    var mockCanvas = {
      width: 0, height: 0,
      getContext: jest.fn(function () { return mockCtx; }),
      toBlob: jest.fn(function (cb) { cb(mockBlob); }),
    };
    var origCreate = document.createElement.bind(document);
    jest.spyOn(document, 'createElement').mockImplementation(function (tag) {
      if (tag === 'canvas') return mockCanvas;
      return origCreate(tag);
    });

    var origImage = global.Image;
    global.Image = function () {
      var img = {};
      setTimeout(function () {
        img.width = 500;
        img.height = 400;
        if (img.onload) img.onload();
      }, 0);
      return img;
    };

    var input = document.getElementById('hero-image-input');
    Object.defineProperty(input, 'files', {
      value: [file],
      writable: false,
    });
    input.dispatchEvent(new Event('change'));

    await new Promise(function (r) { setTimeout(r, 50); });

    expect(global.showErrorSnackbar).toHaveBeenCalledWith('Bad image');

    global.Image = origImage;
    document.createElement.mockRestore();
  });

});
