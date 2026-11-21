/* The landing page uses the same local illustrative geometry as the dashboard. */
'use strict';
(async () => {
  const byId = id => document.getElementById(id);
  try {
    const response = await fetch('/api/state');
    if (!response.ok) throw new Error('Snapshot unavailable');
    const data = await response.json();
    byId('home-count').textContent = data.facilities.length;
    byId('home-sectors').textContent = new Set(data.facilities.map(f => f.sector)).size;
    byId('home-snapshot').textContent = `${data.city.city_en} · Fictional city · Snapshot ${data.at}`;
    const selected = data.facilities.find(f => f.asset_id === 'AST-0036') || data.facilities[0];
    if (!selected) { byId('home-model-name').textContent = 'No facilities in this dataset'; return; }
    byId('home-model-name').textContent = selected.name_en;
    const button = byId('home-rotate');
    const viewer = new SahilAsset3D.AssetViewer(byId('home-model'), {onChange:({rotating}) => {
      button.textContent = rotating ? 'Pause rotation' : 'Rotate model';
      button.setAttribute('aria-pressed',String(rotating));
    }});
    viewer.setFacility(selected);
    button.hidden = false;
    button.onclick = () => viewer.setRotation(!viewer.rotating);
  } catch (error) {
    byId('home-model-caption').textContent = 'Open the dashboard to explore the data and asset profiles.';
  }
})();
