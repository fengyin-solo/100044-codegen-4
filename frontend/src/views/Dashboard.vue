<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览</h2>
        <p class="page-desc">汇总各业务模块的关键指标，先看总量再看异常。</p>
      </div>
    </header>
    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </article>
    </div>
    <table class="data-table">
      <thead>
        <tr><th>业务模块</th><th>今日新增</th><th>待处理</th><th>异常量</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in moduleRows" :key="row.name">
          <td>{{ moduleLabels[row.name] ?? row.name }}</td>
          <td>{{ row.created }}</td>
          <td>{{ row.pending }}</td>
          <td>{{ row.abnormal }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchJson } from '@/api/client'

type Overview = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
}

const cards = ref<Overview['cards']>([])
const moduleRows = ref<Overview['modules']>([])

// 概览接口返回的是后端表名，这里统一翻成中文模块名；新增培训模块的两张表也收进来。
const moduleLabels: Record<string, string> = {
  plant: '厂区单元',
  inflow: '进水监测',
  effluent: '出水监测',
  aeration: '曝气控制',
  dosing: '加药管理',
  sludge: '污泥处置',
  dewater: '脱水运行',
  pump: '泵站运行',
  blower: '鼓风机组',
  membrane: '膜组件',
  online: '在线仪表',
  sample: '取样检测',
  chemical: '药剂出入',
  energy: '能耗管理',
  alarm: '报警中心',
  maint: '设备检修',
  permit: '受限空间作业',
  audit: '达标审核',
  position_rule: '岗位培训计划',
  staff: '员工持证档案',
}

onMounted(async () => {
  try {
    const payload = await fetchJson<Overview>('/api/overview')
    cards.value = payload.cards
    moduleRows.value = payload.modules
  } catch {
    cards.value = [{"label": "业务模块", "value": 0}, {"label": "今日新增", "value": 0}]
    moduleRows.value = [{"name": "厂区单元", "created": 0, "pending": 0, "abnormal": 0}, {"name": "进水监测", "created": 0, "pending": 0, "abnormal": 0}, {"name": "出水监测", "created": 0, "pending": 0, "abnormal": 0}, {"name": "曝气控制", "created": 0, "pending": 0, "abnormal": 0}, {"name": "加药管理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "污泥处置", "created": 0, "pending": 0, "abnormal": 0}, {"name": "脱水运行", "created": 0, "pending": 0, "abnormal": 0}, {"name": "泵站运行", "created": 0, "pending": 0, "abnormal": 0}, {"name": "鼓风机组", "created": 0, "pending": 0, "abnormal": 0}, {"name": "膜组件", "created": 0, "pending": 0, "abnormal": 0}, {"name": "在线仪表", "created": 0, "pending": 0, "abnormal": 0}, {"name": "取样检测", "created": 0, "pending": 0, "abnormal": 0}, {"name": "药剂出入", "created": 0, "pending": 0, "abnormal": 0}, {"name": "能耗管理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "报警中心", "created": 0, "pending": 0, "abnormal": 0}, {"name": "设备检修", "created": 0, "pending": 0, "abnormal": 0}, {"name": "受限空间作业", "created": 0, "pending": 0, "abnormal": 0}, {"name": "达标审核", "created": 0, "pending": 0, "abnormal": 0}]
  }
})
</script>
