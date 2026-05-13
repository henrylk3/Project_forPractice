# 智能聊天机器人 API 接口文档

## 基本信息

- 基础URL: `https://your-api-domain.com/api/v1`
- 认证方式: Bearer Token (JWT)
- 数据格式: JSON
- 编码: UTF-8

## 认证接口

### 微信登录

**POST** `/auth/wx-login`

使用微信授权code进行登录，返回JWT令牌。

**请求参数:**

| 字段          | 类型     | 必填 | 说明       |
| ----------- | ------ | -- | -------- |
| code        | string | 是  | 微信登录code |
| nickname    | string | 否  | 用户昵称     |
| avatar\_url | string | 否  | 用户头像URL  |

**响应示例:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "nickname": "用户",
  "avatar_url": null,
  "expires_at": "2026-05-07T12:00:00"
}
```

### 开发环境登录

**POST** `/auth/dev-login`

开发环境专用登录接口，无需微信code。

**响应:** 同微信登录

### 获取当前用户信息

**GET** `/auth/me`

需要认证。

**响应示例:**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "openid": "oXXXX...",
  "nickname": "用户",
  "avatar_url": null,
  "phone": null,
  "is_active": true,
  "bot_role": "assistant",
  "dialogue_style": "friendly",
  "language": "zh-CN",
  "created_at": "2026-04-30T12:00:00",
  "last_login": "2026-04-30T12:00:00"
}
```

### 更新用户信息

**PUT** `/auth/me`

需要认证。

**请求参数:**

| 字段              | 类型     | 必填 | 说明                                        |
| --------------- | ------ | -- | ----------------------------------------- |
| nickname        | string | 否  | 用户昵称                                      |
| avatar\_url     | string | 否  | 用户头像                                      |
| bot\_role       | string | 否  | 机器人角色: assistant/tutor/companion/creative |
| dialogue\_style | string | 否  | 对话风格: friendly/formal/humorous/concise    |
| language        | string | 否  | 语言设置                                      |

***

## 对话接口

### 发送消息

**POST** `/chat/send`

发送消息并获取AI回复。

**请求参数:**

| 字段               | 类型     | 必填 | 说明                            |
| ---------------- | ------ | -- | ----------------------------- |
| conversation\_id | string | 否  | 对话ID，为空则创建新对话                 |
| content          | string | 是  | 消息内容，最长2000字                  |
| content\_type    | string | 否  | 消息类型: text/image/emoji，默认text |
| media\_url       | string | 否  | 媒体文件URL                       |

**响应示例:**

```json
{
  "conversation_id": "660e8400-e29b-41d4-a716-446655440000",
  "message_id": "770e8400-e29b-41d4-a716-446655440000",
  "role": "assistant",
  "content": "你好！我是智能助手，有什么可以帮助你的吗？",
  "content_type": "text",
  "intent": "greeting",
  "entities": [],
  "created_at": "2026-04-30T12:00:00"
}
```

### 获取对话列表

**GET** `/chat/conversations`

**查询参数:**

| 字段         | 类型  | 说明        |
| ---------- | --- | --------- |
| page       | int | 页码，默认1    |
| page\_size | int | 每页数量，默认20 |

**响应示例:**

```json
{
  "conversations": [
    {
      "id": "660e8400...",
      "title": "新对话",
      "is_pinned": false,
      "message_count": 5,
      "created_at": "2026-04-30T12:00:00",
      "updated_at": "2026-04-30T12:30:00"
    }
  ],
  "total": 10
}
```

### 创建新对话

**POST** `/chat/conversations`

**请求参数:**

| 字段    | 类型     | 必填 | 说明   |
| ----- | ------ | -- | ---- |
| title | string | 否  | 对话标题 |

### 获取对话详情

**GET** `/chat/conversations/{conversation_id}`

### 更新对话

**PUT** `/chat/conversations/{conversation_id}`

**请求参数:**

| 字段         | 类型      | 必填 | 说明   |
| ---------- | ------- | -- | ---- |
| title      | string  | 否  | 对话标题 |
| is\_pinned | boolean | 否  | 是否置顶 |

### 删除对话

**DELETE** `/chat/conversations/{conversation_id}`

### 获取消息列表

**GET** `/chat/conversations/{conversation_id}/messages`

**查询参数:**

| 字段         | 类型  | 说明        |
| ---------- | --- | --------- |
| page       | int | 页码，默认1    |
| page\_size | int | 每页数量，默认50 |

**响应示例:**

```json
{
  "messages": [
    {
      "id": "770e8400...",
      "conversation_id": "660e8400...",
      "role": "user",
      "content": "你好",
      "content_type": "text",
      "media_url": null,
      "intent": null,
      "entities": null,
      "is_read": true,
      "created_at": "2026-04-30T12:00:00"
    }
  ],
  "total": 10,
  "has_more": false
}
```

### 标记消息已读

**PUT** `/chat/conversations/{conversation_id}/read`

### 输入提示

**POST** `/chat/typing`

**请求参数:**

| 字段      | 类型     | 必填 | 说明     |
| ------- | ------ | -- | ------ |
| content | string | 是  | 当前输入内容 |

**响应示例:**

```json
{
  "suggestions": ["你好", "帮我", "什么是"]
}
```

### 搜索消息

**POST** `/chat/search`

**请求参数:**

| 字段               | 类型     | 必填 | 说明        |
| ---------------- | ------ | -- | --------- |
| keyword          | string | 是  | 搜索关键词     |
| conversation\_id | string | 否  | 限定对话ID    |
| page             | int    | 否  | 页码，默认1    |
| page\_size       | int    | 否  | 每页数量，默认20 |

***

## 设置接口

### 获取机器人角色列表

**GET** `/settings/bot-roles`

**响应示例:**

```json
{
  "roles": {
    "assistant": {
      "name": "智能助手",
      "description": "乐于帮助用户解决问题",
      "icon": "🤖"
    },
    "tutor": {
      "name": "耐心老师",
      "description": "善于用简单易懂的方式解释概念",
      "icon": "👨‍🏫"
    }
  }
}
```

### 获取对话风格列表

**GET** `/settings/dialogue-styles`

### 设置机器人角色

**PUT** `/settings/bot-role?role={role}`

### 设置对话风格

**PUT** `/settings/dialogue-style?style={style}`

### 获取常见问题

**GET** `/settings/faq`

### 获取帮助信息

**GET** `/settings/help`

***

## 错误码

| 状态码 | 说明       |
| --- | -------- |
| 200 | 请求成功     |
| 400 | 请求参数错误   |
| 401 | 未认证或认证过期 |
| 403 | 无权限访问    |
| 404 | 资源不存在    |
| 429 | 请求过于频繁   |
| 500 | 服务器内部错误  |

## 限流规则

- 登录接口: 10次/分钟
- 消息发送: 30次/分钟
- 其他接口: 60次/分钟

