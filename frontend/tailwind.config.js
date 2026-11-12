/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        field: { 50: "#f3f7ee", 100: "#e3edd7", 200: "#c5dbae", 500: "#4a7c3a", 600: "#3b6a2c", 700: "#2f5d1e", 800: "#244816", 900: "#17300d" },
        soil: { 50: "#faf6ef", 100: "#f1e7d4", 300: "#d6b98a", 500: "#9a7440", 700: "#6b4f2a", 900: "#3b2a14" },
        wheat: { 100: "#fbf0cf", 300: "#f1d27a", 500: "#d9a521" },
      },
      fontSize: { base: ["1.0625rem", "1.6rem"] },
    },
  },
  plugins: [],
};
