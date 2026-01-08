/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx,js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f4f5fb',
          100: '#e9ebf6',
          200: '#ccd3ed',
          300: '#a8b3e0',
          400: '#7a89d0',
          500: '#5667c0',
          600: '#3f4fa9',
          700: '#34418a',
          800: '#2e3972',
          900: '#28325e'
        }
      }
    },
  },
  plugins: [require('@tailwindcss/typography')],
}
