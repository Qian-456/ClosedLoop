import { describe, expect, it } from 'vitest'
import { formatMoney, formatMoneyExact } from '../format'

describe('formatMoney', () => {
  it('四舍五入到元', () => {
    expect(formatMoney(1.2)).toBe('¥1')
    expect(formatMoney(1.6)).toBe('¥2')
  })
})

describe('formatMoneyExact', () => {
  it('精确到分', () => {
    expect(formatMoneyExact(10)).toBe('¥10.00')
    expect(formatMoneyExact(10.1)).toBe('¥10.10')
    expect(formatMoneyExact(10.666)).toBe('¥10.67')
  })
})

