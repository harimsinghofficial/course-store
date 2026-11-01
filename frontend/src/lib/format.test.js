import { describe, expect, it } from 'vitest';
import { EMAIL_RE, inr, pad2, splitDuration } from './format.js';

describe('inr', () => {
  it('formats with Indian digit grouping', () => {
    expect(inr(0)).toBe('₹0');
    expect(inr(79900)).toBe('₹799');
    expect(inr(799900)).toBe('₹7,999');
    expect(inr(1499900)).toBe('₹14,999');
    expect(inr(12345600)).toBe('₹1,23,456');
    expect(inr(1234567800)).toBe('₹1,23,45,678');
  });
  it('shows paise only when present', () => {
    expect(inr(12345678)).toBe('₹1,23,456.78');
    expect(inr(100)).toBe('₹1');
    expect(inr(105)).toBe('₹1.05');
  });
  it('is safe with junk input', () => {
    expect(inr(undefined)).toBe('₹0');
    expect(inr('abc')).toBe('₹0');
    expect(inr(-500)).toBe('₹0');
  });
});

describe('helpers', () => {
  it('validates simple emails', () => {
    expect(EMAIL_RE.test('asha@example.com')).toBe(true);
    expect(EMAIL_RE.test('not-an-email')).toBe(false);
  });
  it('pads and splits durations', () => {
    expect(pad2(7)).toBe('07');
    expect(pad2(12)).toBe('12');
    expect(splitDuration(90061000)).toEqual({ d: 1, h: 1, m: 1, s: 1 });
    expect(splitDuration(-5)).toEqual({ d: 0, h: 0, m: 0, s: 0 });
  });
});
