/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "surface-container-lowest": "#0e0e12",
        "surface-container-highest": "#353439",
        "inverse-primary": "#bf002a",
        "surface-container": "#1f1f24",
        "on-tertiary-container": "#3c2500",
        "on-error-container": "#ffdad6",
        "secondary-container": "#00c5db",
        "outline": "#ac8887",
        "on-secondary": "#00363d",
        "secondary-fixed-dim": "#37d9ef",
        "background": "#131317",
        "on-secondary-fixed-variant": "#004f58",
        "tertiary": "#ffb955",
        "surface-tint": "#ffb3b2",
        "on-primary": "#680012",
        "secondary-fixed": "#9af0ff",
        "surface-container-low": "#1b1b20",
        "primary-fixed-dim": "#ffb3b2",
        "inverse-on-surface": "#303035",
        "secondary": "#44e2f8",
        "tertiary-fixed-dim": "#ffb955",
        "on-tertiary-fixed-variant": "#633f00",
        "on-secondary-fixed": "#001f24",
        "error": "#ffb4ab",
        "on-secondary-container": "#004d56",
        "tertiary-fixed": "#ffddb4",
        "on-primary-container": "#5b000f",
        "surface-variant": "#353439",
        "on-surface": "#e4e1e8",
        "on-error": "#690005",
        "surface": "#131317",
        "surface-dim": "#131317",
        "primary-container": "#ff525c",
        "on-surface-variant": "#e5bdbc",
        "surface-bright": "#39393e",
        "primary-fixed": "#ffdad8",
        "surface-container-high": "#2a292e",
        "tertiary-container": "#c68200",
        "on-tertiary": "#452b00",
        "on-background": "#e4e1e8",
        "outline-variant": "#5c3f3f",
        "on-primary-fixed": "#410008",
        "primary": "#ffb3b2",
        "on-primary-fixed-variant": "#92001e",
        "inverse-surface": "#e4e1e8",
        "error-container": "#93000a",
        "on-tertiary-fixed": "#291800",
        
        // Keep old jarvis colors just in case some old components still use them
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
      borderRadius: {
        "DEFAULT": "0.25rem",
        "lg": "0.5rem",
        "xl": "0.75rem",
        "full": "9999px"
      },
      spacing: {
        "margin-mobile": "16px",
        "container-max": "1440px",
        "margin-desktop": "40px",
        "gutter": "16px",
        "unit": "4px"
      },
      fontFamily: {
        "body-md": ["JetBrains Mono"],
        "headline-lg": ["Montserrat"],
        "display-lg": ["Montserrat"],
        "body-lg": ["JetBrains Mono"],
        "label-caps": ["JetBrains Mono"],
        "headline-md": ["Montserrat"],
        "terminal-sm": ["JetBrains Mono"],
        // Keep existing fonts as fallback
        "mono": ['"JetBrains Mono"', '"IBM Plex Mono"', 'monospace'],
        "display": ['"Montserrat"', '"Space Grotesk"', 'sans-serif'],
      },
      fontSize: {
        "body-md": ["14px", { "lineHeight": "1.6", "letterSpacing": "0px", "fontWeight": "400" }],
        "headline-lg": ["32px", { "lineHeight": "1.2", "letterSpacing": "0.05em", "fontWeight": "700" }],
        "display-lg": ["48px", { "lineHeight": "1.1", "letterSpacing": "0.1em", "fontWeight": "800" }],
        "body-lg": ["16px", { "lineHeight": "1.6", "letterSpacing": "0px", "fontWeight": "400" }],
        "label-caps": ["12px", { "lineHeight": "1", "letterSpacing": "0.15em", "fontWeight": "500" }],
        "headline-md": ["24px", { "lineHeight": "1.3", "letterSpacing": "0.05em", "fontWeight": "600" }],
        "terminal-sm": ["12px", { "lineHeight": "1.4", "fontWeight": "400" }]
      }
    },
  },
  plugins: [],
}
