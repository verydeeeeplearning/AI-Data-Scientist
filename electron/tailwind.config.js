/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/renderer/**/*.{ts,tsx,html}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        ds: {
          bg: 'var(--ds-bg)',
          surface: 'var(--ds-surface)',
          border: 'var(--ds-border)',
          text: 'var(--ds-text)',
          muted: 'var(--ds-muted)',
          accent: 'var(--ds-accent)',
          'accent-hover': 'var(--ds-accent-hover)',
          success: 'var(--ds-success)',
          warning: 'var(--ds-warning)',
          error: 'var(--ds-error)',
        },
      },
      fontFamily: {
        sans: [
          'Inter',
          'Noto Sans KR',
          'Noto Sans JP',
          'system-ui',
          '-apple-system',
          'Segoe UI',
          'Roboto',
          'sans-serif',
        ],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
};
