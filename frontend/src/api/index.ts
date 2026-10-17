import axios from 'axios'

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,
})

// 请求拦截器：自动附加 token
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：拆包 + 统一错误处理
http.interceptors.response.use(
  (res) => res.data,
  (err) => {
    if (err.response?.status === 401) {
      // token 失效/无效：清全部登录态，避免守卫凭残留状态误判
      localStorage.removeItem('token')
      localStorage.removeItem('role')
      localStorage.removeItem('user_id')
      localStorage.removeItem('username')
      window.location.hash = '#/login'
    }
    return Promise.reject(err)
  }
)

export default http