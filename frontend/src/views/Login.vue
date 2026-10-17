<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '../stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const activeTab = ref('login')
const loading = ref(false)

const loginForm = reactive({ username: '', password: '' })
const regForm = reactive({ username: '', password: '', confirm: '' })

// 守卫跳登录时带的 redirect 优先，否则回主界面
function goAfterLogin() {
  const redirect = route.query.redirect
  router.push(typeof redirect === 'string' && redirect.startsWith('/') ? redirect : '/kb')
}

async function handleLogin() {
  if (!loginForm.username || !loginForm.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    await userStore.login(loginForm.username, loginForm.password)
    ElMessage.success('登录成功')
    goAfterLogin()
  } catch (err: any) {
    ElMessage.error(err.response?.data?.message || '登录失败')
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  if (!regForm.username || !regForm.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  if (regForm.password !== regForm.confirm) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }
  loading.value = true
  try {
    await userStore.register(regForm.username, regForm.password)
    ElMessage.success('注册成功，请用新账号登录')
    loginForm.username = regForm.username
    loginForm.password = ''
    regForm.password = ''
    regForm.confirm = ''
    activeTab.value = 'login'
  } catch (err: any) {
    ElMessage.error(err.response?.data?.message || '注册失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <el-card class="login-card">
      <h2>SmartKefu 管理端</h2>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="登录" name="login">
          <el-form label-position="top" @submit.prevent="handleLogin">
            <el-form-item label="用户名">
              <el-input v-model="loginForm.username" placeholder="请输入用户名" />
            </el-form-item>
            <el-form-item label="密码">
              <el-input v-model="loginForm.password" type="password" show-password
                        placeholder="请输入密码" />
            </el-form-item>
            <el-button type="primary" style="width: 100%"
                       :loading="loading && activeTab === 'login'" @click="handleLogin">
              登 录
            </el-button>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="注册新账号" name="register">
          <el-form label-position="top" @submit.prevent="handleRegister">
            <el-form-item label="用户名">
              <el-input v-model="regForm.username" placeholder="3-50 个字符" />
            </el-form-item>
            <el-form-item label="密码">
              <el-input v-model="regForm.password" type="password" show-password
                        placeholder="至少 6 个字符" />
            </el-form-item>
            <el-form-item label="确认密码">
              <el-input v-model="regForm.confirm" type="password" show-password
                        placeholder="再次输入密码" />
            </el-form-item>
            <el-button type="primary" style="width: 100%"
                       :loading="loading && activeTab === 'register'" @click="handleRegister">
              注 册
            </el-button>
            <p class="tip">新注册账号统一为坐席角色；管理员账号由系统管理员创建。</p>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<style scoped>
.login-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
}
.login-card {
  width: 400px;
}
.tip {
  margin-top: 10px;
  color: #909399;
  font-size: 12px;
}
</style>
