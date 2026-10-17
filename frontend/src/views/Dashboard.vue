<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import http from '../api'

const ov = ref<any>({})
const trendEl = ref<HTMLElement>()
const hotEl = ref<HTMLElement>()

async function load() {
  const [o, t, h] = await Promise.all([
    http.get('/stats/overview'),
    http.get('/stats/daily-trend', { params: { days: 14 } }),
    http.get('/stats/hot-questions', { params: { top_n: 8 } }),
  ])
  return { overview: (o as any).data, trend: (t as any).data, hot: (h as any).data }
}

function renderTrend(trend: any[]) {
  const chart = echarts.init(trendEl.value!)
  chart.setOption({
    title: { text: '近 14 天会话趋势', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, data: ['会话量', '转人工'] },
    grid: { top: 50, bottom: 40 },
    xAxis: { type: 'category', data: trend.map((d) => d.date.slice(5)) },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      { name: '会话量', type: 'line', smooth: true, data: trend.map((d) => d.conversations) },
      { name: '转人工', type: 'line', smooth: true, data: trend.map((d) => d.to_human) },
    ],
  })
}

function renderHot(hot: any[]) {
  const chart = echarts.init(hotEl.value!)
  chart.setOption({
    title: { text: '热门问题 Top8', left: 'center', textStyle: { fontSize: 14 } },
    grid: { top: 50, bottom: 20, left: 140 },
    xAxis: { type: 'value', minInterval: 1 },
    yAxis: {
      type: 'category',
      data: hot.map((h) => h.question).reverse(),
      axisLabel: { width: 120, overflow: 'truncate' },
    },
    series: [{ type: 'bar', data: hot.map((h) => h.count).reverse(), itemStyle: { color: '#409eff' } }],
  })
}

onMounted(async () => {
  const { overview, trend, hot } = await load()
  ov.value = overview
  await nextTick()
  renderTrend(trend)
  renderHot(hot)
})
</script>

<template>
  <div class="page">
    <el-row :gutter="16">
      <el-col :span="6">
        <el-card><div class="kpi"><div class="num">{{ ov.total_conversations ?? 0 }}</div><div class="label">总会话数</div></div></el-card>
      </el-col>
      <el-col :span="6">
        <el-card><div class="kpi"><div class="num">{{ ((ov.to_human_rate ?? 0) * 100).toFixed(1) }}%</div><div class="label">转人工率</div></div></el-card>
      </el-col>
      <el-col :span="6">
        <el-card><div class="kpi"><div class="num">{{ ((ov.ai_solved_rate ?? 0) * 100).toFixed(1) }}%</div><div class="label">AI 独立解决率</div></div></el-card>
      </el-col>
      <el-col :span="6">
        <el-card><div class="kpi"><div class="num">{{ ov.avg_rating ?? '—' }}</div><div class="label">平均满意度（暂无数据）</div></div></el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="14"><el-card><div ref="trendEl" class="chart"></div></el-card></el-col>
      <el-col :span="10"><el-card><div ref="hotEl" class="chart"></div></el-card></el-col>
    </el-row>
  </div>
</template>

<style scoped>
.page { padding: 20px; background: #f5f7fa; min-height: 100vh; }
.kpi { text-align: center; padding: 8px 0; }
.num { font-size: 30px; font-weight: 700; color: #303133; }
.label { color: #909399; font-size: 13px; margin-top: 6px; }
.chart { height: 340px; }
</style>