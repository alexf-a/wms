/**
 * Attach quantity logic helpers to the active global scope.
 *
 * @param {Window|typeof globalThis} globalScope - Browser window or Node-like global object.
 * @returns {void}
 */
(function attachQuantityLogic(globalScope) {
    /**
     * Global property name used to expose the quantity logic API.
     *
     * @type {string}
     */
    const LOGIC_API_NAME = 'WMSQuantityLogic';
    const nonCountStepRaw = Number(globalScope.WMS_QUANTITY_NON_COUNT_STEP);
    const decimalPlacesRaw = Number(globalScope.WMS_QUANTITY_DECIMAL_PLACES);

    if (!Number.isFinite(nonCountStepRaw) || nonCountStepRaw <= 0) {
        throw new Error('WMS_QUANTITY_NON_COUNT_STEP must be provided as a positive number.');
    }

    if (!Number.isInteger(decimalPlacesRaw) || decimalPlacesRaw < 0) {
        throw new Error('WMS_QUANTITY_DECIMAL_PLACES must be provided as a non-negative integer.');
    }

    const nonCountStep = nonCountStepRaw;
    const decimalPlaces = decimalPlacesRaw;

    const roundingFactor = 10 ** decimalPlaces;

    /**
     * Return the increment/decrement step size for a quantity unit.
     *
     * @param {string} quantityUnit - Unit symbol (for example: count, kg, mL).
     * @returns {number} 1 for count units, otherwise the configured non-count step.
     */
    function getStepSize(quantityUnit) {
        return quantityUnit === 'count' ? 1 : nonCountStep;
    }

    /**
     * Calculate the optimistic quantity shown immediately in the UI.
     *
     * Rules:
    * - Uses a unit-based step size (1 for count, configured non-count step otherwise)
     * - Clamps to a minimum of 0
    * - Rounds non-count values to configured decimal places
     *
     * @param {number} currentQuantity - Current numeric quantity.
     * @param {string} action - Quantity action (increment or decrement).
     * @param {string} quantityUnit - Unit symbol for the item quantity.
     * @returns {number} New optimistic quantity for display.
     */
    function calculateOptimisticQuantity(currentQuantity, action, quantityUnit) {
        const step = getStepSize(quantityUnit);
        let newQuantity = action === 'increment' ? currentQuantity + step : currentQuantity - step;
        newQuantity = Math.max(0, newQuantity);
        if (quantityUnit !== 'count') {
            newQuantity = Math.round(newQuantity * roundingFactor) / roundingFactor;
        }
        return newQuantity;
    }

    /**
     * Format a quantity for display in the UI.
     *
     * @param {number} quantity - Numeric quantity value.
     * @param {string} quantityUnit - Unit symbol used by the item.
     * @param {Object<string, string>} [unitNameMap] - Optional map of unit symbol to display name.
     * @returns {string} Human-readable quantity string.
     */
    function formatQuantity(quantity, quantityUnit, unitNameMap) {
        const unitDisplay = (unitNameMap && unitNameMap[quantityUnit]) || quantityUnit;
        const formattedValue = quantityUnit === 'count'
            ? Math.round(quantity)
            : quantity.toFixed(decimalPlaces);
        return `${formattedValue} ${unitDisplay.toLowerCase()}`;
    }

    /**
     * Create initial state for tracking parallel in-flight requests per item.
     *
     * @returns {{nextSeq: number, lastAppliedSeq: number, pendingCount: number}} Fresh pending state object.
     */
    function createPendingState() {
        return {
            nextSeq: 1,
            lastAppliedSeq: 0,
            pendingCount: 0,
        };
    }

    /**
     * Record a newly dispatched request in state and return its sequence number.
     *
     * @param {{nextSeq: number, lastAppliedSeq: number, pendingCount: number}} state - Mutable request state for one item.
     * @returns {number} Sequence number assigned to the recorded request.
     */
    function recordRequest(state) {
        const requestSeq = state.nextSeq;
        state.nextSeq += 1;
        state.pendingCount += 1;
        return requestSeq;
    }

    /**
     * Resolve a completed request and decide whether server response should be applied.
     *
     * Applies response only when this completion leaves no pending requests.
     *
     * @param {{nextSeq: number, lastAppliedSeq: number, pendingCount: number}} state - Mutable request state for one item.
     * @param {number} requestSeq - Sequence number of the completed request.
     * @returns {{shouldApply: boolean}} Whether the caller should apply the response to the UI.
     */
    function resolveRequest(state, requestSeq) {
        state.pendingCount = Math.max(0, state.pendingCount - 1);
        const shouldApply = state.pendingCount === 0;
        if (shouldApply) {
            state.lastAppliedSeq = requestSeq;
        }
        return { shouldApply };
    }

    /**
     * Check whether a server response may be applied with current pending state.
     *
     * @param {{nextSeq: number, lastAppliedSeq: number, pendingCount: number}} state - Mutable request state for one item.
     * @returns {boolean} True when there are no pending requests.
     */
    function shouldApplyServerResponse(state) {
        return state.pendingCount === 0;
    }

    /**
     * Reset state when a direct set action establishes a new baseline.
     *
     * Leaves one pending request to represent the active set operation.
     *
     * @param {{nextSeq: number, lastAppliedSeq: number, pendingCount: number}} state - Mutable request state for one item.
     * @returns {void}
     */
    function resetStateForSet(state) {
        state.nextSeq = 1;
        state.lastAppliedSeq = 0;
        state.pendingCount = 1;
    }

    /**
     * Public API for quantity and request-state logic.
     *
     * @type {{
     *  decimalPlaces: number,
     *  getStepSize: (quantityUnit: string) => number,
     *  calculateOptimisticQuantity: (currentQuantity: number, action: string, quantityUnit: string) => number,
     *  formatQuantity: (quantity: number, quantityUnit: string, unitNameMap?: Object<string, string>) => string,
     *  createPendingState: () => {nextSeq: number, lastAppliedSeq: number, pendingCount: number},
     *  recordRequest: (state: {nextSeq: number, lastAppliedSeq: number, pendingCount: number}) => number,
    *  resolveRequest: (state: {nextSeq: number, lastAppliedSeq: number, pendingCount: number}, requestSeq: number) => {shouldApply: boolean},
     *  shouldApplyServerResponse: (state: {nextSeq: number, lastAppliedSeq: number, pendingCount: number}) => boolean,
     *  resetStateForSet: (state: {nextSeq: number, lastAppliedSeq: number, pendingCount: number}) => void
     * }}
     */
    const api = {
        decimalPlaces,
        getStepSize,
        calculateOptimisticQuantity,
        formatQuantity,
        createPendingState,
        recordRequest,
        resolveRequest,
        shouldApplyServerResponse,
        resetStateForSet,
    };

    globalScope[LOGIC_API_NAME] = api;

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    }
})(typeof window !== 'undefined' ? window : globalThis);
