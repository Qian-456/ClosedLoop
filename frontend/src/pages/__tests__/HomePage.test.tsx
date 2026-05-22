import { describe, expect, it, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import HomePage from '../HomePage'
import { useItineraryStore } from '../../features/itinerary/store/useItineraryStore'

function renderWithRouter() {
  const router = createMemoryRouter(
    [
      { path: '/app', element: <HomePage /> },
      { path: '/app/generating', element: <div>generating</div> },
    ],
    { initialEntries: ['/app'] },
  )
  return render(<RouterProvider router={router} />)
}

describe('HomePage', () => {
  beforeEach(() => {
    useItineraryStore.getState().reset()
  })

  it('输入框高度与字号固定', () => {
    renderWithRouter()
    const textarea = screen.getByPlaceholderText(/例如：今天下午/)
    expect(textarea).toHaveClass('h-[120px]')
    expect(textarea).toHaveClass('text-base')
  })

  it('渲染左上角多会话按钮', () => {
    renderWithRouter()
    expect(screen.getByLabelText('多会话')).toBeInTheDocument()
  })

  it('点击发送后写入 store 并进入 generating', async () => {
    const user = userEvent.setup()

    renderWithRouter()

    await user.type(
      screen.getByPlaceholderText(/例如：今天下午/),
      '今天下午想出去玩 6 小时',
    )
    await user.click(screen.getByLabelText('发送'))

    const s = useItineraryStore.getState()
    expect(s.userInput).toContain('今天下午')
    expect(s.sessionId).toBeTruthy()
    expect(await screen.findByText('generating')).toBeInTheDocument()
  })
})
