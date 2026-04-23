/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/renderer/**/*.{ts,tsx,html}', './src/mobile/**/*.{ts,tsx,html}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        ds: {
          bg: 'var(--ds-bg)',
          surface: 'var(--ds-surface)',
          'surface-elevated': 'var(--ds-surface-elevated)',
          border: 'var(--ds-border)',
          'border-strong': 'var(--ds-border-strong)',
          text: 'var(--ds-text)',
          muted: 'var(--ds-muted)',
          accent: 'var(--ds-accent)',
          'accent-hover': 'var(--ds-accent-hover)',
          'accent-contrast': 'var(--ds-accent-contrast)',
          success: 'var(--ds-success)',
          warning: 'var(--ds-warning)',
          error: 'var(--ds-error)',
          info: 'var(--ds-info)',
        },
      },
      spacing: {
        'ds-0': 'var(--ds-space-0)',
        'ds-1': 'var(--ds-space-1)',
        'ds-2': 'var(--ds-space-2)',
        'ds-3': 'var(--ds-space-3)',
        'ds-4': 'var(--ds-space-4)',
        'ds-5': 'var(--ds-space-5)',
        'ds-6': 'var(--ds-space-6)',
        'ds-8': 'var(--ds-space-8)',
        'ds-10': 'var(--ds-space-10)',
        'ds-12': 'var(--ds-space-12)',
        'ds-16': 'var(--ds-space-16)',
      },
      fontFamily: {
        sans: ['var(--ds-font-family-sans)'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      fontSize: {
        'ds-2xs': ['var(--ds-font-size-2xs)', { lineHeight: '1.4' }],
        'ds-xs': ['var(--ds-font-size-xs)', { lineHeight: '1.4' }],
        'ds-sm': ['var(--ds-font-size-sm)', { lineHeight: '1.5' }],
        'ds-md': ['var(--ds-font-size-md)', { lineHeight: '1.6' }],
        'ds-lg': ['var(--ds-font-size-lg)', { lineHeight: '1.4' }],
        'ds-xl': ['var(--ds-font-size-xl)', { lineHeight: '1.3' }],
      },
      width: {
        'ds-popover': 'min(22rem, calc(100vw - 2rem))',
      },
      maxWidth: {
        'ds-tooltip': '18rem',
        'ds-toast': '22rem',
      },
      borderRadius: {
        'ds-sm': 'var(--ds-radius-sm)',
        'ds-md': 'var(--ds-radius-md)',
        'ds-lg': 'var(--ds-radius-lg)',
        'ds-xl': 'var(--ds-radius-xl)',
        'ds-pill': 'var(--ds-radius-pill)',
      },
      boxShadow: {
        'ds-sm': 'var(--ds-shadow-sm)',
        'ds-md': 'var(--ds-shadow-md)',
        'ds-lg': 'var(--ds-shadow-lg)',
      },
      transitionDuration: {
        'ds-fast': 'var(--ds-motion-fast)',
        'ds-normal': 'var(--ds-motion-normal)',
        'ds-slow': 'var(--ds-motion-slow)',
      },
      transitionTimingFunction: {
        'ds-standard': 'var(--ds-ease-standard)',
        'ds-emphasized': 'var(--ds-ease-emphasized)',
      },
    },
  },
  plugins: [],
};
