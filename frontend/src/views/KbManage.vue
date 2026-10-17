<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Search, UploadFilled, FolderOpened, Edit, Delete,
  Document, Plus, Refresh, ArrowRight, ArrowLeft, InfoFilled,
} from '@element-plus/icons-vue'
import http from '../api'
import { useUserStore } from '../stores/user'

const userStore = useUserStore()
const isAdmin = computed(() => userStore.role === 'admin')

// ===== 知识库列表 =====
const kbs = ref<any[]>([])
const kbKeyword = ref('')
const dialogVisible = ref(false)
const creating = ref(false)
const form = reactive({ name: '', description: '' })

const filteredKbs = computed(() => {
  const kw = kbKeyword.value.trim().toLowerCase()
  if (!kw) return kbs.value
  return kbs.value.filter(
    (k) => k.name.toLowerCase().includes(kw) || (k.description || '').toLowerCase().includes(kw),
  )
})

const totalDocs = computed(() => kbs.value.reduce((s, k) => s + (k.doc_count || 0), 0))

async function loadKbs() {
  const res: any = await http.get('/kb')
  kbs.value = res.data
}

async function createKb() {
  if (!form.name) { ElMessage.warning('请输入知识库名称'); return }
  creating.value = true
  try {
    await http.post('/kb', { name: form.name, description: form.description })
    ElMessage.success('创建成功')
    dialogVisible.value = false
    form.name = ''
    form.description = ''
    await loadKbs()
  } finally {
    creating.value = false
  }
}

// ===== 编辑知识库（名称锁定，仅描述可改）=====
const editDialog = ref(false)
const editing = ref(false)
const editForm = reactive({ id: 0, name: '', description: '' })

function openEdit(kb: any) {
  editForm.id = kb.id
  editForm.name = kb.name
  editForm.description = kb.description || ''
  editDialog.value = true
}

async function saveEdit() {
  editing.value = true
  try {
    await http.put(`/kb/${editForm.id}`, { description: editForm.description })
    ElMessage.success('已更新')
    editDialog.value = false
    await loadKbs()
  } catch (err: any) {
    ElMessage.error(err.response?.data?.message || '更新失败')
  } finally {
    editing.value = false
  }
}

// ===== 删除知识库 =====
async function removeKb(kb: any) {
  try {
    await ElMessageBox.confirm(
      `确定删除知识库「${kb.name}」？该库下 ${kb.doc_count || 0} 个文档及其分块、向量数据将一并清除，且不可恢复。`,
      '删除知识库',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消', dangerouslyUseHTMLString: false },
    )
  } catch { return }
  try {
    await http.delete(`/kb/${kb.id}`)
    ElMessage.success('知识库已删除')
    // 先从本地列表移除，确保用户立即可见效果；再刷新同步服务端
    kbs.value = kbs.value.filter((k) => k.id !== kb.id)
    try { await loadKbs() } catch { /* 刷新失败不影响已删除的反馈 */ }
  } catch (err: any) {
    ElMessage.error(err.response?.data?.message || '删除失败')
  }
}

// ===== 卡片配色（根据 id 取色，稳定不随机）=====
const KB_COLORS = [
  { background: 'linear-gradient(135deg,#667eea 0%,#764ba2 100%)' },
  { background: 'linear-gradient(135deg,#f093fb 0%,#f5576c 100%)' },
  { background: 'linear-gradient(135deg,#4facfe 0%,#00f2fe 100%)' },
  { background: 'linear-gradient(135deg,#43e97b 0%,#38f9d7 100%)' },
  { background: 'linear-gradient(135deg,#fa709a 0%,#fee140 100%)' },
  { background: 'linear-gradient(135deg,#30cfd0 0%,#330867 100%)' },
  { background: 'linear-gradient(135deg,#a8edea 0%,#fed6e3 100%)' },
  { background: 'linear-gradient(135deg,#ff9a9e 0%,#fecfef 100%)' },
]
function kbColor(id: number) {
  return KB_COLORS[(id - 1) % KB_COLORS.length]
}

// ===== 文档管理 =====
const currentKb = ref<any | null>(null)
const docs = ref<any[]>([])
const uploading = ref(false)
const pendingCount = ref(0)

function openDocs(kb: any) {
  currentKb.value = kb
  keyword.value = ''
  statusFilter.value = ''
  currentPage.value = 1
  loadDocs()
}

async function loadDocs() {
  const res: any = await http.get('/kb/documents', {
    params: { kb_id: currentKb.value.id },
  })
  docs.value = res.data
}

// el-upload 自定义上传：多选时每个文件调用一次，全部结束再刷新列表
async function customUpload(options: any) {
  const file = options.file
  const fd = new FormData()
  fd.append('kb_id', String(currentKb.value.id))
  fd.append('file', file)
  pendingCount.value++
  uploading.value = true
  try {
    const res: any = await http.post('/kb/documents', fd)
    ElMessage.success(`《${file.name}》上传成功，状态：${res.data.parse_status}`)
  } catch (err: any) {
    ElMessage.error(err.response?.data?.message || `《${file.name}》上传失败`)
  } finally {
    pendingCount.value--
    if (pendingCount.value === 0) {
      uploading.value = false
      await loadDocs()
    }
  }
}

async function removeDoc(doc: any) {
  await ElMessageBox.confirm(`确定删除《${doc.filename}》？分块与向量会一并清理`, '警告', { type: 'warning' })
  await http.delete(`/kb/documents/${doc.id}`)
  ElMessage.success('删除成功')
  await loadDocs()
}

// ===== 批量选择 / 删除 =====
const selected = ref<any[]>([])
function onSelectionChange(rows: any[]) {
  selected.value = rows
}
async function batchDelete() {
  if (!selected.value.length) return
  await ElMessageBox.confirm(`确定删除选中的 ${selected.value.length} 个文档？分块与向量会一并清理`, '警告', { type: 'warning' })
  for (const d of selected.value) {
    await http.delete(`/kb/documents/${d.id}`)
  }
  ElMessage.success('批量删除成功')
  await loadDocs()
}

// ===== 搜索 + 状态筛选 =====
const keyword = ref('')
const statusFilter = ref('')
const filteredDocs = computed(() =>
  docs.value.filter((d) => {
    const kw = !keyword.value || d.filename.toLowerCase().includes(keyword.value.toLowerCase())
    const st = !statusFilter.value || d.parse_status === statusFilter.value
    return kw && st
  }),
)

// ===== 前端分页 =====
const currentPage = ref(1)
const pageSize = ref(10)
const pagedDocs = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredDocs.value.slice(start, start + pageSize.value)
})
function rowIndex(i: number) {
  return (currentPage.value - 1) * pageSize.value + i + 1
}

// ===== 展示辅助 =====
function fileIcon(type: string) {
  const map: Record<string, string> = {
    pdf: '📄', docx: '📝', doc: '📝', txt: '📃', md: '📑',
  }
  return map[type] || '📄'
}
function statusTag(s: string) {
  const map: Record<string, string> = {
    success: 'success', processing: 'warning', failed: 'danger',
  }
  return map[s] || 'info'
}
function statusText(s: string) {
  const map: Record<string, string> = {
    success: '可用', processing: '处理中', failed: '失败',
  }
  return map[s] || s
}
function formatNumber(n: number) {
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return String(n)
}

// ===== 分块查看 =====
const chunkDialog = ref(false)
const chunks = ref<any[]>([])
const chunkTotal = ref(0)
const chunkPage = ref(1)
const chunkDoc = ref<any | null>(null)
const CHUNK_PAGE_SIZE = 10

async function openChunks(doc: any) {
  chunkDoc.value = doc
  chunkPage.value = 1
  chunkDialog.value = true
  await loadChunks()
}
async function loadChunks() {
  const res: any = await http.get(
    `/kb/documents/${chunkDoc.value.id}/chunks`,
    { params: { page: chunkPage.value, page_size: CHUNK_PAGE_SIZE } },
  )
  chunks.value = res.data.items
  chunkTotal.value = res.data.total
}
function onChunkPage(p: number) {
  chunkPage.value = p
  loadChunks()
}

// ===== 检索测试 =====
const searchDialog = ref(false)
const searching = ref(false)
const searchForm = reactive({ query: '', top_k: 5 })
const searchResult = ref<any | null>(null)
const traceOpen = ref(['fused'])

async function runSearch() {
  if (!searchForm.query) { ElMessage.warning('请输入查询内容'); return }
  searching.value = true
  try {
    const res: any = await http.post('/kb/search-test', {
      query: searchForm.query,
      kb_id: currentKb.value.id,
      top_k: searchForm.top_k,
    })
    searchResult.value = res.data
  } catch (err: any) {
    ElMessage.error(err.response?.data?.message || '检索失败')
  } finally {
    searching.value = false
  }
}

onMounted(loadKbs)
</script>

<template>
  <!-- ============ 视图A：知识库列表（卡片式） ============ -->
  <div v-if="!currentKb" class="kb-page">
    <!-- 渐变页头横幅 -->
    <div class="hero-banner">
      <div class="hero-bg-decor hero-decor-1" />
      <div class="hero-bg-decor hero-decor-2" />
      <div class="hero-content">
        <div class="hero-left">
          <div class="hero-badge">
            <el-icon :size="14"><Document /></el-icon>
            <span>Knowledge Base</span>
          </div>
          <h1 class="hero-title">知识库管理</h1>
          <p class="hero-sub">上传文档、自动解析分块向量化，驱动 AI 智能问答</p>
        </div>
        <div class="hero-right">
          <el-input
            v-model="kbKeyword"
            placeholder="搜索知识库"
            clearable
            class="hero-search"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-button v-if="isAdmin" class="btn-create" @click="dialogVisible = true">
            <el-icon style="margin-right: 4px"><Plus /></el-icon>新建知识库
          </el-button>
        </div>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stat-row">
      <div class="stat-card stat-blue">
        <div class="stat-icon"><el-icon :size="22"><FolderOpened /></el-icon></div>
        <div class="stat-info">
          <div class="stat-value">{{ kbs.length }}</div>
          <div class="stat-label">知识库总数</div>
        </div>
      </div>
      <div class="stat-card stat-purple">
        <div class="stat-icon"><el-icon :size="22"><Document /></el-icon></div>
        <div class="stat-info">
          <div class="stat-value">{{ totalDocs }}</div>
          <div class="stat-label">文档总数</div>
        </div>
      </div>
      <div class="stat-card stat-green">
        <div class="stat-icon"><el-icon :size="22"><Refresh /></el-icon></div>
        <div class="stat-info">
          <div class="stat-value">{{ kbs.filter(k => k.doc_count > 0).length }}</div>
          <div class="stat-label">已启用知识库</div>
        </div>
      </div>
      <div class="stat-card stat-orange">
        <div class="stat-icon"><el-icon :size="22"><Search /></el-icon></div>
        <div class="stat-info">
          <div class="stat-value">RAG</div>
          <div class="stat-label">混合检索 + Rerank</div>
        </div>
      </div>
    </div>

    <el-alert v-if="!isAdmin" type="warning" :closable="false" show-icon class="non-admin-alert">
      当前未登录或非管理员，仅可查看，无法上传 / 删除。请
      <router-link to="/login" style="font-weight: 600">前往登录</router-link>
      （管理员 admin / admin123）。
    </el-alert>

    <!-- 空状态 -->
    <div v-if="!filteredKbs.length" class="empty-state">
      <el-icon :size="64" color="#c0c4cc"><FolderOpened /></el-icon>
      <p class="empty-text">{{ kbKeyword ? '没有匹配的知识库' : '还没有知识库，点击右上角创建第一个' }}</p>
    </div>

    <!-- 知识库卡片网格 -->
    <div v-else class="kb-grid">
      <div
        v-for="kb in filteredKbs"
        :key="kb.id"
        class="kb-card"
        @click="openDocs(kb)"
      >
        <!-- 卡片顶部：图标 + 操作 -->
        <div class="card-top">
          <div class="kb-avatar" :style="kbColor(kb.id)">
            <el-icon :size="22"><Document /></el-icon>
          </div>
          <div class="card-actions" @click.stop>
            <el-tooltip content="编辑描述" placement="top">
              <el-button v-if="isAdmin" circle size="small" class="action-btn" @click="openEdit(kb)">
                <el-icon><Edit /></el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip content="删除知识库" placement="top">
              <el-button v-if="isAdmin" circle size="small" type="danger" class="action-btn" @click="removeKb(kb)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </el-tooltip>
          </div>
        </div>

        <!-- 卡片主体：名称 + 描述 -->
        <div class="card-body">
          <h3 class="kb-name">{{ kb.name }}</h3>
          <p class="kb-desc">{{ kb.description || '暂无描述' }}</p>
        </div>

        <!-- 卡片底部：统计信息 -->
        <div class="card-footer">
          <div class="footer-stat">
            <span class="stat-num">{{ kb.doc_count }}</span>
            <span class="stat-label">文档</span>
          </div>
          <div class="footer-stat">
            <span class="stat-time">{{ kb.created_at }}</span>
            <span class="stat-label">创建于</span>
          </div>
          <div class="footer-enter">
            进入管理 <el-icon style="vertical-align: middle"><arrow-right /></el-icon>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- ============ 视图B：文档管理 ============ -->
  <div v-else class="doc-page">
    <div class="doc-header">
      <div class="doc-header-left">
        <el-button link class="btn-back" @click="currentKb = null">
          <el-icon style="margin-right: 2px"><arrow-left /></el-icon>返回知识库
        </el-button>
        <div class="doc-title-wrap">
          <h2 class="doc-title">{{ currentKb.name }}</h2>
          <span class="doc-count-badge">{{ docs.length }} 篇文档</span>
        </div>
      </div>
      <el-button type="primary" plain class="btn-search-test" @click="searchDialog = true">
        <el-icon style="margin-right: 4px"><Search /></el-icon>检索测试
      </el-button>
    </div>
    <p v-if="currentKb.description" class="doc-subdesc">{{ currentKb.description }}</p>

    <!-- 拖拽上传 -->
    <el-upload
      v-if="isAdmin"
      drag
      multiple
      :show-file-list="false"
      :http-request="customUpload"
      accept=".pdf,.docx,.txt,.md"
      class="uploader"
    >
      <el-icon class="el-icon--upload"><upload-filled /></el-icon>
      <div class="el-upload__text">将文件拖到此处，或 <em>点击上传</em>（可多选批量上传）</div>
      <template #tip>
        <div class="el-upload__tip">支持 PDF / DOCX / TXT / MD，单文件建议不超过 15MB；上传后自动解析、分块并向量化</div>
      </template>
    </el-upload>

    <el-alert v-if="!isAdmin" type="warning" :closable="false" show-icon style="margin: 16px 0">
      仅管理员可上传 / 删除文档，请 <router-link to="/login" style="font-weight: 600">前往登录</router-link>。
    </el-alert>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-select v-model="statusFilter" placeholder="全部状态" clearable style="width: 140px">
        <el-option label="可用" value="success" />
        <el-option label="处理中" value="processing" />
        <el-option label="失败" value="failed" />
      </el-select>
      <el-input v-model="keyword" placeholder="搜索文件名" clearable style="width: 260px">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-button
        v-if="isAdmin" type="danger" plain :disabled="!selected.length"
        @click="batchDelete"
      >批量删除（{{ selected.length }}）</el-button>
      <div class="filter-spacer" />
      <el-button circle size="small" @click="loadDocs" title="刷新">
        <el-icon><Refresh /></el-icon>
      </el-button>
    </div>

    <!-- 文档表格 -->
    <el-table :data="pagedDocs" border stripe @selection-change="onSelectionChange" class="doc-table">
      <el-table-column v-if="isAdmin" type="selection" width="45" />
      <el-table-column type="index" label="#" width="60" :index="rowIndex" />
      <el-table-column label="名称">
        <template #default="{ row }">
          <span style="font-size: 18px; margin-right: 6px">{{ fileIcon(row.file_type) }}</span>
          <span style="font-weight: 600">{{ row.filename }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="chunk_count" label="分块数" width="90" align="center" />
      <el-table-column label="字符数" width="100" align="center">
        <template #default="{ row }">{{ formatNumber(row.char_count) }}</template>
      </el-table-column>
      <el-table-column prop="created_at" label="上传时间" width="150" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusTag(row.parse_status)" size="small">{{ statusText(row.parse_status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="170">
        <template #default="{ row }">
          <el-button size="small" link @click="openChunks(row)">查看分块</el-button>
          <el-button v-if="isAdmin" size="small" link type="danger" @click="removeDoc(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      style="margin-top: 16px; justify-content: flex-end"
      layout="total, sizes, prev, pager, next, jumper"
      :total="filteredDocs.length"
      :page-sizes="[10, 20, 50]"
      v-model:current-page="currentPage"
      v-model:page-size="pageSize"
      background
    />
  </div>

  <!-- ============ 新建知识库 ============ -->
  <el-dialog v-model="dialogVisible" title="新建知识库" width="440px" class="kb-dialog">
    <el-form label-position="top">
      <el-form-item label="名称">
        <el-input v-model="form.name" placeholder="如：产品手册" maxlength="100" show-word-limit />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" :rows="3" maxlength="500" show-word-limit placeholder="简要说明这个知识库的用途" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="creating" @click="createKb">创建</el-button>
    </template>
  </el-dialog>

  <!-- ============ 编辑知识库（名称锁定） ============ -->
  <el-dialog v-model="editDialog" title="编辑知识库" width="440px" class="kb-dialog">
    <el-form label-position="top">
      <el-form-item label="名称">
        <el-input v-model="editForm.name" disabled>
          <template #append>
            <el-tooltip content="知识库名称创建后不可修改" placement="top">
              <el-icon style="cursor: help; color: #909399"><InfoFilled /></el-icon>
            </el-tooltip>
          </template>
        </el-input>
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="editForm.description" type="textarea" :rows="3" maxlength="500" show-word-limit placeholder="简要说明这个知识库的用途" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="editDialog = false">取消</el-button>
      <el-button type="primary" :loading="editing" @click="saveEdit">保存</el-button>
    </template>
  </el-dialog>

  <!-- ============ 分块查看弹窗 ============ -->
  <el-dialog v-model="chunkDialog" :title="`《${chunkDoc?.filename}》的分块（共 ${chunkTotal} 块）`" width="720px">
    <el-table :data="chunks" border>
      <el-table-column prop="chunk_index" label="序号" width="70" />
      <el-table-column prop="content" label="内容" show-overflow-tooltip />
    </el-table>
    <el-pagination
      style="margin-top: 12px; justify-content: flex-end"
      layout="total, prev, pager, next" :total="chunkTotal"
      :page-size="CHUNK_PAGE_SIZE" :current-page="chunkPage"
      @current-change="onChunkPage"
    />
  </el-dialog>

  <!-- ============ 检索测试弹窗 ============ -->
  <el-dialog v-model="searchDialog" title="检索测试（两路召回 → RRF 融合 → Rerank 精排）" width="760px">
    <el-form inline>
      <el-form-item label="查询">
        <el-input v-model="searchForm.query" style="width: 280px" placeholder="输入与文档内容相关的提问" />
      </el-form-item>
      <el-form-item label="top_k">
        <el-input-number v-model="searchForm.top_k" :min="1" :max="20" />
      </el-form-item>
      <el-button type="primary" :loading="searching" @click="runSearch">检索</el-button>
    </el-form>

    <div v-if="searchResult">
      <el-alert
        :type="searchResult.hit ? 'success' : 'warning'" :closable="false"
        :title="searchResult.hit
          ? `命中：top1 相关度 ${searchResult.top1_score}，最终返回 ${searchResult.candidates.length} 条`
          : `未命中：top1 相关度 ${searchResult.top1_score} 低于阈值，AI 将走兜底转人工`"
        style="margin-bottom: 12px"
      />

      <el-collapse v-model="traceOpen">
        <el-collapse-item name="vec" :title="`路1 向量召回（${searchResult.trace.vector.length} 条）`">
          <el-table :data="searchResult.trace.vector" size="small" border>
            <el-table-column prop="chunk_id" label="chunk_id" width="110" />
            <el-table-column prop="score" label="向量相似度" />
          </el-table>
        </el-collapse-item>
        <el-collapse-item name="bm" :title="`路2 BM25 召回（${searchResult.trace.bm25.length} 条）`">
          <el-table :data="searchResult.trace.bm25" size="small" border>
            <el-table-column prop="chunk_id" label="chunk_id" width="110" />
            <el-table-column prop="score" label="BM25 得分" />
          </el-table>
        </el-collapse-item>
        <el-collapse-item name="fused" :title="`RRF 融合排名（${searchResult.trace.fused.length} 条）`">
          <el-table :data="searchResult.trace.fused" size="small" border>
            <el-table-column prop="chunk_id" label="chunk_id" width="110" />
            <el-table-column prop="rrf" label="RRF 分" />
          </el-table>
        </el-collapse-item>
      </el-collapse>

      <h4 style="margin: 16px 0 8px">Rerank 最终结果（这些进入大模型上下文）</h4>
      <el-collapse>
        <el-collapse-item
          v-for="(item, i) in searchResult.candidates" :key="item.chunk_id"
          :title="`#${Number(i) + 1} · chunk ${item.chunk_id} · rerank ${item.score.toFixed(4)} · rrf ${item.rrf}`"
        >
          <p style="white-space: pre-wrap">{{ item.content }}</p>
        </el-collapse-item>
      </el-collapse>
    </div>
  </el-dialog>
</template>

<style scoped>
/* ===== 全局页面 ===== */
.kb-page, .doc-page {
  padding: 0 0 32px;
  min-height: 100%;
  background: linear-gradient(180deg, #f0f4ff 0%, #f7f8fc 300px, #f5f7fa 100%);
}

/* ===== 渐变页头横幅 ===== */
.hero-banner {
  position: relative;
  background: linear-gradient(135deg, #1e3a8a 0%, #3b5bdb 40%, #5c7cfa 70%, #748ffc 100%);
  padding: 32px 32px 28px;
  overflow: hidden;
}
.hero-bg-decor {
  position: absolute;
  border-radius: 50%;
  opacity: 0.15;
  pointer-events: none;
}
.hero-decor-1 {
  width: 320px; height: 320px;
  background: radial-gradient(circle, #fff 0%, transparent 70%);
  top: -120px; right: -60px;
}
.hero-decor-2 {
  width: 200px; height: 200px;
  background: radial-gradient(circle, #a5d8ff 0%, transparent 70%);
  bottom: -80px; left: 30%;
}
.hero-content {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 20px;
  flex-wrap: wrap;
}
.hero-left { flex: 1; min-width: 280px; }
.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(255,255,255,0.15);
  backdrop-filter: blur(4px);
  color: #dbe4ff;
  font-size: 12px;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 20px;
  margin-bottom: 12px;
  letter-spacing: 0.5px;
}
.hero-title {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  color: #fff;
  letter-spacing: -0.5px;
}
.hero-sub {
  color: rgba(255,255,255,0.75);
  font-size: 13px;
  margin: 8px 0 0;
}
.hero-right {
  display: flex;
  align-items: center;
  gap: 10px;
}
.hero-search {
  width: 220px;
}
.hero-search :deep(.el-input__wrapper) {
  background: rgba(255,255,255,0.15);
  backdrop-filter: blur(4px);
  box-shadow: none;
  border: 1px solid rgba(255,255,255,0.25);
}
.hero-search :deep(.el-input__inner) {
  color: #fff;
}
.hero-search :deep(.el-input__inner::placeholder) {
  color: rgba(255,255,255,0.6);
}
.hero-search :deep(.el-input__prefix) {
  color: rgba(255,255,255,0.7);
}
.btn-create {
  background: #fff;
  color: #3b5bdb;
  border: none;
  font-weight: 600;
  padding: 10px 20px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  transition: all 0.2s;
}
.btn-create:hover {
  background: #f0f4ff;
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(0,0,0,0.2);
}

/* ===== 统计卡片 ===== */
.stat-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  padding: 0 28px;
  margin-top: -20px;
  position: relative;
  z-index: 2;
  margin-bottom: 24px;
}
.stat-card {
  background: #fff;
  border-radius: 12px;
  padding: 18px 20px;
  display: flex;
  align-items: center;
  gap: 14px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06);
  border: 1px solid #eef0f4;
  transition: all 0.25s;
}
.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0,0,0,0.1);
}
.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}
.stat-blue .stat-icon { background: linear-gradient(135deg, #4facfe, #00f2fe); }
.stat-purple .stat-icon { background: linear-gradient(135deg, #667eea, #764ba2); }
.stat-green .stat-icon { background: linear-gradient(135deg, #43e97b, #38f9d7); }
.stat-orange .stat-icon { background: linear-gradient(135deg, #fa709a, #fee140); }
.stat-info { flex: 1; }
.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: #1d2129;
  line-height: 1.2;
}
.stat-label {
  font-size: 12px;
  color: #86909c;
  margin-top: 2px;
}

/* ===== 空状态 ===== */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 28px;
  color: #c0c4cc;
}
.empty-text { margin-top: 16px; font-size: 14px; color: #909399; }
.non-admin-alert {
  margin: 0 28px 20px;
}

/* ===== 知识库卡片网格 ===== */
.kb-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
  padding: 0 28px;
}

.kb-card {
  background: #fff;
  border: 1px solid #e8eaf0;
  border-radius: 14px;
  padding: 22px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}
.kb-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 4px;
  background: var(--card-accent, #409eff);
  opacity: 0;
  transition: opacity 0.3s;
}
.kb-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 32px rgba(59, 91, 219, 0.12);
  border-color: #c7d2fe;
}
.kb-card:hover::before { opacity: 1; }

/* 卡片顶部 */
.card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.kb-avatar {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}
.card-actions {
  display: flex;
  gap: 6px;
  opacity: 0;
  transition: opacity 0.2s;
}
.kb-card:hover .card-actions { opacity: 1; }
.action-btn {
  background: #f5f6f7;
  border: none;
}
.action-btn:hover { background: #e8e9eb; }

/* 卡片主体 */
.card-body { flex: 1; margin-bottom: 16px; }
.kb-name {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 600;
  color: #1d2129;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
}
.kb-desc {
  margin: 0;
  font-size: 13px;
  color: #86909c;
  line-height: 1.6;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  min-height: 42px;
}

/* 卡片底部 */
.card-footer {
  display: flex;
  align-items: center;
  gap: 20px;
  padding-top: 14px;
  border-top: 1px solid #f2f3f5;
}
.footer-stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.stat-num {
  font-size: 18px;
  font-weight: 700;
  color: #3b5bdb;
  line-height: 1;
}
.stat-label {
  font-size: 11px;
  color: #a9aeb8;
}
.stat-time {
  font-size: 12px;
  color: #4e5969;
  font-weight: 500;
}
.footer-enter {
  margin-left: auto;
  font-size: 12px;
  color: #3b5bdb;
  font-weight: 600;
  opacity: 0;
  transition: opacity 0.2s;
  white-space: nowrap;
}
.kb-card:hover .footer-enter { opacity: 1; }

/* ===== 文档管理页 ===== */
.doc-page { padding: 24px 28px; }
.doc-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  flex-wrap: wrap;
  gap: 12px;
}
.doc-header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}
.btn-back {
  font-size: 14px;
  padding: 6px 10px;
  color: #4e5969;
}
.btn-back:hover { color: #3b5bdb; background: #eef2ff; border-radius: 6px; }
.doc-title-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
}
.doc-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #1d2129;
}
.doc-count-badge {
  background: linear-gradient(135deg, #e8f3ff, #dbe4ff);
  color: #3b5bdb;
  font-size: 12px;
  font-weight: 600;
  padding: 3px 12px;
  border-radius: 20px;
}
.doc-subdesc {
  color: #86909c;
  font-size: 13px;
  margin: 0 0 20px 48px;
}
.btn-search-test {
  font-weight: 500;
  background: linear-gradient(135deg, #3b5bdb, #5c7cfa);
  border: none;
}
.btn-search-test:hover { opacity: 0.9; }

/* 上传区 */
.uploader { margin: 16px 0 20px; width: 100%; }
.uploader :deep(.el-upload),
.uploader :deep(.el-upload-dragger) {
  width: 100%;
  border-radius: 12px;
}
.uploader :deep(.el-upload-dragger) {
  padding: 32px 20px;
  border: 2px dashed #c7d2fe;
  background: linear-gradient(180deg, #f8faff 0%, #fff 100%);
  transition: all 0.2s;
}
.uploader :deep(.el-upload-dragger:hover) {
  border-color: #3b5bdb;
  background: linear-gradient(180deg, #eef2ff 0%, #f8faff 100%);
}

/* 筛选栏 */
.filter-bar {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 16px;
}
.filter-spacer { flex: 1; }

/* 文档表格 */
.doc-table {
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #e8eaf0;
}
.doc-table :deep(.el-table__header th) {
  background: linear-gradient(180deg, #f8faff, #f0f4ff);
  font-weight: 600;
  color: #3b5bdb;
}

/* 弹窗 */
.kb-dialog :deep(.el-dialog__header) {
  padding-bottom: 12px;
}
.kb-dialog :deep(.el-dialog__title) {
  font-weight: 600;
  font-size: 17px;
}
</style>
