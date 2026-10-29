// 后端接口的封装
// 出错时把后端给的 detail 抛出来，页面上直接显示那句话

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(path, {
      headers: { 'Content-Type': 'application/json' },
      ...options
    })
  } catch (error) {
    throw new Error('连不上后端服务：' + error.message)
  }

  if (!response.ok) {
    let message = '请求失败（HTTP ' + response.status + '）'
    try {
      const data = await response.json()
      if (data && data.detail) {
        message = typeof data.detail === 'string'
          ? data.detail
          : JSON.stringify(data.detail)
      }
    } catch (error) {
      // 不是 JSON 响应，用默认文案
    }
    const failure = new Error(message)
    failure.status = response.status
    throw failure
  }

  if (response.status === 204) {
    return null
  }
  return response.json()
}

function query(params) {
  const search = new URLSearchParams()
  Object.keys(params || {}).forEach((key) => {
    const value = params[key]
    if (value !== undefined && value !== null && value !== '') {
      search.append(key, value)
    }
  })
  const text = search.toString()
  return text ? '?' + text : ''
}

export const api = {
  // 选项
  provinces: () => request('/api/options/provinces'),
  schools: (params) => request('/api/options/schools' + query(params)),
  majors: () => request('/api/options/majors'),
  majorsOfSchool: (dwdm) =>
    request('/api/majors-of-school' + query({ dwdm })),

  // 任务
  jobs: () => request('/api/jobs'),
  job: (id) => request('/api/jobs/' + encodeURIComponent(id)),
  logs: (id, offset, limit) =>
    request('/api/jobs/' + encodeURIComponent(id) + '/logs' + query({ offset, limit })),
  createJob: (payload) =>
    request('/api/jobs', { method: 'POST', body: JSON.stringify(payload) }),
  stopJob: (id) =>
    request('/api/jobs/' + encodeURIComponent(id) + '/stop', { method: 'POST' }),

  // 结果
  results: () => request('/api/results')
}

export default api
