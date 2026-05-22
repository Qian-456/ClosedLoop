import { describe, expect, it } from 'vitest'
import { getGreeting } from '../greeting'

describe('getGreeting', () => {
  it('早上好', () => {
    expect(getGreeting(new Date(2024, 0, 1, 6, 0, 0))).toBe('早上好')
  })

  it('中午好', () => {
    expect(getGreeting(new Date(2024, 0, 1, 12, 0, 0))).toBe('中午好')
  })

  it('下午好', () => {
    expect(getGreeting(new Date(2024, 0, 1, 15, 0, 0))).toBe('下午好')
  })

  it('晚上好', () => {
    expect(getGreeting(new Date(2024, 0, 1, 21, 0, 0))).toBe('晚上好')
  })
})

