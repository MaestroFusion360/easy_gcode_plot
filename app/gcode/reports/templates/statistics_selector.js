const selector = document.getElementById('tool');
function selectTool() {
  document.querySelectorAll('section').forEach(section => {section.hidden = section.id !== selector.value;});
  document.querySelectorAll('[data-tool-section]').forEach(path => {
    path.style.display = selector.value === 'section-0' || path.dataset.toolSection === selector.value ? '' : 'none';
  });
}
selector.addEventListener('change', selectTool);
selectTool();
