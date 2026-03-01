/**
 * Dynamic multi-step form — progressive field reveal with validation.
 *
 * Scans the DOM for forms with `data-m3-dynamic-form` and initializes
 * step-by-step field reveal, input validation, and conditional visibility.
 * Runs automatically on DOMContentLoaded.
 */
(function () {
    'use strict';

    const FORM_SELECTOR = '[data-m3-dynamic-form]';
    const FIELD_SELECTOR = '.m3-dynamic-field[data-step]';
    const NEXT_BTN_SELECTOR = '.m3-next-btn';
    const SKIP_BTN_SELECTOR = '.m3-skip-btn';
    const STEP_INPUT_SELECTOR = '[data-step-input]';
    const CONDITIONAL_SELECTOR = '[data-show-if]';
    const DEFAULT_VISIBLE_DISPLAY = 'flex';
    const FOCUS_DELAY = 100;
    const ANIMATION_DURATION = 300;

    document.addEventListener('DOMContentLoaded', () => {
        const forms = document.querySelectorAll(FORM_SELECTOR);
        forms.forEach((form) => initializeDynamicForm(form));
    });

    /**
     * Initialize a single dynamic form: parse steps, attach listeners, set up conditionals.
     *
     * @param {HTMLFormElement} form - The form element with `data-m3-dynamic-form`.
     */
    function initializeDynamicForm(form) {
        const stepElements = Array.from(form.querySelectorAll(FIELD_SELECTOR));
        if (!stepElements.length) {
            return;
        }

        const stepsMap = groupStepsByNumber(stepElements);
        const totalSteps = getTotalSteps(form, stepsMap);
        const initialStep = getInitialStep(form, stepsMap);
        const stepInputs = resolveStepInputs(stepsMap);
        let currentStep = initialStep;

        // Initialize conditional step visibility
        const conditionalElements = form.querySelectorAll(CONDITIONAL_SELECTOR);
        initializeConditionalSteps(form, conditionalElements, stepsMap);

        /** @param {number} step - The step number to update the next button for. */
        const updateNextButton = (step) => {
            const groups = stepsMap[step] || [];

            groups.forEach((group) => {
                const nextBtn = group.querySelector(NEXT_BTN_SELECTOR);
                if (!nextBtn) {
                    return;
                }

                // Find the eligible input for this specific group
                const groupInput = findEligibleInput(group);
                const isOptional = group.hasAttribute('data-optional');
                const visibleDisplay = nextBtn.dataset.visibleDisplay || DEFAULT_VISIBLE_DISPLAY;

                if (isOptional) {
                    nextBtn.style.display = visibleDisplay;
                } else if (groupInput) {
                    nextBtn.style.display = hasInputValue(groupInput) ? visibleDisplay : 'none';
                } else {
                    nextBtn.style.display = visibleDisplay;
                }
            });
        };

        /** @param {number} step - The step number to reveal. */
        const showStep = (step) => {
            const groups = stepsMap[step] || [];
            if (!groups.length) {
                return;
            }

            groups.forEach((group) => {
                group.style.display = '';
                group.classList.add('slide-in');
                window.setTimeout(() => {
                    group.classList.remove('slide-in');
                }, ANIMATION_DURATION);
            });

            focusInput(stepInputs[step]);
            currentStep = Math.max(currentStep, step);
        };

        /** Advance to the next step if not already at the last step. */
        const goToNextStep = () => {
            if (currentStep >= totalSteps) {
                return;
            }
            showStep(currentStep + 1);
        };

        attachInputListeners(stepsMap, updateNextButton, goToNextStep);
        attachNextButtonListeners(form, goToNextStep);
        attachSkipButtonListeners(form, totalSteps, showStep);

        Object.keys(stepsMap)
            .map(Number)
            .forEach((step) => updateNextButton(step));
    }

    /**
     * Group step elements by their `data-step` number.
     *
     * @param {Array<HTMLElement>} stepElements - Elements with `data-step` attributes.
     * @returns {Object<number, Array<HTMLElement>>} Map of step number to element arrays.
     */
    function groupStepsByNumber(stepElements) {
        return stepElements.reduce((acc, el) => {
            const step = Number(el.dataset.step);
            if (!Number.isFinite(step)) {
                return acc;
            }

            if (!acc[step]) {
                acc[step] = [];
            }

            acc[step].push(el);
            return acc;
        }, {});
    }

    /**
     * Determine the total number of steps from `data-total-steps` attribute or step map keys.
     *
     * @param {HTMLElement} form - The form element.
     * @param {Object<number, Array<HTMLElement>>} stepsMap - Map of step numbers to elements.
     * @returns {number} The total number of steps.
     */
    function getTotalSteps(form, stepsMap) {
        const attrValue = Number(form.dataset.totalSteps);
        if (Number.isFinite(attrValue) && attrValue > 0) {
            return attrValue;
        }

        return Math.max(...Object.keys(stepsMap).map(Number));
    }

    /**
     * Determine the initial step from `data-initial-step` attribute or step map keys.
     *
     * @param {HTMLElement} form - The form element.
     * @param {Object<number, Array<HTMLElement>>} stepsMap - Map of step numbers to elements.
     * @returns {number} The initial step number.
     */
    function getInitialStep(form, stepsMap) {
        const attrValue = Number(form.dataset.initialStep);
        if (Number.isFinite(attrValue) && attrValue > 0) {
            return attrValue;
        }

        return Math.min(...Object.keys(stepsMap).map(Number));
    }

    /**
     * Build a map of step number to the first eligible input element for that step.
     *
     * @param {Object<number, Array<HTMLElement>>} stepsMap - Map of step numbers to elements.
     * @returns {Object<number, HTMLElement>} Map of step number to input element.
     */
    function resolveStepInputs(stepsMap) {
        const result = {};
        Object.entries(stepsMap).forEach(([step, groups]) => {
            const input = groups
                .map((group) => findEligibleInput(group))
                .find(Boolean);

            if (input) {
                result[Number(step)] = input;
            }
        });
        return result;
    }

    /**
     * Find the first eligible input element within a step group.
     *
     * @param {HTMLElement} group - The step group element.
     * @returns {HTMLElement|null} The first eligible input, or null if none found.
     */
    function findEligibleInput(group) {
        return (
            group.querySelector(STEP_INPUT_SELECTOR) ||
            group.querySelector('input:not([type="hidden"])') ||
            group.querySelector('textarea') ||
            group.querySelector('select')
        );
    }

    /**
     * Check whether an input element has a non-empty value.
     *
     * @param {HTMLElement} input - The input element to check.
     * @returns {boolean} True if the input has a value.
     */
    function hasInputValue(input) {
        if (!input || input.disabled) {
            return false;
        }

        const tagName = input.tagName.toLowerCase();

        if (tagName === 'select') {
            return Boolean(input.value);
        }

        if (input.type === 'checkbox' || input.type === 'radio') {
            if (!input.name) {
                return input.checked;
            }

            const form = input.form || document;
            const selector = `input[name="${escapeCssIdentifier(input.name)}"]`;
            const group = form.querySelectorAll(selector);
            return Array.from(group).some((control) => control.checked);
        }

        return Boolean(input.value && input.value.trim().length > 0);
    }

    /**
     * Focus an input element after a short delay.
     *
     * @param {HTMLElement|undefined} input - The input element to focus.
     */
    function focusInput(input) {
        if (!input || typeof input.focus !== 'function' || input.disabled) {
            return;
        }

        window.setTimeout(() => {
            input.focus();
        }, FOCUS_DELAY);
    }

    /**
     * Attach input and keydown listeners to step inputs for validation and auto-advance.
     *
     * @param {Object<number, Array<HTMLElement>>} stepsMap - Map of step numbers to elements.
     * @param {Function} updateNextButton - Callback to update next button visibility.
     * @param {Function} goToNextStep - Callback to advance to the next step.
     */
    function attachInputListeners(stepsMap, updateNextButton, goToNextStep) {
        // Iterate over all groups to attach listeners to each group's input
        Object.entries(stepsMap).forEach(([stepKey, groups]) => {
            const step = Number(stepKey);
            
            groups.forEach((group) => {
                const input = findEligibleInput(group);
                if (!input) {
                    return;
                }

                input.addEventListener('input', () => updateNextButton(step));
                
                // Select elements also need 'change' event for better cross-browser support
                if (input.tagName === 'SELECT') {
                    input.addEventListener('change', () => updateNextButton(step));
                }

                if (input.tagName === 'TEXTAREA') {
                    input.addEventListener('keydown', (event) => {
                        if ((event.ctrlKey || event.metaKey) && event.key === 'Enter' && hasInputValue(input)) {
                            event.preventDefault();
                            goToNextStep();
                        }
                    });
                } else {
                    input.addEventListener('keydown', (event) => {
                        if (event.key === 'Enter' && hasInputValue(input)) {
                            event.preventDefault();
                            goToNextStep();
                        }
                    });
                }
            });
        });
    }

    /**
     * Attach click listeners to all next buttons to advance on click.
     *
     * @param {HTMLElement} form - The form element.
     * @param {Function} goToNextStep - Callback to advance to the next step.
     */
    function attachNextButtonListeners(form, goToNextStep) {
        const buttons = form.querySelectorAll(NEXT_BTN_SELECTOR);
        buttons.forEach((button) => {
            button.addEventListener('click', (event) => {
                event.preventDefault();
                goToNextStep();
            });
        });
    }

    /**
     * Attach click listeners to skip buttons to jump to a target step.
     *
     * @param {HTMLElement} form - The form element.
     * @param {number} totalSteps - The total number of steps (used as default skip target).
     * @param {Function} showStep - Callback to show a specific step.
     */
    function attachSkipButtonListeners(form, totalSteps, showStep) {
        const buttons = form.querySelectorAll(SKIP_BTN_SELECTOR);
        buttons.forEach((button) => {
            button.addEventListener('click', (event) => {
                event.preventDefault();
                const attrValue = Number(button.dataset.skipTo);
                const targetStep = Number.isFinite(attrValue) && attrValue > 0 ? attrValue : totalSteps;
                showStep(targetStep);
            });
        });
    }

    /**
     * Initialize conditional step visibility based on `data-show-if` attributes.
     *
     * @param {HTMLElement} form - The form element.
     * @param {NodeList} conditionalElements - Elements with `data-show-if` attributes.
     * @param {Object<number, Array<HTMLElement>>} stepsMap - Map of step numbers to elements.
     */
    function initializeConditionalSteps(form, conditionalElements, stepsMap) {
        if (!conditionalElements.length) {
            return;
        }

        // Parse all conditional rules and group by control field
        const conditionalsByField = {};
        conditionalElements.forEach((el) => {
            const condition = el.dataset.showIf;
            if (!condition) {
                return;
            }

            const [fieldName, expectedValue] = condition.split('=').map(s => s.trim());
            if (!fieldName || !expectedValue) {
                return;
            }

            if (!conditionalsByField[fieldName]) {
                conditionalsByField[fieldName] = [];
            }

            conditionalsByField[fieldName].push({
                element: el,
                expectedValue: expectedValue,
                step: Number(el.dataset.step)
            });
        });

        // Attach listeners to control fields
        Object.keys(conditionalsByField).forEach((fieldName) => {
            const controls = form.querySelectorAll(`[name="${escapeCssIdentifier(fieldName)}"]`);
            if (!controls.length) {
                return;
            }

            const updateConditionalVisibility = () => {
                const currentValue = getFieldValue(form, fieldName);
                const conditionals = conditionalsByField[fieldName];

                conditionals.forEach((conditional) => {
                    const shouldShow = currentValue === conditional.expectedValue;
                    
                    if (shouldShow) {
                        // Remove the hidden class to allow step logic to control visibility
                        conditional.element.classList.remove('m3-conditional-hidden');
                    } else {
                        // Add the hidden class
                        conditional.element.classList.add('m3-conditional-hidden');
                    }
                });
            };

            // Attach change listeners
            controls.forEach((control) => {
                control.addEventListener('change', updateConditionalVisibility);
                control.addEventListener('input', updateConditionalVisibility);
            });

            // Initial update
            updateConditionalVisibility();
        });
    }

    /**
     * Get the current value of a named form field.
     *
     * @param {HTMLElement} form - The form element.
     * @param {string} fieldName - The name attribute of the field.
     * @returns {string} The field's current value, or empty string if not found.
     */
    function getFieldValue(form, fieldName) {
        const input = form.querySelector(`[name="${escapeCssIdentifier(fieldName)}"]:checked`) ||
                     form.querySelector(`[name="${escapeCssIdentifier(fieldName)}"]`);
        return input ? input.value : '';
    }

    /**
     * Escape a string for safe use as a CSS identifier in querySelector.
     * Uses `CSS.escape` when available, with a polyfill fallback.
     *
     * @param {string} value - The string to escape.
     * @returns {string} The CSS-safe escaped string.
     */
    function escapeCssIdentifier(value) {
        if (window.CSS && typeof window.CSS.escape === 'function') {
            return window.CSS.escape(value);
        }

        // Polyfill adapted from https://github.com/mathiasbynens/CSS.escape (MIT License)
        const string = String(value);
        const length = string.length;
        let index = -1;
        let result = '';
        const firstCodeUnit = string.charCodeAt(0);

        while (++index < length) {
            const codeUnit = string.charCodeAt(index);

            if (codeUnit === 0x0000) {
                result += '\uFFFD';
                continue;
            }

            if (
                (codeUnit >= 0x0001 && codeUnit <= 0x001f) ||
                codeUnit === 0x007f ||
                (index === 0 && codeUnit >= 0x0030 && codeUnit <= 0x0039) ||
                (index === 1 && codeUnit >= 0x0030 && codeUnit <= 0x0039 && firstCodeUnit === 0x002d)
            ) {
                result += `\\${codeUnit.toString(16)} `;
                continue;
            }

            if (
                (index === 0 && codeUnit === 0x002d && length === 1) ||
                codeUnit >= 0x0080 ||
                codeUnit === 0x002d ||
                codeUnit === 0x005f ||
                (codeUnit >= 0x0030 && codeUnit <= 0x0039) ||
                (codeUnit >= 0x0041 && codeUnit <= 0x005a) ||
                (codeUnit >= 0x0061 && codeUnit <= 0x007a)
            ) {
                result += string.charAt(index);
                continue;
            }

            result += `\\${string.charAt(index)}`;
        }

        return result;
    }
})();
