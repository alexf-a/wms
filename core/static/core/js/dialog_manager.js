/**
 * dialog_manager.js — lightweight helpers for native <dialog> elements.
 *
 * Provides:
 *   openModal(id)       – opens a dialog as a modal (backdrop + trap focus)
 *   closeDialog(id)     – closes a dialog with a fade-out animation
 *   openBottomSheet(id) – opens a dialog styled as a bottom sheet
 *
 * All functions accept either a string (element ID) or a <dialog> element.
 */

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function _resolve(idOrEl) {
    if (typeof idOrEl === 'string') {
        return document.getElementById(idOrEl);
    }
    return idOrEl;
}

/* ------------------------------------------------------------------ */
/*  Public API                                                         */
/* ------------------------------------------------------------------ */

/**
 * Open a <dialog> as a modal (centered overlay with backdrop).
 * @param {string|HTMLDialogElement} idOrEl
 */
function openModal(idOrEl) {
    const dialog = _resolve(idOrEl);
    if (!dialog) return;
    dialog.classList.remove('dialog--closing');
    dialog.showModal();
}

/**
 * Open a <dialog> styled as a bottom sheet (slides up from bottom).
 * The dialog element should have the `dialog--bottom-sheet` CSS class.
 * @param {string|HTMLDialogElement} idOrEl
 */
function openBottomSheet(idOrEl) {
    const dialog = _resolve(idOrEl);
    if (!dialog) return;
    dialog.classList.add('dialog--bottom-sheet');
    dialog.classList.remove('dialog--closing');
    dialog.showModal();
}

/**
 * Close a <dialog> with a short fade/slide-out animation, then actually
 * close it so the browser removes it from the top layer.
 * @param {string|HTMLDialogElement} idOrEl
 */
function closeDialog(idOrEl) {
    const dialog = _resolve(idOrEl);
    if (!dialog) return;

    dialog.classList.add('dialog--closing');

    function onEnd() {
        dialog.classList.remove('dialog--closing');
        dialog.close();
        dialog.removeEventListener('animationend', onEnd);
    }
    dialog.addEventListener('animationend', onEnd, { once: true });

    // Safety: if the animation never fires (e.g. prefers-reduced-motion),
    // close after a short timeout.
    setTimeout(function () {
        if (dialog.open) {
            dialog.classList.remove('dialog--closing');
            dialog.close();
        }
    }, 300);
}

/* ------------------------------------------------------------------ */
/*  Auto-close on backdrop click                                       */
/* ------------------------------------------------------------------ */

document.addEventListener('click', function (e) {
    if (e.target.tagName === 'DIALOG' && e.target.open) {
        // The click landed on the <dialog> backdrop (not inner content).
        var rect = e.target.getBoundingClientRect();
        var insideDialog =
            e.clientX >= rect.left &&
            e.clientX <= rect.right &&
            e.clientY >= rect.top &&
            e.clientY <= rect.bottom;

        // For a <dialog> with showModal(), clicks outside the element
        // box still register on the dialog element itself.  We can
        // detect those by checking whether the click is inside the
        // rendered box.
        if (!insideDialog) {
            closeDialog(e.target);
        }
    }
});
