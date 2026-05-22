import { describe, expect, it } from 'vitest'
import { buildApiUrl } from '../url'

describe('buildApiUrl', () => {
  it('base 为空时返回规范化路径', () => {
    expect(buildApiUrl('/execute/start', '')).toBe('/execute/start')
    expect(buildApiUrl('execute/start', '')).toBe('/execute/start')
  })

  it('base 含尾部斜杠时不会产生双斜杠', () => {
    expect(buildApiUrl('/execute/events/exe_1', 'http://localhost:8000/')).toBe(
      'http://localhost:8000/execute/events/exe_1',
    )
    expect(buildApiUrl('/execute/events/exe_1', '/api/')).toBe('/api/execute/events/exe_1')
  })

  it('base 含路径前缀时保持前缀语义', () => {
    expect(buildApiUrl('/invoke', 'http://localhost:8000/api')).toBe('http://localhost:8000/api/invoke')
    expect(buildApiUrl('/invoke', '/api')).toBe('/api/invoke')
  })
})

