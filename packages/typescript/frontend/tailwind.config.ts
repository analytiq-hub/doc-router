import type { Config } from "tailwindcss";

import { brandPalette } from "./src/styles/brandPalette";

const secondary = "hsla(190, 81%, 42%, 1)";

const config: Config = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      screens: {
        xs: "480px",
      },
      colors: {
        primary: {
          ...brandPalette,
          DEFAULT: brandPalette[600],
        },
        secondary: {
          DEFAULT: secondary,
          50: "hsla(190, 81%, 90%, 1)",
          100: "hsla(190, 81%, 82%, 1)",
          200: "hsla(190, 81%, 74%, 1)",
          300: "hsla(190, 81%, 66%, 1)",
          400: "hsla(190, 81%, 58%, 1)",
          500: "hsla(190, 81%, 50%, 1)",
          600: secondary,
          700: "hsla(190, 81%, 34%, 1)",
          800: "hsla(190, 81%, 28%, 1)",
          900: "hsla(190, 81%, 20%, 1)"
        },
        "gray-darker": "#504747"
      },
      spacing: {
        7.5: "1.875rem", // 30px
        15: "3.75rem", // 60px
        22: "5.5rem", // 88px
        25: "6.25rem", // 100px
        26: "6.5rem", // 104px
        30: "8.5rem", // 136px
        32: "9rem", // 144px
        68: "17rem" // 272px
      },
      padding: {
        px: "1px"
      },
      margin: {
        px: "1px",
        "-px": "-1px",
        "-2px": "-2px",
        auto: "auto"
      },
      fontSize: {
        micro: ".5rem", // 8px
        xxs: ".625rem", // 10px
        md: "1.125rem" // 18px
      },
      fontWeight: {
        hairline: "100"
      },
      fontFamily: {
        brand: ["Source Sans Pro", "sans-serif"],
        sans: ["Source Sans Pro", "sans-serif"],
        serif: ["Source Sans Pro", "sans-serif"],
        inconsolata: ["Inconsolata"],
        source: ["source-code-pro", "Menlo", "Monaco", "Consolas", "Courier New", "monospace"]
      },
      minWidth: {
        site: "18.75rem",
        "input-mini": "17.5rem",
        "input-small": "31.25rem",
        "input-medium": "36.3125rem",
        "input-large": "61.45rem",
        "button-mini": "5.5rem",
        "button-small": "7rem",
        "button-medium": "9.875rem",
        "button-large": "10rem"
      },
      width: {
        arrow: ".8rem",
        "3/10": "30%",
        "7/10": "70%",
        "9/10": "90%",
        "12/25": "48%"
      },
      maxWidth: {
        sm: "30rem",
        md: "40rem",
        lg: "50rem",
        xl: "60rem",
        "2xl": "70rem",
        "3xl": "80rem",
        "4xl": "90rem",
        "5xl": "100rem",
        "1/4": "25%",
        "1/2": "50%",
        "3/5": "60%",
        "4/5": "80%",
        "9/10": "90%",
        "site-mini": "17.5rem",
        "site-small": "31.25rem",
        "site-medium": "43.75rem",
        "site-large": "56.25rem",
        site: "73.75rem",
        screen: "100vw"
      },
      height: {
        arrow: ".4rem",
        px: "1px",
        4: "1rem",
        5: "1.25rem",
        8: "1.8rem",
        9: "2.25rem",
        10: "2.5rem",
        11: "2.75rem",
        12: "3rem",
        16: "4rem",
        24: "6rem",
        32: "8rem"
      },
      borderWidth: {
        1: "1px",
        5: "5px"
      },
      borderRadius: {
        half: "50%",
        full: "100%"
      },
      zIndex: {
        1: "1",
        2: "2",
        3: "3",
        4: "4",
        5: "5",
        6: "6"
      },
      fill: {
        transparent: "transparent"
      },
      flex: {
        2: "2 2 0%",
        3: "3 3 0%"
      }
    },
    outline: {
      none: ["2px solid transparent", "2px"],
      white: ["2px dotted white", "2px"],
      black: ["2px dotted black", "2px"]
    }
  },
  plugins: [],
};
export default config;
