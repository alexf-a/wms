/**
 * Onboarding wizard — client-side step navigation, location/unit creation, completion.
 *
 * When loaded via <script> tag with data-* attributes, auto-initializes.
 * When loaded via require() (tests), exports initOnboarding(config) for manual init.
 */

function initOnboarding(config) {
  'use strict';

  var CREATE_LOCATION_URL = config.createLocationUrl;
  var CREATE_UNIT_URL = config.createUnitUrl;
  var COMPLETE_ONBOARDING_URL = config.completeOnboardingUrl;

  // --- State ---
  var currentStep = 0;
  var createdLocationId = null;
  var createdLocationName = null;
  var saving = false;

  // --- DOM refs ---
  var steps = document.querySelectorAll('.onboarding-step');
  var progressBar = document.getElementById('progress-bar');
  var progressSteps = [
    document.getElementById('progress-step-1'),
    document.getElementById('progress-step-2')
  ];
  var progressLabel = document.getElementById('progress-label');

  // Step 1 elements
  var locationNameInput = document.getElementById('location-name');
  var locationAddressInput = document.getElementById('location-address');
  var locationError = document.getElementById('location-error');

  // Step 2 elements
  var unitNameInput = document.getElementById('unit-name');
  var unitError = document.getElementById('unit-error');
  var unitLocationHint = document.getElementById('unit-location-hint');
  var unitLocationNameEl = document.getElementById('unit-location-name');

  // --- Functions ---

  function showStep(n) {
    currentStep = n;
    steps.forEach(function (el) { el.classList.add('hidden'); });
    steps[n].classList.remove('hidden');
    updateProgress();
  }

  function updateProgress() {
    if (currentStep === 1 || currentStep === 2) {
      progressBar.classList.remove('hidden');
      progressSteps[0].classList.toggle('bg-primary', currentStep >= 1);
      progressSteps[0].classList.toggle('bg-muted', currentStep < 1);
      progressSteps[1].classList.toggle('bg-primary', currentStep >= 2);
      progressSteps[1].classList.toggle('bg-muted', currentStep < 2);
      progressLabel.textContent = 'Step ' + currentStep + ' of 2';
    } else {
      progressBar.classList.add('hidden');
    }
  }

  function setDisabled(disabled) {
    saving = disabled;
    var buttons = document.querySelectorAll('#onboarding-wizard button');
    buttons.forEach(function (btn) { btn.disabled = disabled; });
  }

  function showError(el, message) {
    el.textContent = message;
    el.classList.remove('hidden');
  }

  function hideError(el) {
    el.classList.add('hidden');
    el.textContent = '';
  }

  async function handleCreateLocation() {
    var name = locationNameInput.value.trim();
    if (!name) {
      showStep(2);
      return;
    }
    hideError(locationError);
    setDisabled(true);

    try {
      var res = await apiFetch(CREATE_LOCATION_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name,
          address: locationAddressInput.value.trim() || null
        })
      });
      var data = await res.json();
      if (!res.ok) {
        showError(locationError, data.error || 'Failed to create location.');
        return;
      }
      createdLocationId = data.id;
      createdLocationName = data.name;
      unitLocationHint.classList.remove('hidden');
      unitLocationNameEl.textContent = createdLocationName;
      showStep(2);
    } catch (err) {
      showError(locationError, 'Network error. Please try again.');
    } finally {
      setDisabled(false);
    }
  }

  async function handleCreateUnit() {
    var name = unitNameInput.value.trim();
    if (!name) {
      await finish();
      return;
    }
    hideError(unitError);
    setDisabled(true);

    try {
      var payload = { name: name };
      if (createdLocationId) {
        payload.location_id = createdLocationId;
      }
      var res = await apiFetch(CREATE_UNIT_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      var data = await res.json();
      if (!res.ok) {
        showError(unitError, data.error || 'Failed to create unit.');
        return;
      }
      await finish();
    } catch (err) {
      showError(unitError, 'Network error. Please try again.');
    } finally {
      setDisabled(false);
    }
  }

  async function finish() {
    setDisabled(true);
    try {
      await apiFetch(COMPLETE_ONBOARDING_URL, { method: 'POST' });
    } catch (err) {
      // Best-effort — don't block the user from proceeding
    }
    showStep(3);
    setDisabled(false);
  }

  // --- Event listeners ---
  document.getElementById('btn-get-started').addEventListener('click', function () {
    showStep(1);
  });

  document.getElementById('btn-location-next').addEventListener('click', handleCreateLocation);
  document.getElementById('btn-location-skip').addEventListener('click', function () {
    showStep(2);
  });

  document.getElementById('btn-unit-next').addEventListener('click', handleCreateUnit);
  document.getElementById('btn-unit-back').addEventListener('click', function () {
    showStep(1);
  });
  document.getElementById('btn-unit-skip').addEventListener('click', function () {
    finish();
  });

  // Initialize
  showStep(0);
}

// Auto-initialize when loaded via <script> tag with data attributes
if (typeof document !== 'undefined' && document.currentScript) {
  var scriptTag = document.currentScript;
  initOnboarding({
    createLocationUrl: scriptTag.getAttribute('data-create-location-url'),
    createUnitUrl: scriptTag.getAttribute('data-create-unit-url'),
    completeOnboardingUrl: scriptTag.getAttribute('data-complete-onboarding-url'),
  });
}

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { initOnboarding: initOnboarding };
}
