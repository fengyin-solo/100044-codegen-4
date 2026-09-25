<template>
  <section class="page" data-module="training">
    <header class="page-head">
      <div>
        <h2>员工培训与持证上岗</h2>
        <p class="page-desc">
          按岗位维护培训计划，证书到期前按阈值提醒；到期当天与超期按不同口径区分上岗资格。
          资格状态每次进入都按当天日期现算，与证书列表保持一致。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="exportRows">导出现筛档案</button>
      </div>
    </header>

    <div class="tab-bar">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab"
        :class="{ active: activeTab === tab.key }"
        type="button"
        @click="switchTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- 持证看板 + 档案 -->
    <template v-if="activeTab === 'staff'">
      <div class="stat-row">
        <article v-for="item in statCards" :key="item.label" class="stat-card">
          <span class="stat-label">{{ item.label }}</span>
          <strong class="stat-value" :class="item.cls">{{ item.value }}</strong>
        </article>
      </div>

      <form class="filter-bar" @submit.prevent="reloadStaff">
        <label class="filter-item">
          <span>工号/姓名</span>
          <input v-model="filters.keyword" placeholder="按工号或姓名检索" />
        </label>
        <label class="filter-item">
          <span>岗位</span>
          <select v-model="filters.position">
            <option value="">全部岗位</option>
            <option v-for="rule in rules" :key="String(rule.id)" :value="String(rule.岗位名称)">{{ rule.岗位名称 }}</option>
          </select>
        </label>
        <label class="filter-item">
          <span>资格口径</span>
          <select v-model="filters.caliber">
            <option value="">全部口径</option>
            <option v-for="caliber in calibers" :key="caliber" :value="caliber">{{ caliber }}</option>
          </select>
        </label>
        <button class="btn" type="submit">查询</button>
        <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
        <button class="btn primary" type="button" @click="openStaffForm">登记单个员工</button>
        <button class="btn primary" type="button" @click="openImport">批量导入</button>
      </form>

      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in staffColumns" :key="column">{{ column }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in staffRows" :key="String(row.id)">
            <td v-for="column in staffColumns" :key="column">
              <span v-if="column === '资格口径'" class="badge" :class="caliberClass(row.资格口径)">{{ row.资格口径 }}</span>
              <span v-else-if="column === '持证上岗'">{{ row.持证上岗 ? '可上岗' : '不可上岗' }}</span>
              <span v-else-if="column === '距到期天数'">{{ row.距到期天数 === null ? '—' : `${row.距到期天数} 天` }}</span>
              <span v-else>{{ row[column] ?? '—' }}</span>
            </td>
          </tr>
          <tr v-if="!staffRows.length">
            <td :colspan="staffColumns.length" class="empty-state">暂无符合条件的持证档案，可单条登记或批量导入</td>
          </tr>
        </tbody>
      </table>
      <footer class="page-foot">
        <span>共 {{ staffTotal }} 条员工持证档案（资格状态按当天 {{ todayLabel }} 现算）</span>
        <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      </footer>
    </template>

    <!-- 到期提醒 -->
    <template v-else-if="activeTab === 'reminder'">
      <form class="filter-bar" @submit.prevent="reloadReminders">
        <label class="filter-item">
          <span>只看口径</span>
          <select v-model="reminderScope">
            <option value="">全部需关注</option>
            <option v-for="caliber in calibers" :key="caliber" :value="caliber">{{ caliber }}</option>
          </select>
        </label>
        <button class="btn" type="submit">刷新提醒</button>
      </form>
      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in reminderColumns" :key="column">{{ column }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in reminderRows" :key="String(row.id)">
            <td v-for="column in reminderColumns" :key="column">
              <span v-if="column === '资格口径'" class="badge" :class="caliberClass(row.资格口径)">{{ row.资格口径 }}</span>
              <span v-else-if="column === '距到期天数'">{{ row.距到期天数 === null ? '—' : `${row.距到期天数} 天` }}</span>
              <span v-else>{{ row[column] ?? '—' }}</span>
            </td>
          </tr>
          <tr v-if="!reminderRows.length">
            <td :colspan="reminderColumns.length" class="empty-state">当前没有需要关注的证书</td>
          </tr>
        </tbody>
      </table>
    </template>

    <!-- 岗位培训计划 -->
    <template v-else>
      <form class="filter-bar" @submit.prevent="reloadRules">
        <label class="filter-item">
          <span>岗位名称</span>
          <input v-model="ruleKeyword" placeholder="按岗位名称检索" />
        </label>
        <button class="btn" type="submit">查询</button>
        <button class="btn primary" type="button" @click="openRuleForm()">新增岗位规则</button>
      </form>
      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in ruleColumns" :key="column">{{ column }}</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="rule in rules" :key="String(rule.id)">
            <td v-for="column in ruleColumns" :key="column">{{ rule[column] ?? '—' }}</td>
            <td class="row-actions">
              <button class="link" type="button" @click="openRuleForm(rule)">编辑阈值/计划</button>
              <button class="link" type="button" @click="toggleRule(rule)">
                {{ rule.启用状态 === '启用' ? '停用' : '启用' }}
              </button>
            </td>
          </tr>
          <tr v-if="!rules.length">
            <td :colspan="ruleColumns.length + 1" class="empty-state">暂无岗位培训规则，可先新增</td>
          </tr>
        </tbody>
      </table>
      <footer class="page-foot">
        <span>培训周期与到期提醒阈值改完立即生效；员工资格口径随阈值重新计算。</span>
        <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      </footer>
    </template>

    <!-- 批量导入弹层 -->
    <div v-if="importOpen" class="modal-mask" @click.self="importOpen = false">
      <div class="modal modal-wide">
        <h3>批量导入员工持证档案</h3>
        <p class="modal-hint">
          每行一名员工，列顺序：工号、姓名、岗位名称、所属部门、证书名称、发证机构、发证日期、到期日期、备注。
          用 Tab 或逗号分隔；日期必须为 <code>YYYY-MM-DD</code>；可粘贴含表头的第一行。
          重复人员、证书缺失、日期不合法都会逐行给出原因，且不会覆盖任何既有记录。
        </p>
        <textarea v-model="importText" class="import-area" rows="9" :placeholder="importPlaceholder"></textarea>
        <div class="modal-actions">
          <button class="btn" type="button" @click="parsePreview">解析预览</button>
          <button class="btn primary" type="button" :disabled="!parsedRows.length" @click="submitImport">
            提交导入（{{ parsedRows.length }} 行）
          </button>
          <button class="btn ghost" type="button" @click="importOpen = false">关闭</button>
        </div>
        <div v-if="parseError" class="error-text">{{ parseError }}</div>
        <table v-if="previewRows.length" class="data-table preview-table">
          <thead>
            <tr><th>行</th><th>工号</th><th>姓名</th><th>岗位名称</th><th>证书名称</th><th>到期日期</th><th>预览结果</th></tr>
          </thead>
          <tbody>
            <tr v-for="item in previewRows" :key="item.line">
              <td>{{ item.line }}</td>
              <td>{{ item.row.工号 || '—' }}</td>
              <td>{{ item.row.姓名 || '—' }}</td>
              <td>{{ item.row.岗位名称 || '—' }}</td>
              <td>{{ item.row.证书名称 || '—' }}</td>
              <td>{{ item.row.到期日期 || '—' }}</td>
              <td class="error-text">{{ item.issue || '可提交' }}</td>
            </tr>
          </tbody>
        </table>
        <div v-if="importResult" class="import-result">
          <p :class="importResult.failed_count ? 'error-text' : 'ok-text'">{{ importResult.message }}</p>
          <table class="data-table preview-table">
            <thead>
              <tr><th>行</th><th>工号</th><th>结果</th><th>原因</th></tr>
            </thead>
            <tbody>
              <tr v-for="item in importResult.results" :key="item.line">
                <td>{{ item.line }}</td>
                <td>{{ item.工号 || '—' }}</td>
                <td>
                  <span class="badge" :class="item.ok ? 'caliber-valid' : 'caliber-expired'">
                    {{ item.ok ? '已入库' : '被拒绝' }}
                  </span>
                </td>
                <td class="error-text">{{ item.reasons.join('；') || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- 单条员工登记表单 -->
    <div v-if="staffFormOpen" class="modal-mask" @click.self="staffFormOpen = false">
      <div class="modal">
        <h3>登记员工持证档案</h3>
        <div class="form-grid">
          <label v-for="field in staffFormFields" :key="field" class="form-item">
            <span>{{ field }}</span>
            <input v-model="staffForm[field]" :placeholder="field === '到期日期' ? 'YYYY-MM-DD' : ''" />
          </label>
        </div>
        <div v-if="formError" class="error-text">{{ formError }}</div>
        <div class="modal-actions">
          <button class="btn primary" type="button" @click="submitStaffForm">保存</button>
          <button class="btn ghost" type="button" @click="staffFormOpen = false">取消</button>
        </div>
      </div>
    </div>

    <!-- 岗位规则表单 -->
    <div v-if="ruleFormOpen" class="modal-mask" @click.self="ruleFormOpen = false">
      <div class="modal">
        <h3>{{ ruleForm.id ? '编辑岗位培训规则' : '新增岗位培训规则' }}</h3>
        <div class="form-grid">
          <label class="form-item">
            <span>岗位名称{{ ruleForm.id ? '（不可改）' : '' }}</span>
            <input v-model="ruleForm.岗位名称" :disabled="!!ruleForm.id" placeholder="如：中控运行工" />
          </label>
          <label class="form-item">
            <span>岗位类别</span>
            <input v-model="ruleForm.岗位类别" placeholder="如：运行 / 化验 / 安全" />
          </label>
          <label class="form-item">
            <span>必备证书</span>
            <input v-model="ruleForm.必备证书" placeholder="该岗位上岗必须持有的证书" />
          </label>
          <label class="form-item">
            <span>培训周期（月）</span>
            <input v-model="ruleForm.培训周期月" type="number" min="1" max="60" />
          </label>
          <label class="form-item">
            <span>提前提醒天数（阈值）</span>
            <input v-model="ruleForm.提前提醒天数" type="number" min="1" max="365" />
          </label>
          <label class="form-item">
            <span>启用状态</span>
            <select v-model="ruleForm.启用状态">
              <option>启用</option>
              <option>停用</option>
            </select>
          </label>
          <label class="form-item form-wide">
            <span>备注</span>
            <input v-model="ruleForm.备注" placeholder="如：仅用于资格提示，不改变作业许可里监护人的填写方式" />
          </label>
        </div>
        <div v-if="formError" class="error-text">{{ formError }}</div>
        <div class="modal-actions">
          <button class="btn primary" type="button" @click="submitRuleForm">保存</button>
          <button class="btn ghost" type="button" @click="ruleFormOpen = false">取消</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type StaffRow = Record<string, string | number | boolean | null>
type RuleRow = Record<string, string | number | null>
type ImportLine = { line: number; row: Record<string, string>; issue: string }

const API = '/api/training'

const calibers = ['持证有效', '即将到期', '今日到期', '已超期', '证书缺失', '岗位未配置']
const staffColumns = ['工号', '姓名', '岗位名称', '所属部门', '证书名称', '发证机构', '发证日期', '到期日期', '必备证书', '资格口径', '持证上岗', '距到期天数', '提醒说明']
const reminderColumns = ['工号', '姓名', '岗位名称', '证书名称', '到期日期', '资格口径', '距到期天数', '提醒说明']
const ruleColumns = ['岗位名称', '岗位类别', '必备证书', '培训周期月', '提前提醒天数', '启用状态', '备注']
const staffFormFields = ['工号', '姓名', '岗位名称', '所属部门', '证书名称', '发证机构', '发证日期', '到期日期', '备注']

const tabs = [
  { key: 'staff', label: '持证档案与资格' },
  { key: 'reminder', label: '到期提醒' },
  { key: 'rules', label: '岗位培训计划' },
] as const
type TabKey = (typeof tabs)[number]['key']
const activeTab = ref<TabKey>('staff')

const staffRows = ref<StaffRow[]>([])
const staffTotal = ref(0)
const reminderRows = ref<StaffRow[]>([])
const reminderScope = ref('')
const rules = ref<RuleRow[]>([])
const ruleKeyword = ref('')
const errorMessage = ref('')
const todayLabel = new Date().toISOString().slice(0, 10)

const filters = reactive({ keyword: '', position: '', caliber: '' })

const statCards = ref<{ label: string; value: number; cls: string }[]>([
  { label: '员工总数', value: 0, cls: '' },
  { label: '可上岗', value: 0, cls: 'ok-text' },
  { label: '即将到期', value: 0, cls: 'warn-text' },
  { label: '今日到期', value: 0, cls: 'warn-text' },
  { label: '已超期', value: 0, cls: 'bad-text' },
  { label: '证书缺失', value: 0, cls: 'bad-text' },
])

const caliberClass = (caliber: unknown) => {
  if (caliber === '持证有效') return 'caliber-valid'
  if (caliber === '即将到期' || caliber === '今日到期') return 'caliber-soon'
  return 'caliber-expired'
}

async function getJson(path: string) {
  const response = await request(path)
  if (!response.ok) throw new Error(`接口返回 ${response.status}`)
  return response.json()
}

async function reloadStaff() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  if (filters.keyword) params.set('keyword', filters.keyword)
  if (filters.position) params.set('position', filters.position)
  if (filters.caliber) params.set('caliber', filters.caliber)
  params.set('size', '100')
  try {
    const payload = await getJson(`${API}/staff?${params.toString()}`)
    staffRows.value = payload.items ?? []
    staffTotal.value = payload.total ?? 0
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '持证档案读取失败'
  }
}

async function reloadStats() {
  try {
    const payload = await getJson(`${API}/staff/stats`)
    const items = (payload.items ?? {}) as Record<string, number>
    statCards.value = [
      { label: '员工总数', value: items.员工总数 ?? 0, cls: '' },
      { label: '可上岗', value: items.可上岗人数 ?? 0, cls: 'ok-text' },
      { label: '即将到期', value: items.即将到期 ?? 0, cls: 'warn-text' },
      { label: '今日到期', value: items.今日到期 ?? 0, cls: 'warn-text' },
      { label: '已超期', value: items.已超期 ?? 0, cls: 'bad-text' },
      { label: '证书缺失', value: items.证书缺失 ?? 0, cls: 'bad-text' },
    ]
  } catch {
    /* 看板数字失败不阻塞档案列表 */
  }
}

async function reloadReminders() {
  const params = new URLSearchParams()
  if (reminderScope.value) params.set('scope', reminderScope.value)
  try {
    const payload = await getJson(`${API}/staff/reminders?${params.toString()}`)
    reminderRows.value = payload.items ?? []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '到期提醒读取失败'
  }
}

async function reloadRules() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  if (ruleKeyword.value) params.set('keyword', ruleKeyword.value)
  try {
    const payload = await getJson(`${API}/rules?${params.toString()}`)
    rules.value = payload.items ?? []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '岗位规则读取失败'
  }
}

function resetFilters() {
  filters.keyword = ''
  filters.position = ''
  filters.caliber = ''
  void reloadStaff()
}

function switchTab(key: TabKey) {
  activeTab.value = key
  if (key === 'rules') void reloadRules()
  if (key === 'reminder') void reloadReminders()
}

function exportRows() {
  const params = new URLSearchParams()
  if (filters.keyword) params.set('keyword', filters.keyword)
  if (filters.position) params.set('position', filters.position)
  if (filters.caliber) params.set('caliber', filters.caliber)
  window.open(`${API}/staff/export?${params.toString()}`, '_blank')
}

// --------------------------------------------------------------- 批量导入
const importOpen = ref(false)
const importText = ref('')
const parseError = ref('')
const parsedRows = ref<Record<string, string>[]>([])
const previewRows = ref<ImportLine[]>([])
const importResult = ref<null | {
  message: string
  failed_count: number
  results: { line: number; ok: boolean; 工号: string; reasons: string[] }[]
}>(null)

const importPlaceholder = [
  '工号\t姓名\t岗位名称\t所属部门\t证书名称\t发证机构\t发证日期\t到期日期',
  'TR0201\t马文\t中控运行工\t运行一值\t污水处理工证\t市人社局\t2026-01-01\t2027-01-01',
].join('\n')

const IMPORT_COLUMNS = staffFormFields
const DATE_COLUMNS = new Set(['发证日期', '到期日期'])
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/

function splitLine(line: string): string[] {
  // 优先按 Tab 切；没有 Tab 再按中英文逗号切，兼容两种粘贴来源。
  if (line.includes('\t')) return line.split('\t').map((cell) => cell.trim())
  return line.split(/[,，]/).map((cell) => cell.trim())
}

function parseImportText(): Record<string, string>[] {
  const lines = importText.value.split(/\r?\n/).map((line) => line.trim()).filter(Boolean)
  if (!lines.length) return []
  let columns = IMPORT_COLUMNS
  let body = lines
  const firstCells = splitLine(lines[0])
  if (firstCells[0] === '工号') {
    columns = firstCells
    body = lines.slice(1)
  }
  return body.map((line) => {
    const cells = splitLine(line)
    const row: Record<string, string> = {}
    columns.forEach((column, index) => {
      row[column] = cells[index] ?? ''
    })
    return row
  })
}

function localIssue(row: Record<string, string>): string {
  const issues: string[] = []
  for (const field of ['工号', '姓名', '岗位名称'] as const) {
    if (!row[field]) issues.push(`${field}为空`)
  }
  if (!row.证书名称 && !row.到期日期) issues.push('证书缺失')
  for (const field of DATE_COLUMNS) {
    const value = row[field]
    if (value && !ISO_DATE.test(value)) issues.push(`${field}格式不合法`)
  }
  return issues.join('；')
}

function parsePreview() {
  parseError.value = ''
  importResult.value = null
  parsedRows.value = parseImportText()
  if (!parsedRows.value.length) {
    parseError.value = '没有解析到任何数据行'
    previewRows.value = []
    return
  }
  const seen = new Set<string>()
  previewRows.value = parsedRows.value.map((row, index) => {
    const issues: string[] = []
    const local = localIssue(row)
    if (local) issues.push(local)
    if (row.工号) {
      if (seen.has(row.工号)) issues.push('工号在粘贴内容中重复')
      else seen.add(row.工号)
    }
    return { line: index + 1, row, issue: issues.join('；') }
  })
}

async function submitImport() {
  parseError.value = ''
  try {
    const response = await request(`${API}/staff/import`, {
      method: 'POST',
      body: JSON.stringify({ rows: parsedRows.value }),
    })
    const payload = await response.json()
    if (!response.ok) {
      parseError.value = payload.detail ?? '导入失败'
      return
    }
    importResult.value = payload
    importText.value = ''
    parsedRows.value = []
    previewRows.value = []
    await Promise.all([reloadStaff(), reloadStats(), reloadRules()])
  } catch (error) {
    parseError.value = error instanceof Error ? error.message : '导入请求失败'
  }
}

function openImport() {
  importOpen.value = true
  importText.value = ''
  parseError.value = ''
  parsedRows.value = []
  previewRows.value = []
  importResult.value = null
  void reloadRules()
}

// --------------------------------------------------------------- 单条员工
const staffFormOpen = ref(false)
const staffForm = reactive<Record<string, string>>(Object.fromEntries(staffFormFields.map((field) => [field, ''])))
const formError = ref('')

function openStaffForm() {
  staffFormFields.forEach((field) => { staffForm[field] = '' })
  formError.value = ''
  staffFormOpen.value = true
}

async function submitStaffForm() {
  formError.value = ''
  try {
    const response = await request(`${API}/staff`, {
      method: 'POST',
      body: JSON.stringify({ values: { ...staffForm } }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      formError.value = payload.message ?? '登记失败'
      return
    }
    staffFormOpen.value = false
    await Promise.all([reloadStaff(), reloadStats()])
  } catch (error) {
    formError.value = error instanceof Error ? error.message : '登记请求失败'
  }
}

// --------------------------------------------------------------- 岗位规则
const ruleFormOpen = ref(false)
const ruleForm = reactive<Record<string, string | number>>({
  id: '', 岗位名称: '', 岗位类别: '', 必备证书: '', 培训周期月: 12, 提前提醒天数: 30, 启用状态: '启用', 备注: '',
})

function openRuleForm(rule?: RuleRow) {
  formError.value = ''
  if (rule) {
    Object.assign(ruleForm, {
      id: rule.id ?? '',
      岗位名称: String(rule.岗位名称 ?? ''),
      岗位类别: String(rule.岗位类别 ?? ''),
      必备证书: String(rule.必备证书 ?? ''),
      培训周期月: Number(rule.培训周期月 ?? 12),
      提前提醒天数: Number(rule.提前提醒天数 ?? 30),
      启用状态: String(rule.启用状态 ?? '启用'),
      备注: String(rule.备注 ?? ''),
    })
  } else {
    Object.assign(ruleForm, { id: '', 岗位名称: '', 岗位类别: '', 必备证书: '', 培训周期月: 12, 提前提醒天数: 30, 启用状态: '启用', 备注: '' })
  }
  ruleFormOpen.value = true
}

async function submitRuleForm() {
  formError.value = ''
  const values: Record<string, unknown> = {
    岗位类别: ruleForm.岗位类别,
    必备证书: ruleForm.必备证书,
    培训周期月: ruleForm.培训周期月,
    提前提醒天数: ruleForm.提前提醒天数,
    启用状态: ruleForm.启用状态,
    备注: ruleForm.备注,
  }
  try {
    let response: Response
    if (ruleForm.id) {
      response = await request(`${API}/rules/${ruleForm.id}`, { method: 'PATCH', body: JSON.stringify({ values }) })
    } else {
      values.岗位名称 = ruleForm.岗位名称
      response = await request(`${API}/rules`, { method: 'POST', body: JSON.stringify({ values }) })
    }
    const payload = await response.json()
    if (!payload.ok) {
      formError.value = payload.message ?? '规则保存失败'
      return
    }
    ruleFormOpen.value = false
    await Promise.all([reloadRules(), reloadStaff(), reloadStats()])
  } catch (error) {
    formError.value = error instanceof Error ? error.message : '规则保存请求失败'
  }
}

async function toggleRule(rule: RuleRow) {
  const next = rule.启用状态 === '启用' ? '停用' : '启用'
  try {
    const response = await request(`${API}/rules/${rule.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ values: { 启用状态: next } }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      errorMessage.value = payload.message ?? '规则状态未更新'
      return
    }
    await reloadRules()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '规则状态更新失败'
  }
}

onMounted(() => {
  void Promise.all([reloadStaff(), reloadStats(), reloadRules()])
})
</script>

<style scoped>
.tab-bar { display: flex; gap: 4px; margin: 8px 0 14px; border-bottom: 1px solid var(--border); }
.tab { border: none; background: none; padding: 8px 14px; cursor: pointer; font-size: 14px; color: var(--muted); border-bottom: 2px solid transparent; }
.tab.active { color: var(--brand); border-bottom-color: var(--brand); font-weight: 600; }
.badge { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 12px; }
.caliber-valid { background: #e7f6ec; color: #15803d; }
.caliber-soon { background: #fef3e2; color: #b45309; }
.caliber-expired { background: #fdecec; color: #b42318; }
.ok-text { color: #15803d; }
.warn-text { color: #b45309; }
.bad-text { color: #b42318; }
.modal-mask { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: flex-start; justify-content: center; padding: 40px 16px; overflow: auto; z-index: 50; }
.modal { background: #fff; border-radius: 10px; padding: 18px 20px; width: 560px; max-width: 100%; }
.modal-wide { width: 860px; }
.modal h3 { margin: 0 0 8px; }
.modal-hint { color: var(--muted); font-size: 12px; line-height: 1.6; }
.modal-hint code { background: #f1f5f9; padding: 0 4px; border-radius: 4px; }
.import-area { width: 100%; font-family: ui-monospace, Menlo, monospace; font-size: 12px; padding: 8px; border: 1px solid var(--border); border-radius: 6px; }
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin: 12px 0; }
.preview-table { margin-top: 10px; font-size: 12px; }
.import-result { margin-top: 12px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 14px; }
.form-item { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
.form-item input, .form-item select { padding: 6px 8px; border: 1px solid var(--border); border-radius: 6px; font-size: 13px; color: #1f2937; }
.form-wide { grid-column: 1 / -1; }
</style>
