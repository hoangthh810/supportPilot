import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AppLayout from '@/layouts/AppLayout.vue'

describe('AppLayout', () => {
  it('renders the neutral foundation shell', () => {
    const wrapper = mount(AppLayout, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
          RouterView: { template: '<main data-test="router-view" />' },
        },
      },
    })

    expect(wrapper.text()).toContain('SupportPilot')
    expect(wrapper.find('[data-test="router-view"]').exists()).toBe(true)
  })
})

