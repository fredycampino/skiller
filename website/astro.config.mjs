import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://skiller.run',
  base: '/',
  output: 'static',
  redirects: {
    '/docs/': '/docs/getting-started/installation/',
  },
  integrations: [
    starlight({
      title: 'skiller.run',
      disable404Route: true,
      social: [
        {
          icon: 'github',
          label: 'GitHub',
          href: 'https://github.com/fredycampino/skiller',
        },
      ],
      customCss: ['./src/styles/starlight.css'],
      sidebar: [
        {
          label: 'Getting started',
          items: [
            { label: 'Installation', slug: 'docs/getting-started/installation' },
            { label: 'Add an LLM provider', slug: 'docs/getting-started/add-an-llm-provider' },
            { label: 'Your first agent', slug: 'docs/getting-started/your-first-agent' },
          ],
        },
        {
          label: 'Demos',
          items: [
            { label: 'Create a custom agent', slug: 'docs/demos/custom-agent' },
            { label: 'Automate a pull request', slug: 'docs/demos/automate-a-pull-request' },
            { label: 'Trigger an agent with a webhook', slug: 'docs/demos/agent-webhook' },
          ],
        },
      ],
    }),
  ],
});
