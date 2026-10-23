/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // A calm study palette: parchment (60%), warm surfaces (30%), and a
        // terracotta action color (10%). Keeping the existing utility names
        // lets every screen share the same accessible visual language.
        slate: {
          50: '#fffdf8',
          100: '#3f322c',
          200: '#4f4038',
          300: '#614d43',
          400: '#745f54',
          500: '#877166',
          600: '#a38a79',
          700: '#cdbca9',
          800: '#e7dccd',
          900: '#f5ede1',
          950: '#fbf6ee',
        },
        brand: {
          50: '#fff3eb',
          100: '#fee2d2',
          200: '#fac4a4',
          300: '#ee9c73',
          400: '#d8784e',
          500: '#b95c38',
          600: '#93452c',
          700: '#743721',
          800: '#5b2d1d',
          900: '#482519',
          950: '#321a11',
        },
      },
    },
  },
  plugins: [],
}
