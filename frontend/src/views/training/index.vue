<template>
  <section class="page" data-module="training">
    <header class="page-head">
      <div>
        <h2>员工培训与持证上岗</h2>
        <p class="page-desc">按岗位规则维护培训计划与证书台账，证书到期前按阈值提醒，到期当天与超期按不同口径判定上岗资格。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="toggleImport">批量导入员工</button>
        <button class="btn" type="button" @click="exportRows">导出培训档案清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <div v-if="reminders.length" class="reminder-banner">
      <strong>证书到期提醒（{{ reminders.length }}）：</strong>
      <span
        v-for="item in reminders"
        :key="`${item.员工编号}-${item.证书名称}`"
        class="reminder-item"
        :class="{ urgent: item.提醒等级 === '今日到期' }"
      >
        {{ item.姓名 }}·{{ item.证书名称 }}{{ item.剩余天数 === 0 ? '今日到期' : `剩余${item.剩余天数}天` }}
      </span>
    </div>

    <div v-if="importOpen" class="import-panel">
      <p class="import-hint">
        每行一名员工，字段顺序：员工编号,姓名,岗位,证书名称,证书编号,有效期至（YYYY-MM-DD）。
        重复人员、证书缺失、日期格式不合法会逐条给出原因；已存在的员工编号只拒绝不覆盖。
      </p>
      <textarea
        v-model="importText"
        rows="5"
        class="import-input"
        placeholder="EMP-1001,王五,电工,低压电工证,DQ-2026-001,2027-05-01"
      ></textarea>
      <div class="import-actions">
        <button class="btn primary" type="button" @click="submitImport">提交导入</button>
        <button class="btn ghost" type="button" @click="toggleImport">收起</button>
        <span v-if="importMessage" class="import-message">{{ importMessage }}</span>
      </div>
      <table v-if="importResults.length" class="data-table import-result">
        <thead>
          <tr><th>行号</th><th>员工编号</th><th>结果</th><th>原因</th></tr>
        </thead>
        <tbody>
          <tr v-for="result in importResults" :key="result.行号">
            <td>{{ result.行号 }}</td>
            <td>{{ result.员工编号 || '—' }}</td>
            <td>{{ result.ok ? '成功' : '失败' }}</td>
            <td>{{ result.原因 || '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>员工编号 / 姓名</span>
        <input v-model="filters.keyword" placeholder="按员工编号或姓名检索" />
      </label>
      <label class="filter-item">
        <span>岗位</span>
        <select v-model="filters.position">
          <option value="">全部岗位</option>
          <option v-for="rule in rules" :key="rule.岗位" :value="rule.岗位">{{ rule.岗位 }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>资格状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            <span v-if="column === '资格状态'" class="tag" :class="statusClass(row[column])">{{ row[column] }}</span>
            <span v-else-if="column === '上岗资格'" class="tag" :class="row[column] === '可上岗' ? 'tag-ok' : 'tag-bad'">{{ row[column] }}</span>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">证书与培训</button>
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无员工培训档案，可先批量导入员工</td>
        </tr>
      </tbody>
    </table>

    <div v-if="detail" class="detail-panel">
      <header class="detail-head">
        <strong>{{ detail.姓名 }}（{{ detail.员工编号 }} · {{ detail.岗位 }}）</strong>
        <span class="tag" :class="statusClass(detail.资格状态)">{{ detail.资格状态 }}</span>
        <span class="tag" :class="detail.上岗资格 === '可上岗' ? 'tag-ok' : 'tag-bad'">{{ detail.上岗资格 }}</span>
        <button class="link" type="button" @click="detail = null">收起</button>
      </header>
      <div class="detail-grid">
        <div>
          <h3 class="detail-title">证书列表</h3>
          <table class="data-table">
            <thead>
              <tr><th>证书名称</th><th>证书编号</th><th>有效期至</th><th>剩余天数</th><th>证书状态</th></tr>
            </thead>
            <tbody>
              <tr v-for="cert in detail.证书列表" :key="cert.证书编号 || cert.证书名称">
                <td>{{ cert.证书名称 }}</td>
                <td>{{ cert.证书编号 || '—' }}</td>
                <td>{{ cert.有效期至 }}</td>
                <td>{{ cert.剩余天数 ?? '—' }}</td>
                <td><span class="tag" :class="statusClass(cert.证书状态)">{{ cert.证书状态 }}</span></td>
              </tr>
              <tr v-if="!detail.证书列表?.length">
                <td colspan="5" class="empty-state">暂无证书记录</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div>
          <h3 class="detail-title">培训计划</h3>
          <table class="data-table">
            <thead>
              <tr><th>计划名称</th><th>计划日期</th><th>计划状态</th></tr>
            </thead>
            <tbody>
              <tr v-for="plan in detail.培训计划" :key="plan.计划名称">
                <td>{{ plan.计划名称 }}</td>
                <td>{{ plan.计划日期 }}</td>
                <td>{{ plan.计划状态 }}</td>
              </tr>
              <tr v-if="!detail.培训计划?.length">
                <td colspan="3" class="empty-state">暂无培训计划，可点击“生成培训计划”</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <footer class="page-foot">
      <span>共 {{ total }} 条员工培训档案</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span v-else-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, any>

const ENDPOINT = '/api/training'
const columns = ["员工编号", "姓名", "岗位", "必备证书", "最近到期日", "剩余天数", "资格状态", "上岗资格"]
const actions = ["生成培训计划", "完成培训"]
const statuses = ["持证有效", "临期提醒", "今日到期", "已超期", "证书缺失"]

const rows = ref<Row[]>([])
const total = ref(0)
const stats = ref([
  { label: '持证有效', value: 0 },
  { label: '临期提醒', value: 0 },
  { label: '今日到期', value: 0 },
  { label: '不可上岗', value: 0 },
])
const reminders = ref<Row[]>([])
const rules = ref<Row[]>([])
const detail = ref<Row | null>(null)
const filters = ref({ keyword: '', position: '', status: '' })
const errorMessage = ref('')
const noticeMessage = ref('')
const importOpen = ref(false)
const importText = ref('')
const importMessage = ref('')
const importResults = ref<Row[]>([])

function statusClass(status: unknown): string {
  switch (status) {
    case '持证有效':
      return 'tag-ok'
    case '临期提醒':
      return 'tag-warn'
    case '今日到期':
      return 'tag-today'
    default:
      return 'tag-bad'
  }
}

function toggleImport() {
  importOpen.value = !importOpen.value
  if (!importOpen.value) {
    importMessage.value = ''
    importResults.value = []
  }
}

function resetFilters() {
  filters.value = { keyword: '', position: '', status: '' }
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error('员工档案明细读取失败')
    }
    detail.value = await response.json()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '员工档案明细读取失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      throw new Error(payload.message || '员工培训动作未生效，请稍后重试')
    }
    noticeMessage.value = payload.message || '操作完成'
    await reload()
    if (detail.value && detail.value.id === row.id) {
      await openDetail(row)
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '员工培训操作失败'
  }
}

async function submitImport() {
  errorMessage.value = ''
  importMessage.value = ''
  importResults.value = []
  const lines = importText.value.split('\n').map((line) => line.trim()).filter(Boolean)
  if (!lines.length) {
    importMessage.value = '请先粘贴要导入的员工行'
    return
  }
  try {
    const response = await request(`${ENDPOINT}/import`, {
      method: 'POST',
      body: JSON.stringify({ rows: lines }),
    })
    const payload = await response.json()
    importMessage.value = payload.message || '导入已处理'
    importResults.value = payload.results ?? []
    await reload()
  } catch (error) {
    importMessage.value = error instanceof Error ? error.message : '批量导入失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (filters.value.keyword) query.set('keyword', filters.value.keyword)
  if (filters.value.position) query.set('position', filters.value.position)
  if (filters.value.status) query.set('status', filters.value.status)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('员工培训档案列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    await Promise.all([loadStats(), loadReminders()])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '员工培训档案列表读取失败'
  }
}

async function loadStats() {
  try {
    const response = await request(`${ENDPOINT}/stats`)
    if (!response.ok) return
    const payload = await response.json()
    stats.value = [
      { label: '持证有效', value: payload['持证有效'] ?? 0 },
      { label: '临期提醒', value: payload['临期提醒'] ?? 0 },
      { label: '今日到期', value: payload['今日到期'] ?? 0 },
      { label: '不可上岗', value: (payload['已超期'] ?? 0) + (payload['证书缺失'] ?? 0) },
    ]
  } catch {
    // 统计卡片读取失败时保留上一次数值
  }
}

async function loadReminders() {
  try {
    const response = await request(`${ENDPOINT}/reminders`)
    if (!response.ok) return
    const payload = await response.json()
    reminders.value = payload.items ?? []
  } catch {
    reminders.value = []
  }
}

async function loadRules() {
  try {
    const response = await request(`${ENDPOINT}/rules`)
    if (!response.ok) return
    const payload = await response.json()
    rules.value = payload.items ?? []
  } catch {
    rules.value = []
  }
}

onMounted(() => {
  void reload()
  void loadRules()
})
</script>

<style scoped>
.reminder-banner {
  background: #fff8e6;
  border: 1px solid #f0c36d;
  border-radius: 8px;
  padding: 8px 12px;
  margin-bottom: 12px;
  font-size: 13px;
}
.reminder-item {
  display: inline-block;
  margin: 2px 8px 2px 0;
  color: #8a5a00;
}
.reminder-item.urgent {
  color: #b42318;
  font-weight: 600;
}
.import-panel {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}
.import-hint {
  margin: 0 0 8px;
  font-size: 12px;
  color: var(--muted);
}
.import-input {
  width: 100%;
  font-family: inherit;
  font-size: 13px;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px;
  resize: vertical;
}
.import-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 8px;
}
.import-message {
  font-size: 12px;
  color: var(--muted);
}
.import-result {
  margin-top: 8px;
}
.detail-panel {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  margin-top: 12px;
}
.detail-head {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 8px;
}
.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.detail-title {
  font-size: 13px;
  margin: 4px 0 6px;
}
.tag {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 12px;
}
.tag-ok {
  background: #e7f6ec;
  color: #157347;
}
.tag-warn {
  background: #fff3cd;
  color: #8a5a00;
}
.tag-today {
  background: #ffe8d6;
  color: #b34700;
}
.tag-bad {
  background: #fdecea;
  color: #b42318;
}
.notice-text {
  color: #157347;
}
</style>
