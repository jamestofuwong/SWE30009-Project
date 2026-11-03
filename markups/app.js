/*
 * Shared behaviour for all three AI Gateway markups.
 * The markups only differ in HTML/CSS; they follow the same hooks:
 *   form#calc                  – wraps the model inputs + buttons
 *   input[data-model]          – usage input (in millions of tokens), data-name / data-provider / data-price
 *   input#batch                – batch API toggle (50% off)
 *   [data-rate][data-base]     – price labels that update when batch is toggled
 *   #results, #empty           – summary container / "nothing entered" message
 *   template#row-tpl           – one summary row, filled via [data-field="name|provider|usage|rate|cost"]
 *   #rows, #list-subtotal, #discount-row, #discount, #subtotal, #sst, #total
 */
(function () {
  'use strict';

  var SST_RATE = 0.06;
  var BATCH_DISCOUNT = 0.5;

  var $ = function (sel) { return document.querySelector(sel); };
  var money = function (n, min, max) {
    return new Intl.NumberFormat('en-US', {
      style: 'currency', currency: 'USD',
      minimumFractionDigits: min == null ? 2 : min,
      maximumFractionDigits: max == null ? 2 : max
    }).format(n);
  };
  var cents = function (n) { return Math.round(n * 100) / 100; };

  var form = $('#calc');
  var batch = $('#batch');
  var results = $('#results');
  var empty = $('#empty');
  var inputs = Array.prototype.slice.call(document.querySelectorAll('input[data-model]'));
  var calculated = false;

  function factor() { return batch.checked ? 1 - BATCH_DISCOUNT : 1; }

  function renderRates() {
    document.documentElement.setAttribute('data-batch', batch.checked ? 'on' : 'off');
    document.querySelectorAll('[data-rate]').forEach(function (el) {
      el.textContent = money(parseFloat(el.dataset.base) * factor(), 2, 3);
    });
  }

  function calculate() {
    var f = factor();
    var rows = $('#rows');
    rows.innerHTML = '';
    var list = 0, subtotal = 0;

    inputs.forEach(function (input) {
      var usage = parseFloat(input.value);
      if (!(usage > 0)) return;
      var base = parseFloat(input.dataset.price);
      var rate = base * f;
      var cost = cents(usage * rate);
      list += cents(usage * base);
      subtotal += cost;

      var node = $('#row-tpl').content.cloneNode(true);
      var set = function (k, v) { node.querySelector('[data-field="' + k + '"]').textContent = v; };
      set('name', input.dataset.name);
      set('provider', input.dataset.provider);
      set('usage', usage.toLocaleString('en-US', { maximumFractionDigits: 3 }) + ' M');
      set('rate', money(rate, 2, 3) + ' / 1M');
      set('cost', money(cost));
      rows.appendChild(node);
    });

    var hasUsage = subtotal > 0 || rows.children.length > 0;
    results.hidden = !hasUsage;
    empty.hidden = hasUsage;
    if (!hasUsage) return;

    var discount = cents(list - subtotal);
    var sst = cents(subtotal * SST_RATE);
    $('#list-subtotal').textContent = money(list);
    $('#discount').textContent = '−' + money(discount);
    $('#discount-row').hidden = !batch.checked;
    $('#subtotal').textContent = money(subtotal);
    $('#sst').textContent = money(sst);
    $('#total').textContent = money(cents(subtotal + sst));
    results.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    calculated = true;
    calculate();
  });

  form.addEventListener('reset', function () {
    calculated = false;
    // let the browser clear the fields first, then refresh the dependent UI
    setTimeout(function () {
      results.hidden = true;
      empty.hidden = true;
      renderRates();
    }, 0);
  });

  batch.addEventListener('change', function () {
    renderRates();
    if (calculated) calculate(); // keep an open summary in sync with the toggle
  });

  renderRates();
})();
