document.addEventListener("DOMContentLoaded", function () {
  var dialog = document.getElementById("product-preview-dialog");
  var image = document.getElementById("product-preview-full-image");
  var heading = document.getElementById("product-preview-title");
  var original = document.getElementById("product-preview-open-original");
  if (!dialog || !image || !heading || !original) return;
  var lastTrigger = null;
  function closePreview() {
    if (typeof dialog.close === "function" && dialog.open) dialog.close();
    else dialog.removeAttribute("open");
  }
  document.querySelectorAll("[data-product-preview]").forEach(function (button) {
    button.addEventListener("click", function () {
      var src = button.getAttribute("data-preview-src");
      var title = button.getAttribute("data-preview-title") || "Actual ParentWise product page";
      if (!src || !src.startsWith("assets/")) return;
      lastTrigger = button;
      image.src = src;
      image.alt = title;
      heading.textContent = title;
      original.href = src;
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");
    });
  });
  dialog.querySelectorAll("[data-close-product-preview]").forEach(function (button) {
    button.addEventListener("click", closePreview);
  });
  dialog.addEventListener("click", function (event) {
    if (event.target === dialog) closePreview();
  });
  dialog.addEventListener("close", function () {
    image.removeAttribute("src");
    if (lastTrigger) lastTrigger.focus();
  });
});
