// Flat config (ESLint v9+). Activated when ESLint is installed.
// Until then, the standalone scripts/lint-arch.mjs is the primary
// Clean Architecture enforcement (see ADR-0006).
//
// To activate locally:
//   npm install --save-dev eslint @typescript-eslint/parser
//   npx eslint src/renderer

const layerForbidImports = {
  domain: [
    'react',
    'react-dom',
    'zustand',
    'axios',
    '*/infrastructure/*',
    '*/components/*',
    '*/hooks/*',
    '*/stores/*',
    '*/application/*',
  ],
  application: [
    'react',
    'react-dom',
    '*/infrastructure/*',
    '*/components/*',
    '*/hooks/*',
  ],
  components: ['*/infrastructure/*'],
};

function noRestrictedImports(patterns) {
  return [
    'error',
    {
      patterns: patterns.map((p) => ({
        group: [p],
        message: `Clean Architecture violation — see scripts/lint-arch.mjs and ADR-0006`,
      })),
    },
  ];
}

export default [
  {
    files: ['src/renderer/domain/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': noRestrictedImports(layerForbidImports.domain),
    },
  },
  {
    files: ['src/renderer/application/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': noRestrictedImports(layerForbidImports.application),
    },
  },
  {
    files: ['src/renderer/components/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': noRestrictedImports(layerForbidImports.components),
    },
  },
];
