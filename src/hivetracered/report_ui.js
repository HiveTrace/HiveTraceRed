// Embedded in the standalone report: no server, fetches or external dependencies.
const ReportLog = (() => {
  const states = new Map();
  const labels = {success:'Success', failure:'Unsuccessful attack', blocked:'Blocked',
    request_error:'Request error', judge_error:'Judge error', unscored:'No assessment'};
  const suffix = ns => ns ? '_' + ns : '';
  const el = (prefix, ns) => document.getElementById(prefix + suffix(ns));
  const escape = value => String(value).replace(/[&<>"']/g, ch =>
    ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[ch]));
  function searchText(row, texts) {
    return [row.attack,row.type,row.example,row.variant,texts[row.base],texts[row.prompt],
      ...row.responses.flatMap(r => [labels[r[0]],texts[r[1]],texts[r[2]],texts[r[3]]])]
      .join('\n').toLocaleLowerCase();
  }
  function selectRows(rows, texts, filters) {
    const query = (filters.query || '').trim().toLocaleLowerCase();
    return rows.filter(row => {
      if (filters.types && !filters.types.includes(row.type)) return false;
      if (filters.success === 'success' && !row.successes) return false;
      if (filters.success === 'fail' && (!row.valid || row.successes)) return false;
      if (filters.success === 'unknown' && row.valid) return false;
      if (filters.blocked === 'blocked' && !row.blocked) return false;
      if (filters.blocked === 'not_blocked' && row.blocked) return false;
      if (filters.errors === 'any' && !row.errors) return false;
      if (filters.errors === 'no_valid' && row.valid) return false;
      if (['request_error','judge_error','unscored'].includes(filters.errors) &&
          !row.responses.some(r => r[0] === filters.errors)) return false;
      return !query || searchText(row, texts).includes(query);
    });
  }
  function pageRows(rows, page, size) {
    const pages = Math.max(1, Math.ceil(rows.length / size));
    page = Math.max(0, Math.min(page, pages - 1));
    return {rows: rows.slice(page * size, (page + 1) * size), page, pages};
  }
  function state(ns) {
    if (!states.has(ns)) {
      const data = el('log-data', ns);
      const payload = data ? JSON.parse(data.textContent) : {texts:[], rows:[]};
      if (data) data.textContent = ''; // JSON can be released after parsing.
      payload.rows.forEach((row, i) => row.id = i);
      states.set(ns, {...payload, page:0, size:50, selected:payload.rows});
    }
    return states.get(ns);
  }
  function details(row, texts) {
    let html = `<h4>Original example</h4><pre>${escape(texts[row.base])}</pre>` +
      `<h4>Attack variant ${row.variant} of ${row.variants}</h4><pre>${escape(texts[row.prompt])}</pre>`;
    row.responses.forEach((response, i) => {
      html += `<h4>Request ${i+1}: ${labels[response[0]]}</h4>`;
      for (let j=1; j<4; j++) if (texts[response[j]]) {
        html += `<pre${j===2 ? ' class="explorer-error"' : ''}>${escape(texts[response[j]])}</pre>`;
      }
    });
    return html;
  }
  function render(ns) {
    const table = el('explorer-table', ns);
    if (!table) return;
    const s = state(ns), page = pageRows(s.selected, s.page, s.size);
    s.page = page.page;
    table.querySelector('tbody').innerHTML = page.rows.map(row => {
      const success = row.valid ? `${row.successes}/${row.valid} · ${(100*row.successes/row.valid).toFixed(0)}%` : 'No assessment';
      const base = s.texts[row.base];
      const cells = [row.attack,row.type,row.example,`${row.variant} of ${row.variants}`,
        base.length > 100 ? base.slice(0,99)+'…' : base,
        `${row.responses.length} requests · ${row.valid} valid`,success,row.errors,row.blocked ? 'Yes' : 'No'];
      return `<tr class="explorer-row" data-row-id="${row.id}" tabindex="0" aria-expanded="false">` +
        cells.map(value=>`<td>${escape(value)}</td>`).join('') + '</tr>';
    }).join('') || '<tr><td colspan="9">No matching records</td></tr>';
    const start = s.selected.length ? s.page*s.size+1 : 0;
    const end = Math.min((s.page+1)*s.size, s.selected.length);
    el('filtered-count',ns).textContent = `${start}–${end} of ${s.selected.length} matching records (${s.rows.length} total)`;
    el('page-label',ns).textContent = `Page ${s.page+1} of ${page.pages}`;
    el('page-prev',ns).disabled = s.page === 0;
    el('page-next',ns).disabled = s.page+1 === page.pages;
  }
  function filter(ns) {
    const s = state(ns);
    const types = Array.from(el('attack-type-box',ns).querySelectorAll('input:checked')).map(c=>c.value);
    s.selected = selectRows(s.rows,s.texts,{
      query:el('log-search',ns).value, types,
      success:el('filter-success',ns).value, blocked:el('filter-blocked',ns).value,
      errors:el('filter-errors',ns).value});
    s.page = 0;
    render(ns);
  }
  function bind(ns) {
    const table=el('explorer-table',ns);
    if (!table || table.dataset.bound) return;
    table.dataset.bound='1';
    const box=el('attack-type-box',ns);
    (REPORT_CONFIG.types[ns] || []).forEach(type=>{
      const label=document.createElement('label'), cb=document.createElement('input');
      cb.type='checkbox'; cb.checked=true; cb.value=type;
      label.append(cb,document.createTextNode(' '+type)); box.appendChild(label);
    });
    box.addEventListener('change',()=>filter(ns));
    ['filter-success','filter-blocked','filter-errors'].forEach(id=>el(id,ns).addEventListener('change',()=>filter(ns)));
    el('log-search',ns).addEventListener('input',()=>filter(ns));
    el('page-size',ns).addEventListener('change',()=>{state(ns).size=Number(el('page-size',ns).value);state(ns).page=0;render(ns);});
    el('page-prev',ns).addEventListener('click',()=>{state(ns).page--;render(ns);});
    el('page-next',ns).addEventListener('click',()=>{state(ns).page++;render(ns);});
    const expand = event => {
      if (event.type==='keydown' && !['Enter',' '].includes(event.key)) return;
      const tr=event.target.closest('tr.explorer-row');
      if (!tr || !table.contains(tr)) return;
      if(event.type==='keydown') event.preventDefault();
      const next=tr.nextElementSibling;
      if(next && next.classList.contains('explorer-expand')) {
        next.remove(); tr.classList.remove('open'); tr.setAttribute('aria-expanded','false'); return;
      }
      const s=state(ns), row=s.rows[Number(tr.dataset.rowId)];
      const detail=document.createElement('tr'); detail.className='explorer-expand';
      const cell=document.createElement('td'); cell.colSpan=9;
      cell.innerHTML=details(row,s.texts); detail.appendChild(cell);tr.after(detail);
      tr.classList.add('open');tr.setAttribute('aria-expanded','true');
    };
    table.addEventListener('click',expand);table.addEventListener('keydown',expand);
  }
  return {selectRows,pageRows,details,bind,filter,render,state};
})();
function renderVisibleCharts(scope) {
  if (!scope || !window.Plotly) return;
  scope.querySelectorAll('.plotly-graph-div').forEach(gd=>{
    if (gd.closest('[style*="display:none"], [style*="display: none"]')) return;
    const pending = (window.REPORT_PLOTS || {})[gd.id];
    if (pending) { delete window.REPORT_PLOTS[gd.id]; pending(); }
    else if(gd.data) window.Plotly.Plots.resize(gd);
  });
}
function showTab(ns,n) {
  const scope=ns ? document.getElementById('dataset-panel-'+ns) : document;
  if(!scope) return;
  const suffix=ns ? '_'+ns : '';
  scope.querySelectorAll('.section').forEach(section=>section.style.display='none');
  const tab=document.getElementById('tab'+n+suffix);if(tab) tab.style.display='block';
  scope.querySelectorAll('.tablink').forEach(button=>button.classList.toggle('active',button.dataset.target==='tab'+n+suffix));
  if(n===4) {ReportLog.bind(ns); ReportLog.render(ns);}
  renderVisibleCharts(tab);
}
function showDataset(ns) {
  document.querySelectorAll('.dataset-panel').forEach(panel=>panel.style.display=panel.id==='dataset-panel-'+ns?'block':'none');
  document.querySelectorAll('.dataset-tablink').forEach(button=>button.classList.toggle('active',button.dataset.ds===ns));
  renderVisibleCharts(document.getElementById('dataset-panel-'+ns));
}
function showErrors(ns,kind) {
  showTab(ns,4);
  const suffix=ns?'_'+ns:'';
  document.getElementById('log-search'+suffix).value='';
  ['filter-success','filter-blocked'].forEach(id=>document.getElementById(id+suffix).value='all');
  document.querySelectorAll('#attack-type-box'+suffix+' input').forEach(cb=>cb.checked=true);
  document.getElementById('filter-errors'+suffix).value=kind;
  ReportLog.filter(ns);
}
document.addEventListener('DOMContentLoaded',()=>{
  if(REPORT_CONFIG.multi && REPORT_CONFIG.namespaces.length) showDataset(REPORT_CONFIG.namespaces[0]);
  else showTab('',1);
});
