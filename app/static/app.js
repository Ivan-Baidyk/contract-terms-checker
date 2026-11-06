/* Логика одностраничного интерфейса. */
(function () {
  'use strict';

  const state = { files: [], result: null };

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  const dropzone = $('#dropzone');
  const fileInput = $('#file-input');
  const fileList = $('#file-list');
  const checkBtn = $('#check-btn');
  const checkDate = $('#check-date');
  const results = $('#results');

  // ---------- Управление файлами ----------

  function addFiles(files) {
    for (const f of files) {
      if (f.name && f.name.toLowerCase().endsWith('.txt')) {
        state.files.push(f);
      }
    }
    renderFileList();
  }

  function renderFileList() {
    fileList.innerHTML = '';
    state.files.forEach((f, i) => {
      const chip = document.createElement('span');
      chip.className = 'file-chip';
      chip.innerHTML =
        '<span>' + escapeHtml(f.name) + '</span>' +
        '<span class="link" data-rm="' + i + '">✕</span>';
      fileList.appendChild(chip);
    });
    checkBtn.disabled = state.files.length === 0;
  }

  fileList.addEventListener('click', (e) => {
    const rm = e.target.getAttribute && e.target.getAttribute('data-rm');
    if (rm !== null) {
      state.files.splice(Number(rm), 1);
      renderFileList();
    }
  });

  dropzone.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', () => {
    addFiles(Array.from(fileInput.files || []));
    fileInput.value = '';
  });

  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    addFiles(Array.from(e.dataTransfer.files || []));
  });

  $('#clear-btn').addEventListener('click', () => {
    state.files = [];
    state.result = null;
    renderFileList();
    results.classList.add('hidden');
  });

  // ---------- Примеры ----------

  $('#load-sample-btn').addEventListener('click', async () => {
    try {
      const resp = await fetch('/api/examples');
      const data = await resp.json();
      const files = data.map(
        (d) => new File([d.content], d.filename, { type: 'text/plain' })
      );
      state.files = files;
      renderFileList();
      await runParse();
    } catch (err) {
      console.error(err);
    }
  });

  // ---------- Отправка ----------

  function checkDateFormatted() {
    const v = checkDate.value; // YYYY-MM-DD
    if (!v) return '10.03.2026';
    const [y, m, d] = v.split('-');
    return d + '.' + m + '.' + y;
  }

  function buildForm() {
    const fd = new FormData();
    fd.append('check_date', checkDateFormatted());
    for (const f of state.files) fd.append('files', f, f.name);
    return fd;
  }

  async function runParse() {
    if (state.files.length === 0) return;
    setBusy(checkBtn, true);
    try {
      const resp = await fetch('/api/parse', { method: 'POST', body: buildForm() });
      const data = await resp.json();
      if (!resp.ok) { alert(data.error || 'Ошибка разбора'); return; }
      state.result = data;
      results.classList.remove('hidden');
      renderTable(data.contracts);
      renderCards(data.contracts);
      renderQuestions(data.questions);
      renderDocuments(data.documents);
    } catch (err) {
      alert('Ошибка запроса: ' + err.message);
    } finally {
      setBusy(checkBtn, false);
    }
  }

  checkBtn.addEventListener('click', runParse);

  // ---------- Рендер: таблица ----------

  function renderTable(contracts) {
    const tbody = $('#contracts-tbody');
    tbody.innerHTML = '';
    for (const c of contracts) {
      const tr = document.createElement('tr');
      const amount = c.amount != null
        ? formatMoney(c.amount) + (c.amount_changed_by ? ' <span class="changed-tag">изм.</span>' : '')
        : '<span class="nodata">нет данных</span>';
      const ddate = c.delivery_date
        ? c.delivery_date + (c.delivery_date_changed_by ? ' <span class="changed-tag">изм.</span>' : '')
        : '<span class="nodata">нет данных</span>';
      const status = c.needs_review
        ? '<span class="changed-tag" style="background:#fecaca;color:#b91c1c">проверить</span>'
        : (c.pending_changes.length ? '<span class="changed-tag" style="background:#fef9c3;color:#854d0e">есть проект/письмо</span>' : '<span class="changed-tag" style="background:#dcfce7;color:#166534">ок</span>');
      tr.innerHTML =
        '<td class="num">' + escapeHtml(c.number) + '</td>' +
        '<td>' + escapeHtml(c.supplier || '—') + '</td>' +
        '<td>' + amount + '</td>' +
        '<td>' + ddate + '</td>' +
        '<td>' + status + '</td>';
      tbody.appendChild(tr);
    }
  }

  // ---------- Рендер: карточки ----------

  function renderCards(contracts) {
    const wrap = $('#contract-cards');
    wrap.innerHTML = '';
    for (const c of contracts) {
      const card = document.createElement('div');
      card.className = 'contract-card';

      const head = document.createElement('div');
      head.className = 'contract-card-head';
      head.innerHTML =
        '<span class="num">' + escapeHtml(c.number) + '</span>' +
        '<span class="supplier">' + escapeHtml(c.supplier || '—') + ' · покупатель ' + escapeHtml(c.buyer || '—') + '</span>';
      card.appendChild(head);

      const body = document.createElement('div');
      body.className = 'contract-card-body';

      body.appendChild(fieldRow('Сумма договора', amountCell(c), c.amount_quote));
      body.appendChild(fieldRow('Срок поставки', deliveryCell(c), c.delivery_date_quote));

      if (c.pending_changes && c.pending_changes.length) {
        const pc = document.createElement('div');
        pc.className = 'pending-box';
        pc.innerHTML = '<div class="ptitle">Несогласованные предложения (не изменяют условия)</div>';
        for (const p of c.pending_changes) {
          const label = p.doc_type === 'letter' ? 'Письмо поставщика' : 'Проект допсоглашения';
          const fromTo = p.old_value ? p.old_value + ' → ' + p.new_value : p.new_value;
          const fieldName = p.field === 'amount' ? 'сумма' : 'срок поставки';
          pc.innerHTML +=
            '<div style="margin-top:8px"><b>' + label + '</b> (' + escapeHtml(p.filename) + '): ' +
            fieldName + ': <b>' + escapeHtml(fromTo || '') + '</b></div>';
          pc.innerHTML += quoteBox(p.quote, p.filename, p.paragraph);
        }
        body.appendChild(pc);
      }

      if (c.needs_review) {
        const rb = document.createElement('div');
        rb.className = 'review-box';
        rb.textContent = 'Требуется ручная проверка: ' + (c.review_reason || 'неоднозначность');
        body.appendChild(rb);
      }

      card.appendChild(body);
      wrap.appendChild(card);
    }
  }

  function fieldRow(label, valueHtml, quote) {
    const row = document.createElement('div');
    row.className = 'field-row';
    row.innerHTML = '<div class="field-label">' + label + '</div><div class="field-value">' + valueHtml + '</div>';
    if (quote && quote.text) {
      row.innerHTML += quoteBox(quote.text, quote.filename, quote.paragraph);
    }
    return row;
  }

  function amountCell(c) {
    if (c.amount == null) return '<span class="nodata">нет данных</span>';
    let html = formatMoney(c.amount);
    if (c.amount_changed_by) html += ' <span class="changed-tag">изменено: ' + escapeHtml(c.amount_changed_by) + '</span>';
    return html;
  }

  function deliveryCell(c) {
    if (!c.delivery_date) return '<span class="nodata">нет данных</span>';
    let html = c.delivery_date;
    if (c.delivery_date_changed_by) html += ' <span class="changed-tag">изменено: ' + escapeHtml(c.delivery_date_changed_by) + '</span>';
    return html;
  }

  function quoteBox(text, filename, paragraph) {
    if (!text) return '';
    return '<div class="quote-box">«' + escapeHtml(text) + '»' +
      '<div class="src">Источник: ' + escapeHtml(filename) +
      (paragraph ? ' · <span class="link" data-src="' + escapeHtml(filename) + '" data-para="' + paragraph + '">перейти к абзацу ↗</span>' : '') +
      '</div></div>';
  }

  // ---------- Рендер: вопросы ----------

  function renderQuestions(questions) {
    const box = $('#q-answers');
    box.innerHTML = '';
    for (const q of questions) {
      box.appendChild(answerEl(q));
    }
  }

  function answerEl(q) {
    const div = document.createElement('div');
    div.className = 'answer' + (q.status === 'no_data' ? ' no_data' : '');
    let html = '<div class="q">Ответ</div><div class="a">' + escapeHtml(q.text) + '</div>';
    if (q.quote && q.quote.text) {
      html += quoteBox(q.quote.text, q.quote.filename, q.quote.paragraph);
    }
    if (q.items && q.items.length) {
      for (const it of q.items) {
        html += '<div style="margin-top:8px"><b>' + escapeHtml(it.number) + '</b> — поставка ' + escapeHtml(it.delivery_date) + '</div>';
        for (const uc of (it.unagreed_changes || [])) {
          html += '<div class="pending-box"><div class="ptitle">Несогласованное изменение срока</div>' +
            '<b>' + escapeHtml(uc.filename) + '</b>: ' + escapeHtml(uc.old_value || '') + ' → ' + escapeHtml(uc.new_value) + '</div>';
        }
      }
    }
    div.innerHTML = html;
    return div;
  }

  async function askQuery(text) {
    if (!state.result && state.files.length === 0) return;
    const box = $('#q-answers');
    const fd = buildForm();
    fd.append('text', text);
    try {
      const resp = await fetch('/api/query', { method: 'POST', body: fd });
      const data = await resp.json();
      box.appendChild(answerEl(data));
    } catch (err) {
      console.error(err);
    }
  }

  $$('.q-btn').forEach((btn) => {
    btn.addEventListener('click', () => askQuery(btn.getAttribute('data-q')));
  });
  $('#q-ask').addEventListener('click', () => {
    const t = $('#q-input').value.trim();
    if (t) askQuery(t);
  });
  $('#q-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const t = $('#q-input').value.trim();
      if (t) askQuery(t);
    }
  });

  // ---------- Рендер: исходные тексты ----------

  function renderDocuments(documents) {
    const wrap = $('#doc-viewer');
    wrap.innerHTML = '';
    documents.forEach((d, di) => {
      const block = document.createElement('div');
      block.className = 'doc-block';
      const head = document.createElement('div');
      head.className = 'doc-block-head';
      head.innerHTML =
        '<span class="fname">' + escapeHtml(d.filename) + '</span>' +
        '<span class="badge ' + escapeHtml(d.doc_type) + '">' + typeLabel(d.doc_type) + '</span>' +
        '<span class="badge ' + statusBadge(d.status).cls + '">' + statusBadge(d.status).label + '</span>';
      block.appendChild(head);
      const paras = document.createElement('div');
      paras.className = 'doc-paras';
      d.paragraphs.forEach((p, pi) => {
        const para = document.createElement('div');
        para.className = 'doc-para';
        para.id = 'doc-' + di + '-p' + (pi + 1);
        para.innerHTML = '<span class="pno">' + (pi + 1) + '</span>' + escapeHtml(p);
        paras.appendChild(para);
      });
      block.appendChild(paras);
      wrap.appendChild(block);
      // сохраняем индекс для переходов
      block.dataset.filename = d.filename;
      block.dataset.index = di;
    });
  }

  // Переход к абзацу по клику на цитату
  document.addEventListener('click', (e) => {
    const t = e.target;
    const src = t.getAttribute && t.getAttribute('data-src');
    if (!src) return;
    const para = t.getAttribute('data-para');
    const blocks = $$('.doc-block');
    const block = blocks.find((b) => b.dataset.filename === src);
    if (!block) return;
    const di = block.dataset.index;
    const el = document.getElementById('doc-' + di + '-p' + para);
    if (el) {
      $$('.doc-para.highlight').forEach((x) => x.classList.remove('highlight'));
      el.classList.add('highlight');
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  });

  // ---------- Утилиты ----------

  function typeLabel(t) {
    return {
      contract: 'договор',
      amendment: 'допсоглашение',
      draft: 'проект',
      letter: 'письмо',
      unknown: 'неизвестно',
    }[t] || t;
  }

  function statusBadge(s) {
    if (s === 'signed') return { cls: 'amendment', label: 'подписан' };
    if (s === 'unsigned') return { cls: 'draft', label: 'не подписан' };
    if (s === 'proposal') return { cls: 'letter', label: 'предложение' };
    return { cls: 'unknown', label: s };
  }

  function formatMoney(n) {
    return n.toLocaleString('ru-RU').replace(/\u00a0/g, ' ') + ' ₽';
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function setBusy(btn, busy) {
    if (busy) {
      btn.dataset.orig = btn.innerHTML;
      btn.innerHTML = '<span class="spinner"></span> Проверка…';
      btn.disabled = true;
    } else {
      btn.innerHTML = btn.dataset.orig || 'Проверить условия';
      btn.disabled = state.files.length === 0;
    }
  }
})();
