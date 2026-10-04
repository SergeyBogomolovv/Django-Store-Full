const toastRegion = document.querySelector(".toast-region");

function dismissToast(toast) {
  toast.querySelector("button").addEventListener("click", () => toast.remove());
  setTimeout(() => toast.remove(), 7000);
}

document.querySelectorAll(".store-toast").forEach(dismissToast);

function showToast(message, error = false) {
  const toast = document.createElement("div");
  toast.className = "store-toast" + (error ? " error" : "");
  toast.setAttribute("role", "status");
  const text = document.createElement("span");
  text.textContent = message;
  const close = document.createElement("button");
  close.type = "button";
  close.textContent = "×";
  close.setAttribute("aria-label", "Закрыть");
  toast.append(text, close);
  toastRegion.append(toast);
  dismissToast(toast);
}

const menuButton = document.querySelector(".menu-toggle");
menuButton.addEventListener("click", () => {
  const menu = document.getElementById("mobile-menu");
  menu.hidden = !menu.hidden;
  menuButton.setAttribute("aria-expanded", String(!menu.hidden));
});

document.querySelectorAll("[data-cart-add]").forEach((form) => {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button");
    button.disabled = true;
    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: { Accept: "application/json" },
      });
      const data = await response.json();
      showToast(data.message, !response.ok);
      const counter = document.getElementById("cart-count");
      counter.textContent = data.cart_count;
      counter.classList.remove("bump");
      requestAnimationFrame(() => counter.classList.add("bump"));
    } catch {
      showToast("Не удалось связаться с магазином. Попробуйте ещё раз.", true);
    } finally {
      button.disabled = false;
    }
  });
});

document.querySelectorAll(".field").forEach((wrapper) => {
  const input = wrapper.querySelector("input, select, textarea");
  const errors = wrapper.querySelector(".field-errors");
  if (!input || !errors) return;
  input.setAttribute("aria-describedby", errors.id);
  if (errors.textContent.trim()) input.setAttribute("aria-invalid", "true");
});

const registration = document.querySelector("[data-registration]");
if (registration) {
  const touched = new Set();
  let timer;
  let controller;
  let version = 0;

  async function validate(currentVersion) {
    controller = new AbortController();
    try {
      const response = await fetch(registration.dataset.validateUrl, {
        method: "POST",
        body: new FormData(registration),
        signal: controller.signal,
      });
      if (!response.ok) return;
      const data = await response.json();
      if (currentVersion !== version) return;
      touched.forEach((name) => {
        const field = registration.elements.namedItem(name);
        const errors = document.getElementById(field.id + "-errors");
        const messages = data.errors[name] || [];
        errors.replaceChildren();
        messages.forEach(({ message }) => {
          const text = document.createElement("span");
          text.textContent = message;
          errors.append(text);
        });
        field.setAttribute("aria-invalid", String(messages.length > 0));
      });
    } catch (error) {
      // При недоступной сети остаётся обычная проверка формы при отправке.
      if (error.name !== "AbortError") return;
    }
  }

  registration.addEventListener("input", (event) => {
    if (!event.target.closest(".field")) return;
    touched.add(event.target.name);
    version += 1;
    clearTimeout(timer);
    if (controller) controller.abort();
    timer = setTimeout(() => validate(version), 350);
  });
}
