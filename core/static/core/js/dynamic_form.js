(function () {
    'use strict';

    const FORM_SELECTOR = '[data-m3-dynamic-form]';
    const FIELD_SELECTOR = '.m3-dynamic-field[data-step]';
    const NEXT_BTN_SELECTOR = '.m3-next-btn';
    const SKIP_BTN_SELECTOR = '.m3-skip-btn';
    const STEP_INPUT_SELECTOR = '[data-step-input]';
    const DEFAULT_VISIBLE_DISPLAY = 'flex';
    const FOCUS_DELAY = 100;
    const ANIMATION_DURATION = 300;

    document.addEventListener('DOMContentLoaded', () => {
        const forms = document.querySelectorAll(FORM_SELECTOR);
        forms.forEach((form) => initializeDynamicForm(form));
    });

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

        const updateNextButton = (step) => {
            const input = stepInputs[step];
            const groups = stepsMap[step] || [];

            groups.forEach((group) => {
                const nextBtn = group.querySelector(NEXT_BTN_SELECTOR);
                if (!nextBtn) {
                    return;
                }

                const visibleDisplay = nextBtn.dataset.visibleDisplay || DEFAULT_VISIBLE_DISPLAY;

                if (input) {
                    nextBtn.style.display = hasInputValue(input) ? visibleDisplay : 'none';
                } else {
                    nextBtn.style.display = visibleDisplay;
                }
            });
        };

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

        const goToNextStep = () => {
            if (currentStep >= totalSteps) {
                return;
            }
            showStep(currentStep + 1);
        };

        attachInputListeners(stepInputs, updateNextButton, goToNextStep);
        attachNextButtonListeners(form, goToNextStep);
        attachSkipButtonListeners(form, totalSteps, showStep);

        Object.keys(stepsMap)
            .map(Number)
            .forEach((step) => updateNextButton(step));
    }

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

    function getTotalSteps(form, stepsMap) {
        const attrValue = Number(form.dataset.totalSteps);
        if (Number.isFinite(attrValue) && attrValue > 0) {
            return attrValue;
        }

        return Math.max(...Object.keys(stepsMap).map(Number));
    }

    function getInitialStep(form, stepsMap) {
        const attrValue = Number(form.dataset.initialStep);
        if (Number.isFinite(attrValue) && attrValue > 0) {
            return attrValue;
        }

        return Math.min(...Object.keys(stepsMap).map(Number));
    }

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

    function findEligibleInput(group) {
        return (
            group.querySelector(STEP_INPUT_SELECTOR) ||
            group.querySelector('input:not([type="hidden"])') ||
            group.querySelector('textarea') ||
            group.querySelector('select')
        );
    }

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

    function focusInput(input) {
        if (!input || typeof input.focus !== 'function' || input.disabled) {
            return;
        }

        window.setTimeout(() => {
            input.focus();
        }, FOCUS_DELAY);
    }

    function attachInputListeners(stepInputs, updateNextButton, goToNextStep) {
        Object.entries(stepInputs).forEach(([stepKey, input]) => {
            const step = Number(stepKey);
            if (!input) {
                return;
            }

            input.addEventListener('input', () => updateNextButton(step));

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
    }

    function attachNextButtonListeners(form, goToNextStep) {
        const buttons = form.querySelectorAll(NEXT_BTN_SELECTOR);
        buttons.forEach((button) => {
            button.addEventListener('click', (event) => {
                event.preventDefault();
                goToNextStep();
            });
        });
    }

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
