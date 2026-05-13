const app = getApp()

const RETRY_CONFIG = {
  maxRetries: 1,
  retryDelay: 500,
  retryableCodes: [429, 502, 503],
}

const TIMEOUT_CONFIG = {
  connect: 5000,
  request: 15000,
  stream: 60000,
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

function request(options, retryCount = 0) {
  return new Promise((resolve, reject) => {
    if (!app.globalData.serverAvailable && retryCount === 0) {
      app.checkServerAvailable().then((available) => {
        if (!available) {
          reject({ code: -1, message: '服务器暂不可用，请检查后端是否运行' })
          return
        }
        doRequest(options, retryCount, resolve, reject)
      })
      return
    }

    doRequest(options, retryCount, resolve, reject)
  })
}

function doRequest(options, retryCount, resolve, reject) {
    const token = app.globalData.token
    const header = {
      'Content-Type': 'application/json',
      ...(options.header || {}),
    }

    if (token) {
      header['Authorization'] = `Bearer ${token}`
    }

    const timeout = options.timeout || TIMEOUT_CONFIG.request

    wx.request({
      url: `${app.globalData.baseUrl}${options.url}`,
      method: options.method || 'GET',
      data: options.data || {},
      header,
      timeout,
      success(res) {
        app.globalData.serverAvailable = true
        if (res.statusCode === 200) {
          resolve(res.data)
        } else if (res.statusCode === 401) {
          app.logout()
          reject({ code: 401, message: '登录已过期，请重新登录' })
        } else if (res.statusCode === 429) {
          if (retryCount < RETRY_CONFIG.maxRetries) {
            const delay = RETRY_CONFIG.retryDelay * (retryCount + 2)
            sleep(delay).then(() => {
              doRequest(options, retryCount + 1, resolve, reject)
            })
          } else {
            reject({ code: 429, message: '请求过于频繁，请稍后再试' })
          }
        } else {
          reject({ code: res.statusCode, message: res.data?.detail || '请求失败' })
        }
      },
      fail(err) {
        app.globalData.serverAvailable = false
        reject({ code: -1, message: '网络连接失败，请检查网络设置' })
      },
    })
}

function get(url, data) {
  return request({ url, method: 'GET', data })
}

function post(url, data, options) {
  return request({ url, method: 'POST', data, ...options })
}

function put(url, data) {
  return request({ url, method: 'PUT', data })
}

function del(url, data) {
  return request({ url, method: 'DELETE', data })
}

function uploadFile(url, filePath, name = 'file') {
  return new Promise((resolve, reject) => {
    const token = app.globalData.token
    wx.uploadFile({
      url: `${app.globalData.baseUrl}${url}`,
      filePath,
      name,
      header: {
        'Authorization': `Bearer ${token}`,
      },
      timeout: 30000,
      success(res) {
        if (res.statusCode === 200) {
          resolve(JSON.parse(res.data))
        } else {
          reject({ code: res.statusCode, message: '上传失败' })
        }
      },
      fail(err) {
        reject({ code: -1, message: '上传失败' })
      },
    })
  })
}

function streamPost(url, data, onToken, onDone, onError) {
  const token = app.globalData.token
  const header = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,
  }

  let retryCount = 0
  const maxStreamRetries = 1

  function doRequest() {
    const requestTask = wx.request({
      url: `${app.globalData.baseUrl}${url}`,
      method: 'POST',
      data,
      header,
      enableChunked: true,
      timeout: TIMEOUT_CONFIG.stream,
      success(res) {
        if (res.statusCode === 200) {
          const fullText = res.data
          if (typeof fullText === 'string') {
            const lines = fullText.split('\n')
            let accumulated = ''
            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const parsed = JSON.parse(line.substring(6))
                  if (parsed.type === 'token') {
                    accumulated += parsed.content
                    onToken(parsed.content, accumulated)
                  } else if (parsed.type === 'done') {
                    onDone(parsed)
                  } else if (parsed.type === 'start') {
                    onToken('', '', parsed)
                  }
                } catch (e) {}
              }
            }
            if (!accumulated) {
              onDone({ content: fullText, type: 'done' })
            }
          } else {
            onDone(res.data)
          }
        } else if (res.statusCode === 429 && retryCount < maxStreamRetries) {
          retryCount++
          sleep(2000).then(() => doRequest())
        } else {
          onError({ code: res.statusCode, message: res.data?.detail || '请求失败' })
        }
      },
      fail(err) {
        app.globalData.serverAvailable = false
        onError({ code: -1, message: '网络连接失败，请检查网络后重试' })
      },
    })

    return requestTask
  }

  return doRequest()
}

module.exports = {
  request,
  get,
  post,
  put,
  del,
  uploadFile,
  streamPost,
}
