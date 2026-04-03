/**
 * @file sharing.js
 * Sharing dialog — invite users by email, manage access levels.
 * Requires fetch_utils.js to be loaded first.
 */

(function () {
  'use strict';

  /* ---- Element refs ---- */
  var dialog = document.getElementById('sharing-dialog');
  if (!dialog) return;

  var subtitle = document.getElementById('sharing-subtitle');
  var emailInput = document.getElementById('sharing-email');
  var permSelect = document.getElementById('sharing-permission');
  var inviteBtn = document.getElementById('sharing-invite-btn');
  var errorEl = document.getElementById('sharing-error');
  var successEl = document.getElementById('sharing-success');
  var listEl = document.getElementById('sharing-list');
  var emptyEl = document.getElementById('sharing-empty');
  var closeBtn = document.getElementById('sharing-close-btn');

  /** @type {string} Base URL for the current entity's sharing API */
  var baseUrl = '';

  /* ---- Helpers ---- */

  /**
   * Close dialog with animation.
   * @returns {void}
   */
  function closeDialog() {
    dialog.classList.add('dialog--closing');
    setTimeout(function () {
      dialog.classList.remove('dialog--closing');
      dialog.close();
    }, 150);
  }

  /**
   * Show error message.
   * @param {string} msg
   * @returns {void}
   */
  function showError(msg) {
    errorEl.textContent = msg;
    errorEl.classList.remove('hidden');
    successEl.classList.add('hidden');
  }

  /**
   * Show success message.
   * @param {string} msg
   * @returns {void}
   */
  function showSuccess(msg) {
    successEl.textContent = msg;
    successEl.classList.remove('hidden');
    errorEl.classList.add('hidden');
  }

  /** @returns {void} */
  function hideMessages() {
    errorEl.classList.add('hidden');
    successEl.classList.add('hidden');
  }

  /**
   * Build a share row element.
   * @param {Object} share - {id, email, permission}
   * @returns {HTMLElement}
   */
  function buildShareRow(share) {
    var row = document.createElement('div');
    row.className = 'flex items-center gap-2 rounded-md border border-border px-3 py-2';
    row.setAttribute('data-share-id', share.id);

    var email = document.createElement('span');
    email.className = 'min-w-0 flex-1 truncate text-sm text-foreground';
    email.textContent = share.email;

    var select = document.createElement('select');
    select.className = 'rounded-md border border-input bg-background px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring';
    select.innerHTML = '<option value="read">View</option><option value="write">Edit own</option><option value="write_all">Edit all</option>';
    select.value = share.permission;
    select.addEventListener('change', function () {
      updatePermission(share.id, select.value);
    });

    var removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'shrink-0 rounded-md p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive';
    removeBtn.setAttribute('aria-label', 'Remove access');
    removeBtn.innerHTML = '<svg class="h-4 w-4" viewBox="0 0 24 24" fill="currentColor"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>';
    removeBtn.addEventListener('click', function () {
      removeAccess(share.id, row);
    });

    row.appendChild(email);
    row.appendChild(select);
    row.appendChild(removeBtn);
    return row;
  }

  /**
   * Render the shares list.
   * @param {Array<Object>} shares
   * @returns {void}
   */
  function renderShares(shares) {
    // Remove existing share rows (keep emptyEl)
    var rows = listEl.querySelectorAll('[data-share-id]');
    rows.forEach(function (row) { row.remove(); });

    if (shares.length === 0) {
      emptyEl.classList.remove('hidden');
    } else {
      emptyEl.classList.add('hidden');
      shares.forEach(function (share) {
        listEl.appendChild(buildShareRow(share));
      });
    }
  }

  /**
   * Fetch and render current shares.
   * @returns {void}
   */
  function loadShares() {
    apiFetch(baseUrl)
      .then(function (r) {
        if (!r.ok) return r.json().then(function (d) { throw new Error(d.error || 'Failed to load shares'); });
        return r.json();
      })
      .then(function (data) { if (data) renderShares(data.shares); })
      .catch(function (err) { showError(err.message); });
  }

  /**
   * Invite a user by email.
   * @returns {void}
   */
  function invite() {
    var email = emailInput.value.trim();
    if (!email) { showError('Email is required'); return; }

    hideMessages();
    inviteBtn.disabled = true;

    apiFetch(baseUrl + 'add/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email, permission: permSelect.value }),
    })
      .then(function (r) {
        if (!r.ok) return r.json().then(function (d) { throw new Error(d.error || 'Failed'); });
        return r.json();
      })
      .then(function (share) {
        emailInput.value = '';
        showSuccess('Invited ' + share.email);
        emptyEl.classList.add('hidden');
        listEl.appendChild(buildShareRow(share));
      })
      .catch(function (err) { showError(err.message); })
      .finally(function () { inviteBtn.disabled = false; });
  }

  /**
   * Update a share's permission.
   * @param {number} accessId
   * @param {string} permission
   * @returns {void}
   */
  function updatePermission(accessId, permission) {
    hideMessages();
    apiFetch(baseUrl + accessId + '/update/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ permission: permission }),
    })
      .then(function (r) {
        if (!r.ok) return r.json().then(function (d) { throw new Error(d.error || 'Failed'); });
      })
      .catch(function (err) { showError(err.message); });
  }

  /**
   * Remove a share.
   * @param {number} accessId
   * @param {HTMLElement} rowEl
   * @returns {void}
   */
  function removeAccess(accessId, rowEl) {
    hideMessages();
    apiFetch(baseUrl + accessId + '/remove/', { method: 'POST' })
      .then(function (r) {
        if (!r.ok) return r.json().then(function (d) { throw new Error(d.error || 'Failed'); });
        rowEl.remove();
        // Check if list is now empty
        if (!listEl.querySelector('[data-share-id]')) {
          emptyEl.classList.remove('hidden');
        }
      })
      .catch(function (err) { showError(err.message); });
  }

  /* ---- Event listeners ---- */

  closeBtn.addEventListener('click', closeDialog);
  dialog.addEventListener('click', function (e) {
    if (e.target === dialog) closeDialog();
  });
  inviteBtn.addEventListener('click', invite);
  emailInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') invite();
  });

  /* ---- Public API ---- */

  /**
   * Open the sharing dialog for a unit.
   * @param {number} userId - The unit owner's user ID.
   * @param {string} accessToken - The unit's access token.
   * @param {string} entityName - Display name for the subtitle.
   * @returns {void}
   */
  window.openUnitSharing = function (userId, accessToken, entityName) {
    baseUrl = '/api/units/' + userId + '/' + accessToken + '/sharing/';
    subtitle.textContent = entityName;
    emailInput.value = '';
    hideMessages();
    renderShares([]);
    dialog.showModal();
    loadShares();
  };

  /**
   * Open the sharing dialog for a location.
   * @param {number} locationId - The location's ID.
   * @param {string} entityName - Display name for the subtitle.
   * @returns {void}
   */
  window.openLocationSharing = function (locationId, entityName) {
    baseUrl = '/api/locations/' + locationId + '/sharing/';
    subtitle.textContent = entityName;
    emailInput.value = '';
    hideMessages();
    renderShares([]);
    dialog.showModal();
    loadShares();
  };
})();
