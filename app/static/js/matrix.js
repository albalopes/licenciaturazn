document.addEventListener('DOMContentLoaded', () => {
  const buttons = document.querySelectorAll('.view-btn');
  const cards = document.getElementById('matrix-cards');
  const table = document.getElementById('matrix-table');
  buttons.forEach(button => button.addEventListener('click', () => {
    buttons.forEach(b => b.classList.remove('active'));
    button.classList.add('active');
    const isTable = button.dataset.view === 'table';
    cards.classList.toggle('hidden', isTable);
    table.classList.toggle('hidden', !isTable);
    localStorage.setItem('matrix-view', button.dataset.view);
  }));
  const saved = localStorage.getItem('matrix-view');
  if (saved) document.querySelector(`.view-btn[data-view="${saved}"]`)?.click();
});
