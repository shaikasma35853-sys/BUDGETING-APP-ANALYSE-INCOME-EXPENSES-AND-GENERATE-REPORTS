function renderDashboard(d){
  var months = Array.from(new Set([...(d.income_ts||[]).map(r=>r.month), ...(d.expense_ts||[]).map(r=>r.month)])).sort();
  var incMap = Object.fromEntries((d.income_ts||[]).map(r=>[r.month, r.income]));
  var expMap = Object.fromEntries((d.expense_ts||[]).map(r=>[r.month, r.expense]));
  var inc = months.map(m=>incMap[m]||0);
  var exp = months.map(m=>expMap[m]||0);
  Plotly.newPlot('ixeChart', [
    {x: months, y: inc, type:'bar', name:'Income'},
    {x: months, y: exp, type:'bar', name:'Expense'}
  ], {barmode:'group', margin:{t:20}, yaxis:{title:'₹'}});

  var ts = d.timeseries || [];
  Plotly.newPlot('tsChart', [{x: ts.map(r=>r.month), y: ts.map(r=>r.net), type:'scatter', mode:'lines+markers', name:'Net'}],
                 {margin:{t:20}, yaxis:{title:'₹'}});

  var cm = d.cm_categories || d.categories || [];
  Plotly.newPlot('cmCatChart', [{labels: cm.map(c=>c.category), values: cm.map(c=>c.amount), type: 'pie', hole: 0.45}], {margin:{t:20}});

  var daily = d.daily_cum || [];
  Plotly.newPlot('cumChart', [
    {x: daily.map(r=>r.day), y: daily.map(r=>r.spent_cum), type:'scatter', mode:'lines+markers', name:'Spent'},
    {x: daily.map(r=>r.day), y: daily.map(r=>r.budget_line), type:'scatter', mode:'lines', name:'Budget (linear)'}
  ], {margin:{t:20}, xaxis:{title:'Day of Month'}, yaxis:{title:'₹'}});

  var container = document.getElementById('budgetProgress');
  container.innerHTML = '';
  (d.budget_progress||[]).forEach(item=>{
    var row = document.createElement('div');
    row.className = 'mb-2';
    row.innerHTML = `
      <div class="d-flex justify-content-between small">
        <span>${item.category}</span>
        <span>₹${item.spent} / ₹${item.budget} (${item.pct}%)</span>
      </div>
      <div class="progress" role="progressbar" aria-valuemin="0" aria-valuemax="100">
        <div class="progress-bar ${item.pct>100?'bg-danger':(item.pct>90?'bg-warning':'bg-success')}" style="width:${Math.min(item.pct,150)}%"></div>
      </div>`;
    container.appendChild(row);
  });
}

(function(){
  const btn = document.getElementById('themeToggle');
  const apply = (mode)=>{
    if(mode==='dark'){ document.documentElement.classList.add('dark'); }
    else { document.documentElement.classList.remove('dark'); }
    localStorage.setItem('theme', mode);
  };
  const saved = localStorage.getItem('theme') || 'light';
  apply(saved);
  if(btn){
    btn.addEventListener('click', (e)=>{
      e.preventDefault();
      apply(document.documentElement.classList.contains('dark')?'light':'dark');
    });
  }
})();

(function(){
  const inp = document.getElementById('txnSearch');
  if(!inp) return;
  const table = document.getElementById('txnTable');
  inp.addEventListener('input', ()=>{
    const q = inp.value.toLowerCase();
    Array.from(table.tBodies[0].rows).forEach(r=>{
      const t = Array.from(r.cells).map(c=>c.textContent.toLowerCase()).join(' ');
      r.style.display = t.includes(q)?'':'none';
    });
  });
})();
