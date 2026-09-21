(function () {
  'use strict';

  function createModal(id, title) {
    const dialog = document.createElement('dialog');
    dialog.id = id;
    dialog.className = 'admin-modal';
    dialog.innerHTML = '<div class="admin-modal-box"><div class="admin-modal-head"><h2></h2><button type="button" class="admin-modal-close" aria-label="Fechar">×</button></div><div class="admin-modal-body"></div></div>';
    dialog.querySelector('h2').textContent = title || '';
    dialog.querySelector('.admin-modal-close').addEventListener('click', () => dialog.close());
    dialog.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });
    document.body.appendChild(dialog);
    return dialog;
  }

  function setupCreateModals() {
    let counter = 0;
    document.querySelectorAll('.admin-form form[method="post"], form.admin-form[method="post"]').forEach((form) => {
      const action = form.getAttribute('action') || '';
      const hasFile = form.getAttribute('enctype');
      const looksLikeCreate = !action && !hasFile;
      if (!looksLikeCreate || form.dataset.createModalReady) return;
      form.dataset.createModalReady = '1';

      let container = form.classList.contains('admin-form') ? form : form.closest('.admin-form');
      if (!container || container.dataset.createModalContainer) return;
      container.dataset.createModalContainer = '1';
      const heading = container.querySelector('h2');
      const title = heading ? heading.textContent.trim() : 'Novo cadastro';
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'btn btn-primary admin-open-create';
      button.textContent = '+ ' + title;
      container.parentNode.insertBefore(button, container);
      const modal = createModal('admin-create-modal-' + (++counter), title);
      const body = modal.querySelector('.admin-modal-body');
      body.appendChild(container);
      container.style.marginBottom = '0';
      button.addEventListener('click', () => modal.showModal());
      form.addEventListener('submit', () => setTimeout(() => modal.close(), 50));
    });
  }

  function setupDeleteConfirmations() {
    let dialog = createModal('admin-delete-modal', 'Confirmar exclusão');
    const body = dialog.querySelector('.admin-modal-body');
    body.innerHTML = '<p id="admin-delete-message">Tem certeza de que deseja excluir este registro?</p><div class="admin-modal-actions"><button type="button" class="btn btn-outline" id="admin-delete-cancel">Cancelar</button><button type="button" class="btn btn-danger" id="admin-delete-confirm">Excluir</button></div>';
    let pendingForm = null;
    document.getElementById('admin-delete-cancel').addEventListener('click', () => { pendingForm = null; dialog.close(); });
    document.getElementById('admin-delete-confirm').addEventListener('click', () => {
      if (!pendingForm) return;
      const form = pendingForm;
      pendingForm = null;
      dialog.close();
      form.submit();
    });
    document.querySelectorAll('form[method="post"]').forEach((form) => {
      const button = form.querySelector('button');
      const action = form.getAttribute('action') || '';
      const isDelete = /excluir|delete/i.test(action) || (button && /excluir/i.test(button.textContent || ''));
      if (!isDelete || form.dataset.deleteModalReady) return;
      form.dataset.deleteModalReady = '1';
      form.removeAttribute('onsubmit');
      form.addEventListener('submit', (event) => {
        event.preventDefault();
        pendingForm = form;
        const label = button ? button.textContent.trim() : 'este registro';
        document.getElementById('admin-delete-message').textContent = `Tem certeza de que deseja ${label.toLowerCase()}? Esta ação não poderá ser desfeita.`;
        dialog.showModal();
      });
    });
  }

  function init() {
    setupCreateModals();
    setupDeleteConfirmations();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once: true});
  else init();
})();
