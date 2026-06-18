import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import AnalysisCard from '../AnalysisCard.vue'

// Stub element-plus icons as simple components
const stubIcon = { template: '<span />' }

beforeEach(() => {
  vi.clearAllMocks()
})

function mountCard(props: Record<string, any> = {}, options: Record<string, any> = {}) {
  return mount(AnalysisCard, {
    props: {
      cardId: 1,
      title: 'Test Card',
      questions: [],
      ...props
    },
    global: {
      stubs: {
        SettingsMenu: {
          template: '<div class="settings-stub"><button class="settings-trigger" @click="$emit(\'command\', \'delete-card\')">settings</button></div>',
          emits: ['command']
        },
        ElIcon: stubIcon,
        ElInput: {
          template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" @keyup.enter="$emit(\'keyup.enter\')" @keyup.escape="$emit(\'keyup.escape\')" @blur="$emit(\'blur\')" />',
          props: ['modelValue', 'size', 'type', 'placeholder', 'autosize'],
          emits: ['update:modelValue', 'keyup.enter', 'keyup.escape', 'blur']
        },
        ElButton: {
          template: '<button @click="$emit(\'click\')"><slot /></button>',
          props: ['size', 'type', 'loading', 'text'],
          emits: ['click']
        },
        ...options.global?.stubs
      }
    },
    ...options
  })
}

describe('AnalysisCard', () => {
  // ── Title rendering ─────────────────────────────────────
  it('renders card title', () => {
    const wrapper = mountCard({ title: 'My Questions' })

    expect(wrapper.find('.card-title').text()).toBe('My Questions')
  })

  it('renders different title', () => {
    const wrapper = mountCard({ title: 'Research Notes' })

    expect(wrapper.find('.card-title').text()).toBe('Research Notes')
  })

  // ── Question list ───────────────────────────────────────
  it('renders question list', () => {
    const questions = [
      { id: 1, question: 'What is RAG?' },
      { id: 2, question: 'How does retrieval work?' }
    ]
    const wrapper = mountCard({ questions })

    const items = wrapper.findAll('.card-question')
    expect(items).toHaveLength(2)
    expect(items[0].find('.question-text').text()).toBe('What is RAG?')
    expect(items[1].find('.question-text').text()).toBe('How does retrieval work?')
  })

  it('shows empty state when no questions', () => {
    const wrapper = mountCard({ questions: [] })

    expect(wrapper.find('.card-empty').exists()).toBe(true)
    expect(wrapper.find('.card-empty').text()).toBe('暂无问题')
  })

  it('displays question count in header', () => {
    const questions = [
      { id: 1, question: 'Q1' },
      { id: 2, question: 'Q2' },
      { id: 3, question: 'Q3' }
    ]
    const wrapper = mountCard({ questions })

    expect(wrapper.find('.card-count').text()).toBe('3 个问题')
  })

  // ── Settings button ─────────────────────────────────────
  it('shows settings button via SettingsMenu stub', () => {
    const wrapper = mountCard()

    expect(wrapper.find('.settings-stub').exists()).toBe(true)
  })

  // ── Collapse/Expand ─────────────────────────────────────
  it('card body is visible by default (expanded)', () => {
    const wrapper = mountCard({ questions: [{ id: 1, question: 'Q1' }] })

    expect(wrapper.find('.card-body').exists()).toBe(true)
  })

  it('collapses card body when header is clicked', async () => {
    const wrapper = mountCard({ questions: [{ id: 1, question: 'Q1' }] })

    expect(wrapper.find('.card-body').exists()).toBe(true)

    await wrapper.find('.card-header').trigger('click')

    expect(wrapper.find('.card-body').exists()).toBe(false)
  })

  it('expands card body when header is clicked again', async () => {
    const wrapper = mountCard({ questions: [{ id: 1, question: 'Q1' }] })

    // Collapse
    await wrapper.find('.card-header').trigger('click')
    expect(wrapper.find('.card-body').exists()).toBe(false)

    // Expand
    await wrapper.find('.card-header').trigger('click')
    expect(wrapper.find('.card-body').exists()).toBe(true)
  })

  // ── Delete question emit ────────────────────────────────
  it('emits remove-question with question id when delete button clicked', async () => {
    const questions = [
      { id: 10, question: 'What is RAG?' },
      { id: 20, question: 'How does it work?' }
    ]
    const wrapper = mountCard({ questions })

    const deleteBtn = wrapper.findAll('.question-delete')[0]
    await deleteBtn.trigger('click')

    expect(wrapper.emitted('remove-question')).toBeTruthy()
    expect(wrapper.emitted('remove-question')![0]).toEqual([10])
  })

  it('emits remove-question for the correct question', async () => {
    const questions = [
      { id: 10, question: 'Q1' },
      { id: 20, question: 'Q2' },
      { id: 30, question: 'Q3' }
    ]
    const wrapper = mountCard({ questions })

    const deleteBtn = wrapper.findAll('.question-delete')[2]
    await deleteBtn.trigger('click')

    expect(wrapper.emitted('remove-question')![0]).toEqual([30])
  })

  // ── Summary ─────────────────────────────────────────────
  it('renders summary when provided', () => {
    const wrapper = mountCard({ summary: 'This is a summary of the questions' })

    expect(wrapper.find('.card-summary').exists()).toBe(true)
    expect(wrapper.find('.summary-text').text()).toBe('This is a summary of the questions')
  })

  it('does not render summary when not provided', () => {
    const wrapper = mountCard({ summary: undefined })

    expect(wrapper.find('.card-summary').exists()).toBe(false)
  })

  // ── Add question button ─────────────────────────────────
  it('shows add question button', () => {
    const wrapper = mountCard()

    expect(wrapper.find('.card-add-btn').exists()).toBe(true)
    expect(wrapper.find('.card-add-btn').text()).toContain('添加问题')
  })
})
