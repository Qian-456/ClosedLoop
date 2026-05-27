import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'

import MarkdownText from '../MarkdownText'

describe('MarkdownText', () => {
  it('支持加粗语法', () => {
    const { container } = render(<MarkdownText text="**需求总结：**\n\n- A" />)

    expect(container.textContent).toContain('需求总结：')
    expect(container.textContent).not.toContain('**')
    expect(container.querySelector('strong')?.textContent).toBe('需求总结：')
  })

  it('支持列表语法', () => {
    const { container } = render(<MarkdownText text="- A\n\n- B\n" />)

    expect(container.querySelector('ul')).toBeTruthy()
    expect(container.textContent).toContain('A')
    expect(container.textContent).toContain('B')
  })

  it('支持代码块语法', () => {
    const { container } = render(
      <MarkdownText text={'```js\nconsole.log("ok")\n```'} />,
    )

    expect(container.querySelector('pre code')?.textContent).toContain('console.log("ok")')
  })
})
