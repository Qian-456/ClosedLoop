import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import { useItineraryStore } from '../../features/itinerary/store/useItineraryStore'
import HomePage from '../HomePage'

describe('HomePage demo prompts', () => {
  beforeEach(() => {
    localStorage.clear()
    useItineraryStore.persist.clearStorage()
    useItineraryStore.setState({
      sessions: [],
      currentSessionId: null,
      userInput: '',
      invokeStatus: 'idle',
      errorMessage: null,
    })
  })

  it('一家三口示例预算为 500', () => {
    render(<HomePage />)

    fireEvent.click(screen.getByText('一家三口'))
    expect(screen.getByDisplayValue(/预算 500 元以内/)).toBeInTheDocument()
  })

  it('首页输入框 placeholder 不变', () => {
    render(<HomePage />)

    const input = screen.getByRole('textbox')
    expect(input).toHaveAttribute(
      'placeholder',
      '例如：今天下午一家三口想出去玩 6 小时，预算 350 以内',
    )
  })
})
