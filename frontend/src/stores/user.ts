import { defineStore } from 'pinia'
import { ref } from 'vue'
import http from '../api'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')
  const role = ref(localStorage.getItem('role') || '')
  const userId = ref(localStorage.getItem('user_id') || '')
  // 命名加 Ref 后缀：login/register 的形参也叫 username，直接同名会遮蔽 ref
  const usernameRef = ref(localStorage.getItem('username') || '')

  async function login(username: string, password: string) {
    const form = new URLSearchParams()
    form.append('username', username)
    form.append('password', password)
    const res: any = await http.post('/auth/login', form)
    token.value = res.data.access_token
    role.value = res.data.role
    userId.value = String(res.data.user_id)
    localStorage.setItem('token', res.data.access_token)
    localStorage.setItem('role', res.data.role)
    localStorage.setItem('user_id', String(res.data.user_id))
    usernameRef.value = res.data.username || ''
    localStorage.setItem('username', res.data.username || '')
  }

  async function register(username: string, password: string) {
    // 新账号角色由后端强制为 agent，前端不传 role
    await http.post('/auth/register', { username, password })
  }

  function logout() {
    token.value = ''
    role.value = ''
    userId.value = ''
    localStorage.removeItem('token')
    localStorage.removeItem('role')
    localStorage.removeItem('user_id')
    usernameRef.value = ''
    localStorage.removeItem('username')
  }

  return { token, role, userId, username: usernameRef, login, register, logout }
})