document.addEventListener('DOMContentLoaded', () => {
  const toggle = document.querySelector('.nav-toggle');
  const nav = document.querySelector('.main-nav');
  if (toggle && nav) toggle.addEventListener('click', () => {
    const open = nav.classList.toggle('mobile-open');
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  });

  document.querySelectorAll('.nav-drop-toggle').forEach(button => {
    button.addEventListener('click', event => {
      event.stopPropagation();
      const parent = button.closest('.nav-dropdown');
      document.querySelectorAll('.nav-dropdown.open').forEach(item => { if (item !== parent) item.classList.remove('open'); });
      parent.classList.toggle('open');
    });
  });
  document.addEventListener('click', event => {
    if (!event.target.closest('.nav-dropdown')) document.querySelectorAll('.nav-dropdown.open').forEach(item => item.classList.remove('open'));
  });
});
