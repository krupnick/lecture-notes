// Click a prompt to grey it out as "already used" during class.
// This is intentionally NOT saved anywhere -- reloading the page
// (e.g. before your next section) clears all of them automatically.

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.prompt').forEach((el) => {
    el.addEventListener('click', () => {
      el.classList.toggle('used');
    });
  });
});
