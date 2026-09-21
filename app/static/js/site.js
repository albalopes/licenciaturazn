document.addEventListener('DOMContentLoaded', () => {
  const toggle = document.querySelector('.nav-toggle');
  const nav = document.querySelector('.main-nav');

  function closeMobileMenu() {
    if (!nav || !toggle) return;
    nav.classList.remove('mobile-open');
    toggle.setAttribute('aria-expanded', 'false');
  }

  if (toggle && nav) {
    toggle.addEventListener('click', event => {
      event.stopPropagation();
      const open = nav.classList.toggle('mobile-open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  document.querySelectorAll('.nav-drop-toggle').forEach(button => {
    button.setAttribute('aria-expanded', 'false');
    button.addEventListener('click', event => {
      event.stopPropagation();
      const parent = button.closest('.nav-dropdown');
      const wasOpen = parent.classList.contains('open');
      document.querySelectorAll('.nav-dropdown.open').forEach(item => {
        item.classList.remove('open');
        const itemButton = item.querySelector('.nav-drop-toggle');
        if (itemButton) itemButton.setAttribute('aria-expanded', 'false');
      });
      if (!wasOpen) {
        parent.classList.add('open');
        button.setAttribute('aria-expanded', 'true');
      }
    });
  });

  document.querySelectorAll('.main-nav a').forEach(link => {
    link.addEventListener('click', () => closeMobileMenu());
  });

  document.addEventListener('click', event => {
    if (!event.target.closest('.nav-dropdown')) {
      document.querySelectorAll('.nav-dropdown.open').forEach(item => {
        item.classList.remove('open');
        const itemButton = item.querySelector('.nav-drop-toggle');
        if (itemButton) itemButton.setAttribute('aria-expanded', 'false');
      });
    }
  });

  window.addEventListener('resize', () => {
    if (window.innerWidth > 900) closeMobileMenu();
  });
});

/* Filtros automáticos: selects e opções mudam a página imediatamente; buscas textuais continuam com o botão/Enter. */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('form[method="get"]').forEach(form => {
    if (form.dataset.autoFilterReady) return;
    form.dataset.autoFilterReady = '1';
    form.querySelectorAll('select, input[type="checkbox"], input[type="radio"]').forEach(control => {
      control.addEventListener('change', () => form.requestSubmit());
    });
    if (!form.querySelector('.filter-clear')) {
      const clear = document.createElement('a');
      clear.className = 'btn btn-outline filter-clear';
      clear.href = form.getAttribute('action') || window.location.pathname;
      clear.textContent = 'Limpar filtros';
      const actions = form.querySelector('.filter-actions') || form;
      actions.appendChild(clear);
    }
  });
});
