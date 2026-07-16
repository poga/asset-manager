import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BatchTagBar from '../src/components/BatchTagBar.vue'

describe('BatchTagBar', () => {
  it('shows the selection count', () => {
    const w = mount(BatchTagBar, { props: { count: 3, unionTags: [] } })
    expect(w.find('.batch-count').text()).toContain('3')
  })

  it('emits add with the trimmed tag then clears the input', async () => {
    const w = mount(BatchTagBar, { props: { count: 2, unionTags: [] } })
    const input = w.find('.batch-add-input')
    await input.setValue('  dungeon ')
    await input.trigger('keyup.enter')
    expect(w.emitted('add')[0]).toEqual(['dungeon'])
    expect(input.element.value).toBe('')
  })

  it('does not emit add for a blank tag', async () => {
    const w = mount(BatchTagBar, { props: { count: 1, unionTags: [] } })
    const input = w.find('.batch-add-input')
    await input.setValue('   ')
    await input.trigger('keyup.enter')
    expect(w.emitted('add')).toBeUndefined()
  })

  it('emits remove when a union chip × is clicked', async () => {
    const w = mount(BatchTagBar, { props: { count: 2, unionTags: ['2d', 'wip'] } })
    await w.findAll('.batch-chip-remove')[1].trigger('click')
    expect(w.emitted('remove')[0]).toEqual(['wip'])
  })

  it('emits clear', async () => {
    const w = mount(BatchTagBar, { props: { count: 1, unionTags: [] } })
    await w.find('.batch-clear').trigger('click')
    expect(w.emitted('clear')).toBeTruthy()
  })
})
