<script setup lang="ts">
/**
 * 管理端主界面布局：左侧菜单 + 顶部用户栏 + 内容区。
 * 菜单按角色过滤：数据看板仅 admin 可见（与后端 require_role 口径一致）。
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Document, User, DataAnalysis, SwitchButton } from '@element-plus/icons-vue'
import { useUserStore } from '../stores/user'

const router = useRouter()
const userStore = useUserStore()

const isAdmin = computed(() => userStore.role === 'admin')

const menus = computed(() => {
  const items = [
    { path: '/kb', title: '知识库管理', icon: Document },
    { path: '/agent', title: '坐席工作台', icon: User },
  ]
  if (isAdmin.value) items.push({ path: '/dashboard', title: '数据看板', icon: DataAnalysis })
  return items
})

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定退出当前账号？', '提示', { type: 'warning' })
  } catch {
    return   // 用户取消
  }
  userStore.logout()
  ElMessage.success('已退出登录')
  router.push('/login')
}

function openVisitorChat() {
  // 访客聊天窗是匿名入口，独立标签页打开，不占用管理端会话
  window.open('/#/chat', '_blank')
}
</script>

<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="logo">
        <div class="logo-icon">
          <el-icon :size="20"><SwitchButton /></el-icon>
        </div>
        <span class="logo-text">SmartKefu</span>
        <span class="logo-sub">管理端</span>
      </div>
      <el-menu :default-active="$route.path" router class="menu">
        <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">
          <el-icon><component :is="m.icon" /></el-icon>
          <span>{{ m.title }}</span>
        </el-menu-item>
      </el-menu>
      <div class="aside-footer">
        <div class="version-tag">v1.0</div>
      </div>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-left">
          <span class="title">{{ $route.meta.title || 'SmartKefu' }}</span>
        </div>
        <div class="right">
          <el-button link type="primary" class="header-btn" @click="openVisitorChat">
            <el-icon style="margin-right: 4px"><SwitchButton /></el-icon>访客聊天窗
          </el-button>
          <el-tag :type="isAdmin ? 'danger' : 'info'" size="small" effect="dark" round>
            {{ isAdmin ? '管理员' : '坐席' }}
          </el-tag>
          <div class="user-info">
            <div class="user-avatar">{{ (userStore.username || '?').charAt(0).toUpperCase() }}</div>
            <span class="uname">{{ userStore.username || '未登录' }}</span>
          </div>
          <el-button size="small" @click="handleLogout" class="logout-btn">退出登录</el-button>
        </div>
      </el-header>

      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout { height: 100vh; }

/* ===== 侧边栏 ===== */
.aside {
  background: linear-gradient(180deg, #0f172a 0%, #1e293b 50%, #1e3a5f 100%);
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}
.aside::before {
  content: '';
  position: absolute;
  top: -50px;
  right: -50px;
  width: 180px;
  height: 180px;
  background: radial-gradient(circle, rgba(59,91,219,0.25) 0%, transparent 70%);
  border-radius: 50%;
  pointer-events: none;
}

/* Logo */
.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px 18px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  position: relative;
  z-index: 1;
}
.logo-icon {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  background: linear-gradient(135deg, #3b5bdb, #5c7cfa);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  box-shadow: 0 3px 10px rgba(59,91,219,0.4);
}
.logo-text {
  color: #fff;
  font-weight: 700;
  font-size: 16px;
  letter-spacing: -0.3px;
}
.logo-sub {
  color: rgba(255,255,255,0.45);
  font-size: 11px;
  margin-left: auto;
  padding: 2px 8px;
  background: rgba(255,255,255,0.08);
  border-radius: 10px;
  white-space: nowrap;
  flex-shrink: 0;
}

/* 菜单 */
.menu {
  border-right: none;
  background: transparent;
  padding: 12px 10px;
  flex: 1;
  position: relative;
  z-index: 1;
}
.menu :deep(.el-menu-item) {
  color: rgba(255,255,255,0.6);
  border-radius: 8px;
  margin-bottom: 4px;
  height: 44px;
  line-height: 44px;
  transition: all 0.2s;
}
.menu :deep(.el-menu-item:hover) {
  background: rgba(255,255,255,0.08);
  color: #fff;
}
.menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(135deg, #3b5bdb, #5c7cfa);
  color: #fff;
  box-shadow: 0 3px 12px rgba(59,91,219,0.35);
}
.menu :deep(.el-menu-item .el-icon) {
  font-size: 16px;
}

.aside-footer {
  padding: 14px 18px;
  border-top: 1px solid rgba(255,255,255,0.08);
  position: relative;
  z-index: 1;
}
.version-tag {
  display: inline-block;
  font-size: 11px;
  color: rgba(255,255,255,0.35);
  padding: 3px 10px;
  background: rgba(255,255,255,0.06);
  border-radius: 10px;
}

/* ===== 顶部栏 ===== */
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e8eaf0;
  box-shadow: 0 1px 4px rgba(0,0,0,0.04);
  height: 56px;
}
.header-left { display: flex; align-items: center; gap: 12px; }
.title {
  font-size: 15px;
  font-weight: 600;
  color: #1d2129;
}
.right { display: flex; align-items: center; gap: 12px; }
.header-btn { font-size: 13px; }

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
}
.user-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: linear-gradient(135deg, #3b5bdb, #5c7cfa);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
}
.uname { color: #4e5969; font-size: 13px; font-weight: 500; }
.logout-btn {
  font-size: 12px;
  border-color: #e5e6eb;
  color: #86909c;
}
.logout-btn:hover {
  color: #f5576c;
  border-color: #f5576c;
}

.main { padding: 0; background: #f5f7fa; overflow: auto; }
</style>
