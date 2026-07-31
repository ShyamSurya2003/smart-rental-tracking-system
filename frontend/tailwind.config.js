export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#17202a",
        steel: "#41515f",
        mint: "#0f9f8f",
        amber: "#d97706",
        danger: "#dc2626"
      },
      boxShadow: {
        panel: "0 10px 30px rgba(23, 32, 42, 0.08)"
      }
    }
  },
  plugins: []
};
