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
        {
          label: 'Runtime',
          items: [
            { label: 'Runtime configuration', slug: 'docs/configuration/runtime' },
          ],
        },
        {
          label: 'LLM providers',
          items: [
            { label: 'Supported LLM APIs', slug: 'docs/configuration/supported-llm-apis' },
            { label: 'User LLM providers', slug: 'docs/configuration/llm-providers' },
            { label: 'OpenAI adapter', slug: 'docs/configuration/openai-adapter' },
            { label: 'Codex adapter', slug: 'docs/configuration/codex-adapter' },
            { label: 'Bedrock adapter', slug: 'docs/configuration/bedrock-adapter' },
            { label: 'Custom providers', slug: 'docs/configuration/custom-llm-providers' },
          ],
        },
        {
          label: 'Agent harness',
          items: [
            { label: 'Global agent configuration', slug: 'docs/configuration/global-agent' },
            { label: 'Agent profiles', slug: 'docs/configuration/agent-profiles' },
            { label: 'Model selection', slug: 'docs/configuration/model-selection' },
            { label: 'Harness loop limits', slug: 'docs/configuration/harness-loop-limits' },
            { label: 'Context settings', slug: 'docs/configuration/context-settings' },
            { label: 'Event output', slug: 'docs/configuration/event-output' },
            { label: 'Debug settings', slug: 'docs/configuration/debug-settings' },
          ],
        },
        {
          label: 'Harness tools',
          items: [
            { label: 'Overview', slug: 'docs/tools/overview' },
            { label: 'Shell', slug: 'docs/tools/shell' },
            { label: 'Files', slug: 'docs/tools/files' },
          ],
        },
      ],
    }),
  ],
});
