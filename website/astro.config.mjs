import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://skiller.run',
  base: '/',
  output: 'static',
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
          label: 'Demos',
          items: [{ autogenerate: { directory: 'docs/demos' } }],
        },
        {
          label: 'Getting started',
          items: [{ autogenerate: { directory: 'docs/getting-started' } }],
        },
        {
          label: 'Concepts',
          items: [{ autogenerate: { directory: 'docs/concepts' } }],
        },
        {
          label: 'Guides',
          items: [{ autogenerate: { directory: 'docs/guides' } }],
        },
        {
          label: 'Reference',
          items: [{ autogenerate: { directory: 'docs/reference' } }],
        },
        {
          label: 'Development',
          items: [{ autogenerate: { directory: 'docs/development' } }],
        },
      ],
    }),
  ],
});
