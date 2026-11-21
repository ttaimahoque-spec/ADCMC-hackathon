/* Embedded in the saved report. No requests, external files or app are needed. */
(function () {
  'use strict';
  const byId = id => document.getElementById(id);
  const data = JSON.parse(byId('report-data').textContent);
  const date = data.dashboard.at.slice(0,10);
  const basename = 'Sahil_Atlas_' + data.scope + '_' + date;
  function save(content, name, type) {
    const url = URL.createObjectURL(new Blob([content], {type}));
    const link = document.createElement('a');
    link.href = url; link.download = name;
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  }
  byId('download-report').onclick = () => save('<!doctype html>\n' + document.documentElement.outerHTML, basename + '.html', 'text/html;charset=utf-8');
  byId('download-evidence').onclick = () => save(JSON.stringify(data, null, 2), basename + '_evidence.json', 'application/json');
  let wasOpen = [];
  function beforePrint() {
    if (wasOpen.length) return;
    wasOpen = Array.from(document.querySelectorAll('details')).map(el => ({el, open:el.open}));
    for (const entry of wasOpen) entry.el.open = true;
  }
  function afterPrint() {
    for (const entry of wasOpen) entry.el.open = entry.open;
    wasOpen = [];
  }
  window.addEventListener('beforeprint', beforePrint);
  window.addEventListener('afterprint', afterPrint);
  byId('print-report').onclick = () => { beforePrint(); window.print(); };
  const link = byId('scope-link');
  const query = new URLSearchParams({scope:data.scope === 'portfolio' ? 'selected' : 'portfolio',asset:data.selected_asset || ''});
  for (const id of data.selected_measure_ids) query.append('measure',id);
  link.href = '/report?' + query.toString();
  link.textContent = data.scope === 'portfolio' ? 'Create a shorter selected-asset report' : 'Create the full portfolio report';
  if (location.protocol === 'file:' || location.protocol === 'blob:') {
    document.querySelector('.online-actions').hidden = true;
    document.querySelector('.report-tools>div>span').textContent = 'Saved offline snapshot';
  }
})();
