(function () {
  var root = document.documentElement;
  try {
    if (localStorage.getItem("fruitcam-theme") === "light") root.dataset.theme = "light";
    if (localStorage.getItem("fruitcam-motion") === "reduced") root.dataset.motion = "reduced";
  } catch (e) {}
  if (root.dataset.theme === "light") document.querySelector('meta[name="theme-color"]').setAttribute("content", "#f5f1e6");
})();
