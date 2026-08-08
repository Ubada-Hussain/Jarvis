/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        jarvis: {
          bg: '#07070b',
          panel: '#0c0c14',
          crimson: '#ff3b4e',
          'crimson-dim': '#7a1622',
          cyan: '#2dd4ea',
          amber: '#f5a623',
          text: '#ece9f2',
          'text-dim': '#837f92',
          'panel-border': 'rgba(230,57,70,0.28)'
        }
      },
      fontFamily: {
        mono: ['"IBM Plex Mono"', 'monospace'],
        display: ['"Space Grotesk"', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
