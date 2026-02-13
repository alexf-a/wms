const logic = require('./quantity_logic');

describe('getStepSize', () => {
    test('returns 1 for count unit', () => {
        expect(logic.getStepSize('count')).toBe(1);
    });

    test('returns 0.1 for non-count units', () => {
        expect(logic.getStepSize('kg')).toBe(0.1);
        expect(logic.getStepSize('mL')).toBe(0.1);
    });
});

describe('calculateOptimisticQuantity', () => {
    test('increments count by 1', () => {
        expect(logic.calculateOptimisticQuantity(10, 'increment', 'count')).toBe(11);
    });

    test('increments decimal unit by 0.1', () => {
        expect(logic.calculateOptimisticQuantity(2.5, 'increment', 'kg')).toBe(2.6);
    });

    test('decrements count by 1', () => {
        expect(logic.calculateOptimisticQuantity(10, 'decrement', 'count')).toBe(9);
    });

    test('decrements decimal unit by 0.1', () => {
        expect(logic.calculateOptimisticQuantity(2.5, 'decrement', 'kg')).toBe(2.4);
    });

    test('clamps quantity at zero', () => {
        expect(logic.calculateOptimisticQuantity(0, 'decrement', 'count')).toBe(0);
    });

    test('rounds decimal quantity to one decimal place', () => {
        expect(logic.calculateOptimisticQuantity(0.2, 'increment', 'kg')).toBe(0.3);
    });

    test('handles high decimal quantities without drift', () => {
        expect(logic.calculateOptimisticQuantity(999.9, 'increment', 'kg')).toBe(1000.0);
    });
});

describe('formatQuantity', () => {
    const unitMap = {
        count: 'Count',
        kg: 'Kilograms',
    };

    test('formats count as integer', () => {
        expect(logic.formatQuantity(5, 'count', unitMap)).toBe('5 count');
    });

    test('formats decimal units with mapped display name', () => {
        expect(logic.formatQuantity(2.5, 'kg', unitMap)).toBe('2.5 kilograms');
    });

    test('falls back to raw unit when not in mapping', () => {
        expect(logic.formatQuantity(1.1, 'unknown', unitMap)).toBe('1.1 unknown');
    });

    test('formats zero correctly', () => {
        expect(logic.formatQuantity(0, 'count', unitMap)).toBe('0 count');
    });
});

describe('pending state transitions', () => {
    test('createPendingState returns expected defaults', () => {
        expect(logic.createPendingState()).toEqual({
            nextSeq: 1,
            lastAppliedSeq: 0,
            pendingCount: 0,
        });
    });

    test('recordRequest increments sequence and pending count', () => {
        const state = logic.createPendingState();
        const seq = logic.recordRequest(state);
        expect(seq).toBe(1);
        expect(state.nextSeq).toBe(2);
        expect(state.pendingCount).toBe(1);
    });

    test('single request resolves and should apply response', () => {
        const state = logic.createPendingState();
        const seq = logic.recordRequest(state);
        const result = logic.resolveRequest(state, seq);
        expect(result.shouldApply).toBe(true);
        expect(state.pendingCount).toBe(0);
        expect(state.lastAppliedSeq).toBe(1);
    });

    test('multi-request resolves only apply on last response', () => {
        const state = logic.createPendingState();
        const seq1 = logic.recordRequest(state);
        const seq2 = logic.recordRequest(state);
        const seq3 = logic.recordRequest(state);

        expect(logic.resolveRequest(state, seq1).shouldApply).toBe(false);
        expect(logic.resolveRequest(state, seq2).shouldApply).toBe(false);
        expect(logic.resolveRequest(state, seq3).shouldApply).toBe(true);
        expect(state.pendingCount).toBe(0);
        expect(state.lastAppliedSeq).toBe(3);
    });

    test('long-press style 10 requests applies only on final resolve', () => {
        const state = logic.createPendingState();
        const seqs = [];

        for (let index = 0; index < 10; index += 1) {
            seqs.push(logic.recordRequest(state));
        }

        for (let index = 0; index < 9; index += 1) {
            expect(logic.resolveRequest(state, seqs[index]).shouldApply).toBe(false);
        }
        expect(logic.resolveRequest(state, seqs[9]).shouldApply).toBe(true);
        expect(state.pendingCount).toBe(0);
    });

    test('shouldApplyServerResponse reflects pending count', () => {
        const state = logic.createPendingState();
        expect(logic.shouldApplyServerResponse(state)).toBe(true);
        logic.recordRequest(state);
        expect(logic.shouldApplyServerResponse(state)).toBe(false);
    });

    test('resetStateForSet resets sequence baseline', () => {
        const state = logic.createPendingState();
        logic.recordRequest(state);
        logic.recordRequest(state);
        logic.resetStateForSet(state);
        expect(state).toEqual({
            nextSeq: 1,
            lastAppliedSeq: 0,
            pendingCount: 1,
        });
    });
});
