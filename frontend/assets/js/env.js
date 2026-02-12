window.env = {
  API_BASE_URL: window.location.hostname === "localhost"
    ? "http://localhost:8000/api/v1"
    : "https://quickdash-front-back.onrender.com/api/v1"
};
