(function () {
  const $ = (id) => document.getElementById(id);
  const fmt = (n) => Math.round(n).toLocaleString('vi-VN');
  const money = (n) => fmt(n) + 'đ';
  const pct = (n, d = 1) => Number(n).toLocaleString('vi-VN', { minimumFractionDigits: d, maximumFractionDigits: d }) + '%';
  const billions = (n) => (n / 1e9).toLocaleString('vi-VN', { maximumFractionDigits: 1 }) + ' tỷ';
  const dmy = (s) => s.split('-').reverse().join('/');
  const dm = (s) => s.split('-').slice(1).reverse().join('/');
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const color = (g) => `var(--${g})`;
  const tip = $('tip');

  const showTip = (e, html) => {
    tip.innerHTML = html;
    tip.hidden = false;
    const r = tip.getBoundingClientRect();
    tip.style.left = Math.max(8, Math.min(innerWidth - r.width - 8, e.clientX + 12)) + 'px';
    tip.style.top = Math.max(8, e.clientY - r.height - 12) + 'px';
  };
  const hideTip = () => { tip.hidden = true; };
  addEventListener('scroll', hideTip, { passive: true });

  const icons = {
    'Nghỉ': '<svg viewBox="0 0 12 12" aria-hidden="true"><rect x="2" y="2" width="3" height="8" fill="currentColor"/><rect x="7" y="2" width="3" height="8" fill="currentColor"/></svg>',
    'Chơi nhẹ': '<svg viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="4" fill="none" stroke="currentColor" stroke-width="2"/></svg>',
    'Chơi': '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M2 6.5 5 9.5 10.5 2.5" fill="none" stroke="currentColor" stroke-width="2"/></svg>',
  };
  const vclass = { 'Nghỉ': 'v-rest', 'Chơi nhẹ': 'v-light', 'Chơi': 'v-play' };
  const balls = (nums, extra = []) => '<ul class="balls">' + nums.map((n) => `<li>${String(n).padStart(2, '0')}</li>`).join('') +
    extra.map((n) => `<li class="sp">${String(n).padStart(2, '0')}</li>`).join('') + '</ul>';

  function slip(n, last) {
    const seg = (v) => (v / 10000 * 100).toFixed(2) + '%';
    const j2 = n.game === 'power';
    const setsTitle = n.tickets ? `Bộ số cho ${n.tickets} vé, chọn tránh kiểu số đông người chọn` : 'Bộ số tham khảo nếu vẫn muốn mua';
    return `<article class="slip" style="--c:${color(n.game)}">
      <div class="slip-head"><div><h2>${esc(n.name)}</h2><p class="slip-date">Kỳ ${n.id}, ${esc(n.weekday)} ${dmy(n.date)}</p></div>
      <span class="verdict ${vclass[n.verdict]}">${icons[n.verdict]}${esc(n.verdict)}</span></div>
      <div class="value"><div class="value-num">${money(n.ev.total)}</div>
      <div class="value-sub">giá trị kỳ vọng trên vé 10.000đ, bằng ${pct(n.ev.pct)}</div></div>
      <div class="ticketbar" role="img" aria-label="Giá trị kỳ vọng ${pct(n.ev.pct)} giá vé">
        <i class="fx" style="width:${seg(n.ev.fixed)}"></i><i class="j1" style="width:${seg(n.ev.jackpot)}"></i>${j2 ? `<i class="j2" style="width:${seg(n.ev.jackpot2)}"></i>` : ''}</div>
      <ul class="key"><li><b style="background:var(--spent)"></b>Giải cố định ${money(n.ev.fixed)}</li>
      <li><b style="background:var(--c)"></b>${j2 ? 'Jackpot 1' : 'Jackpot'} ${money(n.ev.jackpot)}</li>
      ${j2 ? `<li><b style="background:var(--return)"></b>Jackpot 2 ${money(n.ev.jackpot2)}</li>` : ''}</ul>
      <dl class="stats"><div><dt>${j2 ? 'Jackpot 1 ước tính' : 'Jackpot ước tính'}</dt><dd>${billions(n.jackpot)}</dd></div>
      ${j2 ? `<div><dt>Jackpot 2 ước tính</dt><dd>${billions(n.jackpot2)}</dd></div>` : ''}
      <div><dt>Vé bán ước tính</dt><dd>${(n.tickets_est / 1e6).toLocaleString('vi-VN', { maximumFractionDigits: 2 })} triệu</dd></div>
      <div><dt>Số vé gợi ý</dt><dd>${n.tickets}</dd></div></dl>
      <div class="sets"><h3>${esc(setsTitle)}</h3>${n.sets.map((s) => balls(s)).join('')}</div>
      <div class="last">Kỳ ${last.id}, ${esc(last.weekday)} ${dmy(last.date)}${last.jackpot_winners ? ', có người trúng jackpot' : ', chưa có người trúng jackpot'}
      ${balls(last.main, last.extra)}</div></article>`;
  }

  function evChart(el, game, rows, rules) {
    const render = () => {
      const w = el.clientWidth, h = 230, m = { t: 14, r: 14, b: 26, l: 42 };
      const iw = w - m.l - m.r, ih = h - m.t - m.b;
      const top = Math.max(100, Math.ceil(Math.max(...rows.map((r) => r.pct)) / 20) * 20);
      const x = (i) => m.l + (rows.length < 2 ? 0 : i * iw / (rows.length - 1));
      const y = (v) => m.t + ih - v / top * ih;
      const grid = [0, top / 2, top].map((v) => `<line x1="${m.l}" x2="${w - m.r}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)"/><text x="${m.l - 8}" y="${y(v) + 4}" text-anchor="end">${v}%</text>`).join('');
      const zone = `<rect x="${m.l}" width="${iw}" y="${y(rules.play_pct)}" height="${y(rules.light_pct) - y(rules.play_pct)}" fill="var(--band-fill)"/>`;
      const line = rows.map((r, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(r.pct).toFixed(1)}`).join(' ');
      const dots = rows.map((r, i) => `<circle cx="${x(i)}" cy="${y(r.pct)}" r="${r.winners ? 5 : 3}" fill="${r.winners ? 'var(--surface)' : color(game)}" stroke="${color(game)}" stroke-width="2"/>`).join('');
      const hits = rows.map((r, i) => `<rect data-i="${i}" x="${x(i) - iw / rows.length / 2}" y="${m.t}" width="${iw / rows.length}" height="${ih}" fill="transparent"/>`).join('');
      const ticks = [0, rows.length - 1].map((i) => `<text x="${x(i)}" y="${h - 6}" text-anchor="${i ? 'end' : 'start'}">Kỳ ${rows[i].id}</text>`).join('');
      el.innerHTML = `<svg viewBox="0 0 ${w} ${h}" height="${h}" role="img" aria-label="Giá trị kỳ vọng theo kỳ">${grid}${zone}<path d="${line}" fill="none" stroke="${color(game)}" stroke-width="2"/>${dots}${ticks}${hits}</svg>`;
      el.querySelectorAll('rect[data-i]').forEach((node) => {
        const r = rows[+node.dataset.i];
        const on = (e) => showTip(e, `Kỳ ${r.id}, ${dmy(r.date)}<br>Jackpot ${billions(r.jackpot)}${r.winners ? ', có người trúng' : ''}<br>Giá trị vé ${pct(r.pct)}`);
        node.addEventListener('pointermove', on);
        node.addEventListener('pointerdown', on);
        node.addEventListener('pointerleave', hideTip);
      });
    };
    render();
    new ResizeObserver(render).observe(el);
  }

  function zChart(el, game, t) {
    const render = () => {
      const w = el.clientWidth, h = 190, m = { t: 10, r: 6, b: 24, l: 34 };
      const iw = w - m.l - m.r, ih = h - m.t - m.b, top = 3.5;
      const y = (v) => m.t + ih / 2 - v / top * ih / 2;
      const step = iw / t.z.length, bw = Math.max(1.5, step - 2);
      const band = `<rect x="${m.l}" width="${iw}" y="${y(1.96)}" height="${y(-1.96) - y(1.96)}" fill="var(--band-fill)"/>`;
      const labels = [3, 0, -3].map((v) => `<text x="${m.l - 8}" y="${y(v) + 4}" text-anchor="end">${v > 0 ? '+' : ''}${v}</text>`).join('');
      const bars = t.z.map((z, i) => {
        const a = y(Math.max(z, 0)), b = y(Math.min(z, 0));
        return `<rect x="${m.l + i * step + 1}" y="${a}" width="${bw}" height="${Math.max(1, b - a)}" rx="1" fill="${color(game)}"/>`;
      }).join('');
      const hits = t.z.map((z, i) => `<rect data-i="${i}" x="${m.l + i * step}" y="${m.t}" width="${step}" height="${ih}" fill="transparent"/>`).join('');
      const ticks = [1, t.z.length].map((n) => `<text x="${m.l + (n - .5) * step}" y="${h - 6}" text-anchor="middle">Số ${n}</text>`).join('');
      el.innerHTML = `<svg viewBox="0 0 ${w} ${h}" height="${h}" role="img" aria-label="Độ lệch tần suất từng số">${band}<line x1="${m.l}" x2="${w - m.r}" y1="${y(0)}" y2="${y(0)}" stroke="var(--ink-3)"/>${labels}${bars}${ticks}${hits}</svg>`;
      el.querySelectorAll('rect[data-i]').forEach((node) => {
        const i = +node.dataset.i;
        const on = (e) => showTip(e, `Số ${i + 1}: ra ${fmt(t.counts[i])} lần<br>Kỳ vọng ${fmt(t.expected_count)} lần<br>Độ lệch ${t.z[i].toLocaleString('vi-VN')}`);
        node.addEventListener('pointermove', on);
        node.addEventListener('pointerdown', on);
        node.addEventListener('pointerleave', hideTip);
      });
    };
    render();
    new ResizeObserver(render).observe(el);
  }

  function bookChart(el, b) {
    const render = () => {
      const rows = b.path, w = el.clientWidth, h = 260, m = { t: 14, r: 12, b: 26, l: 62 };
      const iw = w - m.l - m.r, ih = h - m.t - m.b, top = b.spent;
      const x = (i) => m.l + i * iw / (rows.length - 1);
      const y = (v) => m.t + ih - v / top * ih;
      const path = (k) => rows.map((r, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(r[k]).toFixed(1)}`).join(' ');
      const grid = [0, top / 2, top].map((v) => `<line x1="${m.l}" x2="${w - m.r}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)"/><text x="${m.l - 8}" y="${y(v) + 4}" text-anchor="end">${v ? (v / 1e6).toLocaleString('vi-VN') + ' triệu' : '0'}</text>`).join('');
      const end = rows[rows.length - 1];
      const hits = rows.map((r, i) => `<rect data-i="${i}" x="${x(i) - iw / rows.length / 2}" y="${m.t}" width="${iw / rows.length}" height="${ih}" fill="transparent"/>`).join('');
      el.innerHTML = `<svg viewBox="0 0 ${w} ${h}" height="${h}" role="img" aria-label="Tiền bỏ ra và tiền thu về trong backtest">${grid}
        <path d="${path('spent')}" fill="none" stroke="var(--spent)" stroke-width="2"/>
        <path d="${path('random')}" fill="none" stroke="var(--power)" stroke-width="2"/>
        <path d="${path('filter')}" fill="none" stroke="var(--mega)" stroke-width="2"/>
        <text x="${m.l}" y="${h - 6}">${dm(rows[0].week)}</text><text x="${w - m.r}" y="${h - 6}" text-anchor="end">${dm(end.week)}</text>${hits}</svg>
        <ul class="key" style="margin-top:8px"><li><b style="background:var(--spent)"></b>Tiền bỏ ra</li><li><b style="background:var(--mega)"></b>Thu về, bộ số đã lọc</li><li><b style="background:var(--power)"></b>Thu về, chọn ngẫu nhiên</li></ul>`;
      el.querySelectorAll('rect[data-i]').forEach((node) => {
        const r = rows[+node.dataset.i];
        const on = (e) => showTip(e, `Tuần từ ${dmy(r.week)}<br>Bỏ ra ${money(r.spent)}<br>Thu về đã lọc ${money(r.filter)}<br>Thu về ngẫu nhiên ${money(r.random)}`);
        node.addEventListener('pointermove', on);
        node.addEventListener('pointerdown', on);
        node.addEventListener('pointerleave', hideTip);
      });
    };
    render();
    new ResizeObserver(render).observe(el);
  }

  function render(d) {
    const stale = (Date.now() - new Date(d.generated_at).getTime()) / 36e5 > 36;
    $('stamp').textContent = `Cập nhật ${d.generated_at.slice(11, 16)}, ${d.weekday} ${dmy(d.today)}`;
    $('headline').textContent = d.commentary.headline;
    $('commentary').innerHTML = d.commentary.paragraphs.map((p) => `<p>${esc(p)}</p>`).join('');
    const warn = [...d.warnings];
    if (stale) warn.unshift(`Trang chưa được cập nhật từ ${dmy(d.today)}, các số dưới đây có thể đã cũ.`);
    $('alerts').innerHTML = warn.map((w) => `<p>${esc(w)}</p>`).join('');
    $('slips').innerHTML = d.next.map((n) => slip(n, d.latest[n.game])).join('');

    const names = { mega: 'Mega 6/45', power: 'Power 6/55' };
    $('value-charts').innerHTML = Object.keys(names).map((g) => `<div class="chart"><h3>${names[g]}</h3><p>Giá trị kỳ vọng so với giá vé. Vùng nền là mức chơi nhẹ, chấm rỗng là kỳ có người trúng jackpot.</p><div class="plot" id="ev-${g}"></div></div>`).join('');
    Object.keys(names).forEach((g) => evChart($('ev-' + g), g, d.ev_history[g], d.rules));
    $('breakeven').innerHTML = `<caption>Jackpot cần có để vé đạt từng mức giá trị</caption><thead><tr><th>Trò chơi</th><th>${d.rules.light_pct}%, chơi nhẹ</th><th>${d.rules.play_pct}%, chơi</th><th>100%, hòa vốn kỳ vọng</th></tr></thead><tbody>` +
      Object.keys(names).map((g) => `<tr><td>${names[g]}</td>${['45', '55', '100'].map((k) => `<td>${billions(d.breakeven[g][k])}</td>`).join('')}</tr>`).join('') + '</tbody>';
    $('value-table').innerHTML = '<table><thead><tr><th>Kỳ</th><th>Trò chơi</th><th>Ngày</th><th>Jackpot</th><th>Giá trị vé</th></tr></thead><tbody>' +
      Object.keys(names).flatMap((g) => d.ev_history[g].slice().reverse().map((r) => `<tr><td>${r.id}</td><td>${names[g]}</td><td>${dmy(r.date)}</td><td>${billions(r.jackpot)}</td><td>${pct(r.pct)}</td></tr>`)).join('') + '</tbody></table>';

    const t = d.tests;
    $('test-intro').textContent = `Kết luận: không có dấu hiệu đoán được. Kết quả ${fmt(t.mega.draws)} kỳ Mega và ${fmt(t.power.draws)} kỳ Power đều phù hợp với quay ngẫu nhiên, và chọn theo số nóng hay số lạnh không trúng nhiều hơn mức kỳ vọng.`;
    $('test-charts').innerHTML = Object.keys(names).map((g) => `<div class="chart"><h3>${names[g]}</h3><p>Độ lệch tần suất từng số. Vùng nền là khoảng dao động bình thường.</p><div class="plot" id="z-${g}"></div></div>`).join('');
    Object.keys(names).forEach((g) => zChart($('z-' + g), g, t[g]));
    $('test-table').innerHTML = `<thead><tr><th>Phép thử</th><th>Mega 6/45</th><th>Power 6/55</th></tr></thead><tbody>
      <tr><td>Khả năng phân bố số là đều (p, trên 0,05 là bình thường)</td><td>${t.mega.p.toLocaleString('vi-VN')}</td><td>${t.power.p.toLocaleString('vi-VN')}</td></tr>
      <tr><td>Số lệch ngoài vùng bình thường, thực tế / kỳ vọng</td><td>${t.mega.outside} / ${t.mega.outside_expected.toLocaleString('vi-VN')}</td><td>${t.power.outside} / ${t.power.outside_expected.toLocaleString('vi-VN')}</td></tr>
      <tr><td>Chọn 6 số nóng ${d.rules.hot_window} kỳ, số trùng mỗi kỳ / kỳ vọng</td><td>${t.mega.hot.mean.toLocaleString('vi-VN')} / ${t.mega.hot.expected.toLocaleString('vi-VN')}</td><td>${t.power.hot.mean.toLocaleString('vi-VN')} / ${t.power.hot.expected.toLocaleString('vi-VN')}</td></tr>
      <tr><td>Chọn 6 số lạnh ${d.rules.hot_window} kỳ, số trùng mỗi kỳ / kỳ vọng</td><td>${t.mega.cold.mean.toLocaleString('vi-VN')} / ${t.mega.cold.expected.toLocaleString('vi-VN')}</td><td>${t.power.cold.mean.toLocaleString('vi-VN')} / ${t.power.cold.expected.toLocaleString('vi-VN')}</td></tr></tbody>`;

    const p = d.portfolio, b = d.backtest;
    $('book-intro').textContent = `Sổ theo dõi các nhận định trên trang từ ${dmy(p.start)}, không phải tiền thật. Trần ${p.week_cap} vé mỗi tuần, phần không dùng không cộng dồn.`;
    $('book-facts').innerHTML = `<div><b>${p.week_used}/${p.week_cap} vé</b><span>đã dùng tuần này</span></div>
      <div><b>${money(p.spent)}</b><span>đã chi từ khi bắt đầu</span></div>
      <div><b>${money(p.returned)}</b><span>thu về, bộ số đã lọc</span></div>
      <div><b>${money(p.returned_baseline)}</b><span>thu về, chọn ngẫu nhiên</span></div>`;
    bookChart($('book-chart'), b);
    $('book-note').textContent = `Biểu đồ mô phỏng ${b.weeks} tuần gần nhất, mỗi tuần 10 vé, bình quân ${b.sims} lần chạy, chỉ tính giải cố định. Thu về khoảng ${pct(b.filter_pct)} với bộ số đã lọc và ${pct(b.random_pct)} với chọn ngẫu nhiên. Chênh lệch này chủ yếu do vài vé trúng giải nhất: trên toàn bộ lịch sử, tỷ lệ vé trúng từ giải ba trở lên là ${pct(b.full_filter_win_pct, 2)} so với ${pct(b.full_random_win_pct, 2)}, kỳ vọng ${pct(b.full_theory_win_pct, 2)}. Bộ lọc không làm tăng khả năng trúng, chỉ giảm rủi ro phải chia giải nếu trúng.`;
    $('book-log').innerHTML = '<table><thead><tr><th>Kỳ</th><th>Trò chơi</th><th>Ngày</th><th>Nhận định</th><th>Giá trị vé</th><th>Vé</th><th>Thu về</th></tr></thead><tbody>' +
      p.log.map((e) => `<tr><td>${e.id}</td><td>${names[e.game]}</td><td>${dmy(e.date)}</td><td>${esc(e.verdict)}</td><td>${pct(e.ev_pct)}</td><td>${e.tickets.length}</td><td>${e.status === 'done' ? money(e.returned) : 'Chờ kết quả'}</td></tr>`).join('') + '</tbody></table>';

    $('method').innerHTML = `<p><b>Giá trị kỳ vọng</b> là số tiền bình quân một vé thu về, tính bằng xác suất từng giải nhân với tiền thực nhận. Jackpot trừ khả năng phải chia giải, giả định người chơi chọn số đều.</p>
      <p><b>Xác suất</b> trên một bộ số: jackpot Mega 1/${fmt(d.odds.mega.jp)}, Jackpot 1 Power 1/${fmt(d.odds.power.jp)}, Jackpot 2 Power 1/${fmt(d.odds.power.j2)}.</p>
      <p><b>Thuế</b> tính 10% trên phần giải vượt 20 triệu đồng, theo Luật Thuế TNCN có hiệu lực từ 01/07/2026.</p>
      <p><b>Vé bán ước tính</b> suy từ số người trúng giải ba của các kỳ gần đây. <b>Jackpot ước tính</b> bằng mức hiện tại cộng phần tích lũy bình quân trên mỗi vé.</p>
      <p><b>Ngưỡng nhận định</b> do trang đặt ra: dưới ${d.rules.light_pct}% nghỉ, từ ${d.rules.light_pct}% chơi nhẹ ${d.rules.light_tickets} vé, từ ${d.rules.play_pct}% chơi ${d.rules.play_tickets} vé. Mức 100% trong bảng trên là gần đúng vì vé bán thường tăng khi jackpot cao.</p>
      <p><b>Bộ số đã lọc</b> tránh dãy liên tiếp, số tập trung dưới 31 (ngày sinh), số cùng đuôi và số lặp kỳ trước. Đây là chọn ngẫu nhiên có lọc, không phải số dự đoán.</p>
      <p><b>Nguồn:</b> kết quả từ <a href="https://github.com/vietvudanh/vietlott-data">vietlott-data</a>, Mega từ kỳ ${t.mega.first_id}. Jackpot và số người trúng từ <a href="https://xosodaiphat.com/xs-mega-xo-so-mega-645.html">Xổ số Đại Phát</a>, hai nguồn được đối chiếu dãy số mỗi lần cập nhật.</p>`;
  }

  fetch('data/dashboard.json?v=' + Date.now())
    .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(render)
    .catch(() => {
      $('headline').textContent = 'Chưa tải được số liệu';
      $('commentary').innerHTML = '<p>Tải lại trang sau ít phút. Nếu vẫn lỗi, tệp số liệu đang được cập nhật.</p>';
      $('stamp').textContent = '';
    });
})();
