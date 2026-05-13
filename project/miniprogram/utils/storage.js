const STORAGE_KEYS = {
  TOKEN: 'token',
  USER_INFO: 'userInfo',
  CONVERSATIONS: 'conversations',
  MESSAGES_PREFIX: 'messages_',
  SETTINGS: 'settings',
  DRAFT_PREFIX: 'draft_',
}

function setItem(key, value) {
  try {
    wx.setStorageSync(key, value)
    return true
  } catch (e) {
    console.error('Storage setItem error:', e)
    return false
  }
}

function getItem(key, defaultValue) {
  try {
    const value = wx.getStorageSync(key)
    return value || defaultValue
  } catch (e) {
    console.error('Storage getItem error:', e)
    return defaultValue
  }
}

function removeItem(key) {
  try {
    wx.removeStorageSync(key)
    return true
  } catch (e) {
    console.error('Storage removeItem error:', e)
    return false
  }
}

function saveConversations(conversations) {
  return setItem(STORAGE_KEYS.CONVERSATIONS, conversations)
}

function getConversations() {
  return getItem(STORAGE_KEYS.CONVERSATIONS, [])
}

function saveMessages(conversationId, messages) {
  const key = STORAGE_KEYS.MESSAGES_PREFIX + conversationId
  return setItem(key, messages)
}

function getMessages(conversationId) {
  const key = STORAGE_KEYS.MESSAGES_PREFIX + conversationId
  return getItem(key, [])
}

function saveDraft(conversationId, content) {
  const key = STORAGE_KEYS.DRAFT_PREFIX + conversationId
  return setItem(key, content)
}

function getDraft(conversationId) {
  const key = STORAGE_KEYS.DRAFT_PREFIX + conversationId
  return getItem(key, '')
}

function clearDraft(conversationId) {
  const key = STORAGE_KEYS.DRAFT_PREFIX + conversationId
  return removeItem(key)
}

function saveSettings(settings) {
  return setItem(STORAGE_KEYS.SETTINGS, settings)
}

function getSettings() {
  return getItem(STORAGE_KEYS.SETTINGS, {
    autoPlayVoice: true,
    language: 'zh-CN',
  })
}

function clearAllData() {
  try {
    wx.clearStorageSync()
    return true
  } catch (e) {
    console.error('Storage clearAllData error:', e)
    return false
  }
}

function getStorageSize() {
  try {
    const res = wx.getStorageInfoSync()
    return {
      keys: res.keys,
      currentSize: res.currentSize,
      limitSize: res.limitSize,
    }
  } catch (e) {
    return null
  }
}

module.exports = {
  STORAGE_KEYS,
  setItem,
  getItem,
  removeItem,
  saveConversations,
  getConversations,
  saveMessages,
  getMessages,
  saveDraft,
  getDraft,
  clearDraft,
  saveSettings,
  getSettings,
  clearAllData,
  getStorageSize,
}
