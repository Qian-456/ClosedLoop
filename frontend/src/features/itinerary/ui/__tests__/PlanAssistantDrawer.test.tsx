import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

let lastDrawerProps: any = null
let PlanAssistantDrawer: any = null

vi.mock('../../../../shared/ui/BottomDrawer', () => {
  return {
    default: (props: any) => {
      lastDrawerProps = props
      return (
        <div data-testid="drawer">
          <div data-testid="header">{props.header}</div>
          <div data-testid="body">{props.children}</div>
        </div>
      )
    },
  }
})

describe('PlanAssistantDrawer', () => {
  beforeEach(async () => {
    lastDrawerProps = null
    PlanAssistantDrawer = (await import('../PlanAssistantDrawer')).default
  })

  it('plans 模式折叠高度保持不变', async () => {
    const user = userEvent.setup()
    render(<PlanAssistantDrawer variant="plans" />)

    expect(lastDrawerProps?.collapsedHeight).toBe(184)

    await user.click(screen.getByLabelText('打开输入框'))
    expect(lastDrawerProps?.collapsedHeight).toBe(184)
  })

  it('plans 模式输入框字号不小于 16px', async () => {
    const user = userEvent.setup()
    render(<PlanAssistantDrawer variant="plans" />)

    await user.click(screen.getByLabelText('打开输入框'))
    expect(screen.getByLabelText('输入你的想法')).toHaveClass('text-base')
  })
})
