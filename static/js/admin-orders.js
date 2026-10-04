document.addEventListener("DOMContentLoaded", () => {
  const checkboxes = [...document.querySelectorAll(".admin-order-card .action-select")];
  const toggle = document.getElementById("select-orders");
  if (!toggle) return;

  function updateSelection() {
    const count = checkboxes.filter((checkbox) => checkbox.checked).length;
    document.querySelectorAll(".action-counter").forEach((counter) => {
      counter.textContent = `Выбрано: ${count} из ${checkboxes.length}`;
    });
    toggle.checked = count > 0 && count === checkboxes.length;
    toggle.indeterminate = count > 0 && count < checkboxes.length;
  }

  toggle.addEventListener("change", () => {
    checkboxes.forEach((checkbox) => { checkbox.checked = toggle.checked; });
    updateSelection();
  });
  checkboxes.forEach((checkbox) => checkbox.addEventListener("change", updateSelection));
  updateSelection();
});
