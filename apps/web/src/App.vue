<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { calculate, getCalculation, getHistory, getModels } from './api';
import { millions, money, moneyRate } from './money';
import type { HistoryEntry, Model, Summary } from './types';

const SST_PCT = 6;

const models = ref<Model[]>([]);
const usage = ref<Record<string, string>>({});
const batch = ref(false);
const summary = ref<Summary | null>(null);
const history = ref<HistoryEntry[]>([]);

const loading = ref(true);
const busy = ref(false);
const online = ref(true);
const loadError = ref('');
const formError = ref('');
const stale = ref(false);

const factor = computed(() => (batch.value ? 0.5 : 1));
const entries = computed(() =>
  models.value
    .map((m) => ({ modelId: m.id, tokensMillions: parseFloat(usage.value[m.id] ?? '') }))
    .filter((e) => e.tokensMillions > 0),
);

// Editing inputs or the batch toggle makes the shown summary out of date.
watch([usage, batch], () => { if (summary.value) stale.value = true; }, { deep: true });

async function loadHistory() {
  try { history.value = await getHistory(); } catch { /* history is non-critical */ }
}

onMounted(async () => {
  try {
    models.value = (await getModels()).models;
  } catch (e) {
    online.value = false;
    loadError.value = (e as Error).message || 'Could not reach the gateway API.';
  } finally {
    loading.value = false;
  }
  loadHistory();
});

async function onCalculate() {
  formError.value = '';
  if (entries.value.length === 0) {
    summary.value = null;
    formError.value = 'No usage entered — add tokens to at least one model.';
    return;
  }
  busy.value = true;
  try {
    summary.value = await calculate(batch.value, entries.value);
    stale.value = false;
    loadHistory();
  } catch (e) {
    formError.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}

function onReset() {
  usage.value = {};
  batch.value = false;
  summary.value = null;
  formError.value = '';
  stale.value = false;
}

async function openHistory(id: string) {
  try {
    const s = await getCalculation(id);
    summary.value = s;
    batch.value = s.batch;
    usage.value = Object.fromEntries(s.items.map((i) => [i.modelId, String(i.tokensMillions)]));
    stale.value = false;
    formError.value = '';
  } catch (e) {
    formError.value = (e as Error).message;
  }
}

const when = (iso: string) =>
  new Date(iso).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
</script>

<template>
  <div class="shell">
    <div class="topbar">
      <span><span class="tri" aria-hidden="true"></span>ai-gateway / usage</span>
      <span class="status" :class="{ off: !online }">{{ online ? `${models.length} models online` : 'api unreachable' }}</span>
    </div>

    <h1>Calculate your<br>gateway usage.</h1>
    <p class="lede">Enter total tokens (in millions) consumed per model. Get an itemised summary and the final amount payable, SST included.</p>

    <form novalidate @submit.prevent="onCalculate" @reset.prevent="onReset">
      <section class="box" aria-labelledby="models-h">
        <div class="box-head">
          <h2 id="models-h">Models</h2>
          <label class="toggle">
            <input v-model="batch" type="checkbox" />
            <span class="sw" aria-hidden="true"></span>
            Batch API <span class="tag" :class="{ on: batch }">−50%</span>
          </label>
        </div>

        <div v-if="loading" class="skeleton">loading models…</div>
        <div v-else-if="loadError" class="notice err">{{ loadError }}</div>

        <div v-else role="table" aria-label="Model pricing and usage">
          <div v-for="(m, i) in models" :key="m.id" class="row" role="row">
            <span class="idx">{{ String(i + 1).padStart(2, '0') }}</span>
            <label :for="m.id" class="name">{{ m.name }}<em>{{ m.provider }} · {{ m.description }}</em></label>
            <span class="rate"><span :class="{ batch }">{{ moneyRate(m.priceCents * factor) }}</span><i>/1M</i></span>
            <div class="field">
              <input
                :id="m.id" v-model="usage[m.id]" type="number" min="0" step="any" inputmode="decimal" placeholder="0"
                :aria-label="`${m.name} usage in millions of tokens`"
              />
              <span class="unit">M</span>
            </div>
          </div>
        </div>

        <div class="actions">
          <button type="submit" class="primary" :disabled="busy || loading || !!loadError">
            {{ busy ? 'Calculating…' : 'Calculate Usage' }}
          </button>
          <button type="reset" class="ghost">Reset</button>
        </div>
      </section>
    </form>

    <section class="box" aria-labelledby="sum-h" aria-live="polite">
      <div class="box-head">
        <h2 id="sum-h">Summary</h2>
        <span class="tag">SST {{ SST_PCT }}%</span>
      </div>

      <div v-if="formError" class="notice warn">! {{ formError }}</div>

      <template v-if="summary">
        <div v-if="stale" class="notice stale">Inputs changed — press Calculate Usage to refresh this summary.</div>
        <div class="lines">
          <div v-for="it in summary.items" :key="it.modelId" class="line">
            <span class="l-name">{{ it.name }}</span>
            <span class="l-meta">
              {{ it.provider }}<span class="sep">/</span>{{ millions(it.tokensMillions) }} M<span class="sep">×</span>{{ moneyRate(it.unitPriceCents) }} / 1M
            </span>
            <span class="cost">{{ money(it.costCents) }}</span>
          </div>
        </div>
        <dl class="totals">
          <div><dt>List price</dt><dd>{{ money(summary.listCents) }}</dd></div>
          <div v-if="summary.batch" class="save"><dt>Batch discount (50%)</dt><dd>−{{ money(summary.discountCents) }}</dd></div>
          <div><dt>Subtotal</dt><dd>{{ money(summary.subtotalCents) }}</dd></div>
          <div><dt>SST ({{ SST_PCT }}%)</dt><dd>{{ money(summary.sstCents) }}</dd></div>
          <div class="grand"><dt>Total to pay</dt><dd>{{ money(summary.totalCents) }}</dd></div>
        </dl>
      </template>
      <div v-else-if="!formError" class="skeleton">Fill in usage and press Calculate Usage.</div>
    </section>

    <section v-if="history.length" class="box" aria-labelledby="hist-h">
      <div class="box-head"><h2 id="hist-h">Recent calculations</h2></div>
      <ul class="history">
        <li v-for="h in history" :key="h.id">
          <button type="button" @click="openHistory(h.id)">
            <span>{{ when(h.createdAt) }}</span>
            <span>{{ h.itemCount }} model{{ h.itemCount === 1 ? '' : 's' }}{{ h.batch ? ' · batch' : '' }}</span>
            <span class="t">{{ money(h.totalCents) }}</span>
          </button>
        </li>
      </ul>
    </section>
  </div>
</template>
