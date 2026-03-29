import { defineConfig } from 'orval';

export default defineConfig({
  gilbertus: {
    input: {
      target: './openapi.json',
    },
    output: {
      target: './src/gilbertus.ts',
      client: 'react-query',
      mode: 'single',
      override: {
        mutator: {
          path: './src/base.ts',
          name: 'customFetch',
        },
      },
    },
  },
});
