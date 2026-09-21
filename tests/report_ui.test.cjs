/* DOM integration tests against the actual generated standalone report.
   npm install --prefix /tmp/htr-report-dom --cache /tmp/htr-npm-cache jsdom
   NODE_PATH=/tmp/htr-report-dom/node_modules node tests/report_ui.test.cjs REPORT.html
   Plotly is stubbed; this verifies UI behavior, not pixel rendering. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {performance} = require('node:perf_hooks');
const {JSDOM} = require('jsdom');
const path = process.argv[2];
assert.ok(path,'Pass the generated report path');
const html=fs.readFileSync(path,'utf8');
const start=performance.now();
const dom=new JSDOM(html,{runScripts:'outside-only',pretendToBeVisual:true});
const w=dom.window,d=w.document;
const plots=[];
w.Plotly={newPlot:(id,data)=>{plots.push(id);d.getElementById(id).data=data;},Plots:{resize:()=>{}}};
// Execute actual report scripts except the bundled third-party plotting library.
for(const script of d.querySelectorAll('script')) {
  if(script.type==='application/json' || script.textContent.includes('plotly.js v')) continue;
  w.eval(script.textContent + (script.textContent.includes('const REPORT_CONFIG') ? '\nwindow.ReportLog = ReportLog;' : ''));
}
d.dispatchEvent(new w.Event('DOMContentLoaded'));
assert.equal(plots.length,2,'Only the visible summary plots render initially');
const namespaces=['mock_small200','mock_large500'];
const ns=namespaces[0];
const id=(prefix,n=ns)=>d.getElementById(prefix+'_'+n);
const payload=n=>w.eval(`ReportLog.state(${JSON.stringify(n)})`);
const event=(node,type)=>node.dispatchEvent(new w.Event(type,{bubbles:true}));
const select=(prefix,value,n=ns)=>{id(prefix,n).value=value;event(id(prefix,n),'change');};
const search=(value,n=ns)=>{id('log-search',n).value=value;event(id('log-search',n),'input');};
const rows=(n=ns)=>[...id('explorer-table',n).querySelectorAll('tr.explorer-row')];
const visibleIds=(n=ns)=>rows(n).map(r=>Number(r.dataset.rowId));
let cases=0;
function equalSelected(expected,n=ns) {
  assert.deepEqual(Array.from(payload(n).selected,r=>r.id),expected.map(r=>r.id));
  assert.deepEqual(visibleIds(n),expected.slice(0,50).map(r=>r.id));
  cases++;
}
w.showTab(ns,4);
assert.equal(rows().length,50);
assert.equal(id('explorer-table').querySelectorAll('.explorer-expand').length,0);
const all=Array.from(payload(ns).rows),texts=payload(ns).texts;
assert.equal(all.length,2400);
const summary=d.getElementById('dataset-panel-'+ns);
const metric=label=>[...summary.querySelectorAll('.metric')].find(m=>m.querySelector('.label')?.textContent===label);
assert.match(summary.querySelector('.summary-volume').textContent,/7200 model requests/);
assert.match(summary.querySelector('.summary-quality').textContent,/7061 \/ 7200/);
assert.equal(summary.querySelector('.summary-quality button').textContent,'83 request errors · 56 judge errors');
assert.equal(metric('Attacks significantly above baseline').querySelector('.value').textContent,'7 / 9');
assert.equal(summary.querySelectorAll('.summary-results .metric').length,3);
const mixed=all.find(r=>r.attack==='NoneAttack' && r.example==='129');
assert.equal(mixed.successes,1);assert.equal(mixed.valid,2);assert.equal(mixed.errors,1);
id('page-next').click();assert.deepEqual(visibleIds(),all.slice(50,100).map(r=>r.id));
// Search a full response on a record far beyond page 1. Also covers Cyrillic.
const remote=all[all.length-1], token=texts[remote.responses[0][1]].split(' ').at(-1);
search(token);
equalSelected(all.filter(r=>r.responses.some(x=>[texts[x[1]],texts[x[2]],texts[x[3]]].some(t=>t.toLowerCase().includes(token.toLowerCase()))) || texts[r.prompt].toLowerCase().includes(token.toLowerCase()) || texts[r.base].toLowerCase().includes(token.toLowerCase())));
search('синтетический');
equalSelected(all.filter(r=>r.responses.some(x=>texts[x[1]].toLowerCase().includes('синтетический'))));
search('no such text 918238');equalSelected([]);assert.ok(id('page-prev').disabled&&id('page-next').disabled);
search('');equalSelected(all);
// Combinations are independently computed from response statuses, before paging.
for(const success of ['all','success','fail','unknown']) {
  for(const error of ['all','any','request_error','judge_error','unscored','no_valid']) {
    for(const blocked of ['all','blocked','not_blocked']) {
      select('filter-success',success);select('filter-errors',error);select('filter-blocked',blocked);
      const expected=all.filter(r=>{
        const statuses=Array.from(r.responses,x=>x[0]);
        const valid=statuses.filter(x=>['success','failure','blocked'].includes(x)).length;
        const wins=statuses.filter(x=>x==='success').length;
        return (success==='all'||success==='success'&&wins>0||success==='fail'&&valid>0&&!wins||success==='unknown'&&!valid)
          && (error==='all'||error==='any'&&statuses.length>valid||error==='no_valid'&&!valid||statuses.includes(error))
          && (blocked==='all'||blocked==='blocked'&&statuses.includes('blocked')||blocked==='not_blocked'&&!statuses.includes('blocked'));
      });
      equalSelected(expected);
    }
  }
}
// Error card resets conflicting filters/query and includes all types.
search('impossible');w.showErrors(ns,'judge_error');
equalSelected(all.filter(r=>r.responses.some(x=>x[0]==='judge_error')));
rows()[0].click();
assert.ok(id('explorer-table').querySelector('.explorer-expand').textContent.includes('Judge error'));
assert.ok(id('explorer-table').querySelector('.explorer-expand').textContent.includes('Synthetic judge timeout'));
rows()[0].click();assert.equal(id('explorer-table').querySelectorAll('.explorer-expand').length,0);
// Restrict type, then uncheck everything: zero rows, never a fallback to "all".
select('filter-errors','all');
const boxes=[...id('attack-type-box').querySelectorAll('input')];
boxes.forEach((c,i)=>c.checked=i===0);event(boxes[0],'change');
equalSelected(all.filter(r=>r.type===boxes[0].value));
search('judge timeout'); select('filter-errors','judge_error');
equalSelected(all.filter(r=>r.type===boxes[0].value && r.responses.some(x=>x[0]==='judge_error')));
search('');select('filter-errors','all');
boxes.forEach(c=>c.checked=false);event(boxes[0],'change');equalSelected([]);
boxes.forEach(c=>c.checked=true);event(boxes[0],'change');
select('page-size','100');assert.equal(rows().length,100);
id('page-next').click();assert.deepEqual(visibleIds(),all.slice(100,200).map(r=>r.id));
search('judge timeout');assert.ok(id('page-prev').disabled,'Search resets page');
// Dataset switching keeps its own filters, pagination and details.
const saved=visibleIds();
w.showDataset(namespaces[1]);w.showTab(namespaces[1],4);
assert.equal(payload(namespaces[1]).rows.length,6000);assert.equal(rows(namespaces[1]).length,50);
assert.equal(id('log-search',namespaces[1]).value,'');
w.showDataset(ns);assert.deepEqual(visibleIds(),saved);
// New plots only on first visit; revisiting resizes, never recreates.
const before=plots.length;w.showTab(ns,2);assert.equal(plots.length,before+2);
w.showTab(ns,2);assert.equal(plots.length,before+2);
// Pure selection edge cases absent from the demo: all-error and malicious text.
const synthetic={attack:'x',type:'z',example:'0',variant:1,variants:1,base:0,prompt:0,
 responses:[['judge_error',0,1,0]],valid:0,successes:0,errors:1,blocked:false};
w.__case=synthetic;w.__texts=['</pre><img src=x onerror=alert(1)>','ошибка'];
assert.equal(w.eval("ReportLog.selectRows([__case],__texts,{success:'fail'}).length"),0);
assert.equal(w.eval("ReportLog.selectRows([__case],__texts,{success:'unknown'}).length"),1);
assert.equal(w.eval("ReportLog.selectRows([__case],__texts,{errors:'no_valid',query:'ОШИБКА'}).length"),1);
assert.ok(!w.eval('ReportLog.details(__case,__texts)').includes('<img'));
assert.equal(w.eval('ReportLog.pageRows([],99,50).page'),0);
assert.equal(w.eval('ReportLog.pageRows([1,2,3],99,2).rows[0]'),3);
const output={filter_combinations:cases,datasets:2,records:8400,initial_page:50,
 lazy_plots:true,details_and_escaping:true,elapsed_seconds:(performance.now()-start)/1000};
console.log(JSON.stringify(output,null,2));dom.window.close();
