/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "Cascadia Code", "monospace"],
        sans: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      colors: {
        // Remap slate to Precision Terminal palette — all components inherit automatically
        slate: {
          50:  '#e8f0f5',
          100: '#d0e0ec',
          200: '#bfcfdf',
          300: '#a0b8c8',
          400: '#8090a0',
          500: '#5a7080',
          600: '#304050',
          700: '#253040',
          800: '#1c2535',
          900: '#111720',
          950: '#070a0e',
        },
        // Remap emerald to accent green
        emerald: {
          300: '#60ffcc',
          400: '#00dc96',
          500: '#00b87c',
          600: '#009060',
        },
        // Soften red to match design system
        red: {
          400: '#f04060',
          800: '#6a1525',
          950: '#180508',
        },
      },
      transitionDuration: { 180: '180ms' },
      boxShadow: {
        'accent-glow': '0 0 16px rgba(0, 220, 150, 0.3)',
        'accent-sm':   '0 0 8px rgba(0, 220, 150, 0.2)',
        'link-glow':   '0 0 12px rgba(58, 180, 245, 0.35)',
      },
    },
  },
  plugins: [],
}
