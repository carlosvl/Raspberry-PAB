/** Visual press feedback for buttons and button-like controls on touch kiosks. */
(function registerButtonPressFeedback() {
  const PRESS_SELECTOR =
    "button, .admin__link, .admin__nav a, .control-menu__button, .alert__button";
  const PRESS_HOLD_MS = 150;

  function clearPressed() {
    document.querySelectorAll(`${PRESS_SELECTOR}.is-pressed`).forEach((target) => {
      window.setTimeout(() => target.classList.remove("is-pressed"), PRESS_HOLD_MS);
    });
  }

  document.addEventListener(
    "pointerdown",
    (event) => {
      const target = event.target.closest(PRESS_SELECTOR);
      if (!target || target.disabled) return;
      target.classList.add("is-pressed");
    },
    { passive: true },
  );

  document.addEventListener("pointerup", clearPressed, { passive: true });
  document.addEventListener("pointercancel", clearPressed, { passive: true });
})();
