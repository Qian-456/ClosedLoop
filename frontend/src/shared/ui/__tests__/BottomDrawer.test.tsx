import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import BottomDrawer from '../BottomDrawer'

describe('BottomDrawer', () => {
  it('外层不拦截抽屉之外的点击', () => {
    const { container } = render(
      <BottomDrawer header={<div>header</div>}>
        <div>body</div>
      </BottomDrawer>,
    )

    const root = container.querySelector('div.fixed')
    expect(root).toBeTruthy()
    expect(root).toHaveClass('pointer-events-none')

    const panel = root?.firstElementChild
    expect(panel).toBeTruthy()
    expect(panel).toHaveClass('pointer-events-auto')
  })
})

