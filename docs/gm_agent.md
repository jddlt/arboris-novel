# 小说 GM Agent 开发文档

本文档描述 Arboris 小说管理 AI（GM Agent）的功能设计与实现规范。GM Agent 是每本小说的专属智能助手，拥有完整的小说知识和操作权限，用户可通过自然语言对话来管理和优化小说的各项设定。

---

## 1. 功能概述

### 1.1 核心理念

- **对话式管理**：用户通过自然语言与 GM 对话，无需手动填写表单
- **预览确认机制**：所有修改操作先预览，用户确认后再执行
- **完整知识库**：GM 拥有小说的全部上下文（蓝图、角色、章节、RAG 搜索能力）
- **工具调用能力**：基于 Function Calling 实现结构化操作

### 1.2 典型使用场景

| 场景 | 用户输入示例 | GM 响应 |
|------|--------------|---------|
| 创建角色 | "新增3个性格鲜明的配角" | 生成3个角色卡片，用户可逐个应用 |
| 完善角色 | "给张三加点背景故事，要有悲剧色彩" | 返回修改后的角色信息 diff |
| 建立关系 | "让张三和李四是青梅竹马" | 添加关系预览 |
| 扩展大纲 | "第5章太单薄了，帮我拆成3章" | 返回新的章节大纲列表 |
| 优化剧情 | "第10章的转折太突兀，帮我优化" | 获取章节内容并提供修改建议 |
| 查询剧情 | "主角什么时候获得的青龙剑" | RAG 搜索并返回相关片段 |
| 一致性检查 | "帮我检查王五这个角色有没有前后矛盾" | 分析角色在各章节的表现 |

---

## 2. Agent 知识范围

GM Agent 在对话时可访问的上下文信息：

| 类别 | 内容 | 加载方式 | 说明 |
|------|------|----------|------|
| 基础信息 | 标题、题材、风格、基调、简介 | System Prompt | 始终加载 |
| 世界观 | 世界设定 JSON | System Prompt | 始终加载 |
| 角色库 | 所有角色详情 | System Prompt | 始终加载 |
| 关系网 | 所有角色关系 | System Prompt | 始终加载 |
| 章节大纲 | 所有章节标题+摘要 | System Prompt | 始终加载 |
| 章节摘要 | 已完成章节的 AI 摘要 | System Prompt | 始终加载 |
| 章节全文 | 具体章节的完整内容 | 工具调用 | 按需获取 |
| 语义搜索 | 根据问题搜索相关剧情 | 工具调用(RAG) | 按需获取 |

---

## 3. 工具定义

### 3.1 工具清单总览

共 18 个工具，分为 7 类：

```
┌─────────────────────────────────────────────────────────────────┐
│                      GM Agent Tools (18个)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📚 基础信息 (1)                                                │
│  └── update_novel_info                                          │
│                                                                 │
│  🌍 世界观 (1)                                                  │
│  └── update_world_setting                                       │
│                                                                 │
│  👤 角色 (4)                                                    │
│  ├── add_character                                              │
│  ├── update_character                                           │
│  ├── delete_character                                           │
│  └── get_character                                              │
│                                                                 │
│  🔗 关系 (3)                                                    │
│  ├── add_relationship                                           │
│  ├── update_relationship                                        │
│  └── delete_relationship                                        │
│                                                                 │
│  📖 大纲 (5)                                                    │
│  ├── add_outline                                                │
│  ├── update_outline                                             │
│  ├── delete_outline                                             │
│  ├── insert_outline                                             │
│  └── reorder_outlines                                           │
│                                                                 │
│  📝 章节 (2)                                                    │
│  ├── get_chapter_content                                        │
│  └── update_chapter_content                                     │
│                                                                 │
│  🔍 搜索分析 (2)                                                │
│  ├── search_novel                                               │
│  └── analyze_consistency                                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 工具详细定义

#### 📚 基础信息

##### update_novel_info

修改小说基础信息。

```json
{
  "name": "update_novel_info",
  "description": "修改小说的基础信息，如标题、题材、风格等",
  "parameters": {
    "type": "object",
    "properties": {
      "title": { "type": "string", "description": "小说标题" },
      "genre": { "type": "string", "description": "题材类型" },
      "style": { "type": "string", "description": "写作风格" },
      "tone": { "type": "string", "description": "整体基调" },
      "one_sentence_summary": { "type": "string", "description": "一句话简介" },
      "full_synopsis": { "type": "string", "description": "完整故事大纲" }
    }
  }
}
```

#### 🌍 世界观

##### update_world_setting

修改世界观设定。

```json
{
  "name": "update_world_setting",
  "description": "修改小说的世界观设定",
  "parameters": {
    "type": "object",
    "properties": {
      "world_setting": {
        "type": "object",
        "description": "世界观设定对象，包含背景、规则、势力、地点等"
      }
    },
    "required": ["world_setting"]
  }
}
```

#### 👤 角色管理

##### add_character

新增角色。

```json
{
  "name": "add_character",
  "description": "向小说中添加新角色",
  "parameters": {
    "type": "object",
    "properties": {
      "name": { "type": "string", "description": "角色名称" },
      "role": {
        "type": "string",
        "enum": ["主角", "配角", "反派", "龙套"],
        "description": "角色定位"
      },
      "personality": { "type": "string", "description": "性格特点" },
      "background": { "type": "string", "description": "背景故事" },
      "abilities": { "type": "string", "description": "能力/技能" },
      "goals": { "type": "string", "description": "目标/动机" },
      "appearance": { "type": "string", "description": "外貌描述" }
    },
    "required": ["name", "role", "personality"]
  }
}
```

##### update_character

修改角色信息。

```json
{
  "name": "update_character",
  "description": "修改已有角色的信息",
  "parameters": {
    "type": "object",
    "properties": {
      "character_id": { "type": "string", "description": "角色ID" },
      "character_name": { "type": "string", "description": "角色名称（用于查找）" },
      "updates": {
        "type": "object",
        "description": "要更新的字段",
        "properties": {
          "name": { "type": "string" },
          "role": { "type": "string" },
          "personality": { "type": "string" },
          "background": { "type": "string" },
          "abilities": { "type": "string" },
          "goals": { "type": "string" },
          "appearance": { "type": "string" }
        }
      }
    },
    "required": ["updates"]
  }
}
```

##### delete_character

删除角色。

```json
{
  "name": "delete_character",
  "description": "从小说中删除角色",
  "parameters": {
    "type": "object",
    "properties": {
      "character_id": { "type": "string", "description": "角色ID" },
      "character_name": { "type": "string", "description": "角色名称（用于查找）" }
    }
  }
}
```

##### get_character

获取角色详情。

```json
{
  "name": "get_character",
  "description": "获取角色的完整信息",
  "parameters": {
    "type": "object",
    "properties": {
      "character_name": { "type": "string", "description": "角色名称" }
    },
    "required": ["character_name"]
  }
}
```

#### 🔗 关系管理

##### add_relationship

新增角色关系。

```json
{
  "name": "add_relationship",
  "description": "添加两个角色之间的关系",
  "parameters": {
    "type": "object",
    "properties": {
      "from_character": { "type": "string", "description": "关系主体角色名" },
      "to_character": { "type": "string", "description": "关系客体角色名" },
      "relationship_type": {
        "type": "string",
        "enum": ["盟友", "敌人", "恋人", "师徒", "亲属", "朋友", "宿敌", "暧昧", "其他"],
        "description": "关系类型"
      },
      "description": { "type": "string", "description": "关系详细描述" }
    },
    "required": ["from_character", "to_character", "relationship_type"]
  }
}
```

##### update_relationship

修改角色关系。

```json
{
  "name": "update_relationship",
  "description": "修改已有的角色关系",
  "parameters": {
    "type": "object",
    "properties": {
      "from_character": { "type": "string", "description": "关系主体角色名" },
      "to_character": { "type": "string", "description": "关系客体角色名" },
      "relationship_type": { "type": "string", "description": "新的关系类型" },
      "description": { "type": "string", "description": "新的关系描述" }
    },
    "required": ["from_character", "to_character"]
  }
}
```

##### delete_relationship

删除角色关系。

```json
{
  "name": "delete_relationship",
  "description": "删除两个角色之间的关系",
  "parameters": {
    "type": "object",
    "properties": {
      "from_character": { "type": "string", "description": "关系主体角色名" },
      "to_character": { "type": "string", "description": "关系客体角色名" }
    },
    "required": ["from_character", "to_character"]
  }
}
```

#### 📖 大纲管理

##### add_outline

新增章节大纲。

```json
{
  "name": "add_outline",
  "description": "在末尾添加新的章节大纲",
  "parameters": {
    "type": "object",
    "properties": {
      "chapter_number": { "type": "integer", "description": "章节编号" },
      "title": { "type": "string", "description": "章节标题" },
      "summary": { "type": "string", "description": "章节摘要/大纲" }
    },
    "required": ["chapter_number", "title", "summary"]
  }
}
```

##### update_outline

修改章节大纲。

```json
{
  "name": "update_outline",
  "description": "修改已有章节的大纲",
  "parameters": {
    "type": "object",
    "properties": {
      "chapter_number": { "type": "integer", "description": "章节编号" },
      "title": { "type": "string", "description": "新的章节标题" },
      "summary": { "type": "string", "description": "新的章节摘要" }
    },
    "required": ["chapter_number"]
  }
}
```

##### delete_outline

删除章节大纲。

```json
{
  "name": "delete_outline",
  "description": "删除指定章节的大纲",
  "parameters": {
    "type": "object",
    "properties": {
      "chapter_number": { "type": "integer", "description": "要删除的章节编号" }
    },
    "required": ["chapter_number"]
  }
}
```

##### insert_outline

在指定位置插入章节大纲。

```json
{
  "name": "insert_outline",
  "description": "在指定位置插入新章节，后续章节编号自动递增",
  "parameters": {
    "type": "object",
    "properties": {
      "insert_after": { "type": "integer", "description": "在此章节后插入（0表示插入到开头）" },
      "title": { "type": "string", "description": "新章节标题" },
      "summary": { "type": "string", "description": "新章节摘要" }
    },
    "required": ["insert_after", "title", "summary"]
  }
}
```

##### reorder_outlines

批量调整章节顺序。

```json
{
  "name": "reorder_outlines",
  "description": "重新排列章节顺序",
  "parameters": {
    "type": "object",
    "properties": {
      "new_order": {
        "type": "array",
        "items": { "type": "integer" },
        "description": "新的章节顺序，如 [3, 1, 2] 表示原第3章变第1章"
      }
    },
    "required": ["new_order"]
  }
}
```

#### 📝 章节内容

##### get_chapter_content

获取章节完整内容。

```json
{
  "name": "get_chapter_content",
  "description": "获取指定章节的完整内容",
  "parameters": {
    "type": "object",
    "properties": {
      "chapter_number": { "type": "integer", "description": "章节编号" }
    },
    "required": ["chapter_number"]
  }
}
```

##### update_chapter_content

修改章节内容。

```json
{
  "name": "update_chapter_content",
  "description": "修改指定章节的内容（谨慎操作）",
  "parameters": {
    "type": "object",
    "properties": {
      "chapter_number": { "type": "integer", "description": "章节编号" },
      "content": { "type": "string", "description": "新的章节内容" },
      "title": { "type": "string", "description": "新的章节标题（可选）" }
    },
    "required": ["chapter_number", "content"]
  }
}
```

#### 🔍 搜索分析

##### search_novel

语义搜索小说内容。

```json
{
  "name": "search_novel",
  "description": "使用语义搜索在小说中查找相关内容",
  "parameters": {
    "type": "object",
    "properties": {
      "query": { "type": "string", "description": "搜索关键词或问题" },
      "top_k": { "type": "integer", "description": "返回结果数量，默认5" }
    },
    "required": ["query"]
  }
}
```

##### analyze_consistency

分析一致性。

```json
{
  "name": "analyze_consistency",
  "description": "分析角色或剧情的一致性，检查是否有前后矛盾",
  "parameters": {
    "type": "object",
    "properties": {
      "target": { "type": "string", "description": "分析目标（角色名或'剧情'）" },
      "aspect": {
        "type": "string",
        "enum": ["性格", "能力", "关系", "时间线", "全面"],
        "description": "分析维度"
      }
    },
    "required": ["target"]
  }
}
```

---

## 4. 实现优先级

### P0 核心功能（11个工具）

首期实现，覆盖最常用操作：

- 角色：`add_character`, `update_character`, `delete_character`, `get_character`
- 关系：`add_relationship`, `update_relationship`, `delete_relationship`
- 大纲：`add_outline`, `update_outline`, `delete_outline`
- 搜索：`search_novel`

### P1 增强功能（4个工具）

二期实现，补充世界观和章节操作：

- `update_novel_info`
- `update_world_setting`
- `get_chapter_content`
- `update_chapter_content`

### P2 高级功能（3个工具）

三期实现，增加高级编辑和分析：

- `insert_outline`
- `reorder_outlines`
- `analyze_consistency`

---

## 5. 数据模型

### 5.1 新增表

```python
# 对话历史
class GMConversation(Base):
    __tablename__ = "gm_conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("novel_projects.id"))
    title: Mapped[Optional[str]] = mapped_column(String(200))  # 对话标题（可自动生成）
    messages: Mapped[dict] = mapped_column(JSON)  # [{role, content, tool_calls}]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


# 待执行操作
class GMPendingAction(Base):
    __tablename__ = "gm_pending_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("gm_conversations.id"))
    message_index: Mapped[int] = mapped_column(Integer)  # 属于哪条消息
    tool_name: Mapped[str] = mapped_column(String(50))
    params: Mapped[dict] = mapped_column(JSON)
    preview_text: Mapped[str] = mapped_column(Text)  # 用于前端展示的预览
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/applied/discarded
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


# 操作历史（支持撤销）
class GMActionHistory(Base):
    __tablename__ = "gm_action_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("novel_projects.id"))
    action_id: Mapped[str] = mapped_column(String(36))  # 关联 GMPendingAction
    tool_name: Mapped[str] = mapped_column(String(50))
    params: Mapped[dict] = mapped_column(JSON)
    before_state: Mapped[Optional[dict]] = mapped_column(JSON)  # 操作前快照
    after_state: Mapped[Optional[dict]] = mapped_column(JSON)   # 操作后快照
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    reverted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)  # 撤销时间
```

### 5.2 关联关系

```
NovelProject
    │
    ├── GMConversation (1:N)
    │       │
    │       └── GMPendingAction (1:N)
    │
    └── GMActionHistory (1:N)
```

---

## 6. API 设计

### 6.1 对话接口

#### POST /api/novels/{project_id}/gm/chat

发送消息给 GM Agent。

**请求体：**
```json
{
  "message": "新增3个性格鲜明的配角",
  "conversation_id": "uuid-optional"  // 可选，不传则创建新对话
}
```

**响应：**
```json
{
  "conversation_id": "uuid",
  "message": "根据你的故事设定，我建议新增以下角色：...",
  "pending_actions": [
    {
      "action_id": "uuid-1",
      "tool_name": "add_character",
      "params": {
        "name": "沈墨",
        "role": "配角",
        "personality": "表面疯癫，实则洞察一切"
      },
      "preview": "新增角色「沈墨」- 配角，性格：表面疯癫，实则洞察一切"
    }
  ]
}
```

### 6.2 操作执行接口

#### POST /api/novels/{project_id}/gm/apply

应用待执行操作。

**请求体：**
```json
{
  "action_ids": ["uuid-1", "uuid-2"]  // 支持批量
}
```

**响应：**
```json
{
  "success": true,
  "applied": ["uuid-1", "uuid-2"],
  "results": [
    { "action_id": "uuid-1", "message": "角色「沈墨」已添加" }
  ]
}
```

#### POST /api/novels/{project_id}/gm/discard

放弃待执行操作。

**请求体：**
```json
{
  "action_ids": ["uuid-1"]
}
```

### 6.3 对话管理接口

#### GET /api/novels/{project_id}/gm/conversations

获取对话列表。

#### GET /api/novels/{project_id}/gm/conversations/{conversation_id}

获取对话详情（含历史消息）。

#### DELETE /api/novels/{project_id}/gm/conversations/{conversation_id}

删除对话。

---

## 7. 前端组件设计

### 7.1 页面结构

```
┌─────────────────────────────────────────────────────────────────┐
│  小说详情页 - 新增入口                                           │
├─────────────────────────────────────────────────────────────────┤
│  [大纲] [章节] [角色] [世界观] [🤖 GM助手]  ◀── 新Tab            │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 GM 对话界面

```
┌─────────────────────────────────────────────────────────────────┐
│  🤖 小说GM助手                                    [新建对话] ▼   │
├───────────────────────┬─────────────────────────────────────────┤
│  对话历史              │                                         │
│  ├─ 角色设计讨论       │  ┌─────────────────────────────────┐    │
│  ├─ 大纲优化          │  │ 👤 新增3个性格鲜明的配角          │    │
│  └─ 剧情调整          │  └─────────────────────────────────┘    │
│                       │                                         │
│                       │  ┌─────────────────────────────────┐    │
│                       │  │ 🤖 根据你的故事设定，建议：       │    │
│                       │  │                                 │    │
│                       │  │ ┌─────────────────────────────┐ │    │
│                       │  │ │ 📝 新增角色: 沈墨            │ │    │
│                       │  │ │ 定位: 配角                  │ │    │
│                       │  │ │ 性格: 表面疯癫...           │ │    │
│                       │  │ │            [应用] [放弃]    │ │    │
│                       │  │ └─────────────────────────────┘ │    │
│                       │  │                                 │    │
│                       │  │ ┌─────────────────────────────┐ │    │
│                       │  │ │ 📝 新增角色: 苏晴            │ │    │
│                       │  │ │ ...                         │ │    │
│                       │  │ └─────────────────────────────┘ │    │
│                       │  │                                 │    │
│                       │  │       [全部应用] [全部放弃]      │    │
│                       │  └─────────────────────────────────┘    │
│                       │                                         │
│                       │  ┌─────────────────────────────[发送]   │
│                       │  │ 把沈墨改成更阴沉一些...              │
│                       │  └─────────────────────────────────┘    │
└───────────────────────┴─────────────────────────────────────────┘
```

### 7.3 操作卡片组件

```vue
<!-- ActionCard.vue -->
<template>
  <div class="action-card" :class="{ applied: action.status === 'applied' }">
    <div class="action-header">
      <span class="action-icon">{{ getIcon(action.tool_name) }}</span>
      <span class="action-title">{{ getTitle(action) }}</span>
      <span class="action-status" v-if="action.status !== 'pending'">
        {{ action.status === 'applied' ? '✓ 已应用' : '✗ 已放弃' }}
      </span>
    </div>
    <div class="action-preview">
      {{ action.preview }}
    </div>
    <div class="action-buttons" v-if="action.status === 'pending'">
      <button @click="$emit('apply')" class="btn-apply">应用</button>
      <button @click="$emit('discard')" class="btn-discard">放弃</button>
    </div>
  </div>
</template>
```

---

## 8. 后端实现结构

### 8.1 架构原则

- **功能原子化**：每个工具独立一个执行器，互不依赖
- **职责单一**：Service 只做编排，Repository 只做数据访问，Executor 只做业务逻辑
- **易于扩展**：新增工具只需添加一个 Executor 类，无需修改核心代码
- **统一接口**：所有工具执行器实现相同的基类接口

### 8.2 文件结构

```
backend/
├── app/
│   ├── api/
│   │   └── routers/
│   │       └── gm.py                    # GM Agent API 路由（薄层，只做参数校验和响应格式化）
│   │
│   ├── services/
│   │   └── gm/
│   │       ├── __init__.py
│   │       ├── gm_service.py            # GM 对话编排服务（核心调度）
│   │       ├── context_builder.py       # 上下文构建器（负责组装 System Prompt）
│   │       └── tool_registry.py         # 工具注册表（管理所有工具定义）
│   │
│   ├── executors/                       # 工具执行器（每个工具一个文件）
│   │   └── gm/
│   │       ├── __init__.py
│   │       ├── base.py                  # 执行器基类
│   │       ├── character/               # 角色相关执行器
│   │       │   ├── __init__.py
│   │       │   ├── add_character.py
│   │       │   ├── update_character.py
│   │       │   ├── delete_character.py
│   │       │   └── get_character.py
│   │       ├── relationship/            # 关系相关执行器
│   │       │   ├── __init__.py
│   │       │   ├── add_relationship.py
│   │       │   ├── update_relationship.py
│   │       │   └── delete_relationship.py
│   │       ├── outline/                 # 大纲相关执行器
│   │       │   ├── __init__.py
│   │       │   ├── add_outline.py
│   │       │   ├── update_outline.py
│   │       │   ├── delete_outline.py
│   │       │   ├── insert_outline.py
│   │       │   └── reorder_outlines.py
│   │       ├── chapter/                 # 章节相关执行器
│   │       │   ├── __init__.py
│   │       │   ├── get_chapter_content.py
│   │       │   └── update_chapter_content.py
│   │       ├── novel/                   # 小说基础信息执行器
│   │       │   ├── __init__.py
│   │       │   ├── update_novel_info.py
│   │       │   └── update_world_setting.py
│   │       └── search/                  # 搜索分析执行器
│   │           ├── __init__.py
│   │           ├── search_novel.py
│   │           └── analyze_consistency.py
│   │
│   ├── models/
│   │   └── gm.py                        # GM 相关数据模型
│   │
│   └── repositories/
│       └── gm_repository.py             # GM 数据访问层
│
└── prompts/
    └── gm_system.md                     # GM Agent 系统提示词
```

### 8.3 核心类设计

#### 执行器基类

```python
# app/executors/gm/base.py

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    before_state: Optional[Dict[str, Any]] = None  # 用于撤销
    after_state: Optional[Dict[str, Any]] = None


@dataclass
class ToolDefinition:
    """工具定义（用于 Function Calling）"""
    name: str
    description: str
    parameters: Dict[str, Any]


class BaseToolExecutor(ABC):
    """工具执行器基类 - 所有工具必须继承此类"""

    def __init__(self, session: AsyncSession):
        self.session = session

    @classmethod
    @abstractmethod
    def get_definition(cls) -> ToolDefinition:
        """返回工具的 Function Calling 定义"""
        pass

    @classmethod
    @abstractmethod
    def get_name(cls) -> str:
        """返回工具名称"""
        pass

    @abstractmethod
    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        """执行工具逻辑"""
        pass

    @abstractmethod
    def generate_preview(self, params: Dict[str, Any]) -> str:
        """生成操作预览文本（用于前端展示）"""
        pass

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        """参数校验，返回错误信息或 None"""
        return None
```

#### 工具注册表

```python
# app/services/gm/tool_registry.py

from typing import Dict, Type, List
from app.executors.gm.base import BaseToolExecutor, ToolDefinition


class ToolRegistry:
    """工具注册表 - 管理所有可用工具"""

    _executors: Dict[str, Type[BaseToolExecutor]] = {}

    @classmethod
    def register(cls, executor_class: Type[BaseToolExecutor]) -> Type[BaseToolExecutor]:
        """装饰器：注册工具执行器"""
        cls._executors[executor_class.get_name()] = executor_class
        return executor_class

    @classmethod
    def get_executor(cls, tool_name: str) -> Type[BaseToolExecutor]:
        """获取工具执行器类"""
        if tool_name not in cls._executors:
            raise ValueError(f"Unknown tool: {tool_name}")
        return cls._executors[tool_name]

    @classmethod
    def get_all_definitions(cls) -> List[Dict]:
        """获取所有工具的 Function Calling 定义"""
        return [
            {
                "type": "function",
                "function": {
                    "name": executor.get_name(),
                    "description": executor.get_definition().description,
                    "parameters": executor.get_definition().parameters,
                }
            }
            for executor in cls._executors.values()
        ]

    @classmethod
    def get_tool_names(cls) -> List[str]:
        """获取所有工具名称"""
        return list(cls._executors.keys())
```

#### 具体执行器示例

```python
# app/executors/gm/character/add_character.py

from app.executors.gm.base import BaseToolExecutor, ToolDefinition, ToolResult
from app.services.gm.tool_registry import ToolRegistry


@ToolRegistry.register
class AddCharacterExecutor(BaseToolExecutor):
    """添加角色执行器"""

    @classmethod
    def get_name(cls) -> str:
        return "add_character"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="add_character",
            description="向小说中添加新角色",
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "角色名称"},
                    "role": {
                        "type": "string",
                        "enum": ["主角", "配角", "反派", "龙套"],
                        "description": "角色定位"
                    },
                    "personality": {"type": "string", "description": "性格特点"},
                    "background": {"type": "string", "description": "背景故事"},
                    "abilities": {"type": "string", "description": "能力/技能"},
                    "goals": {"type": "string", "description": "目标/动机"},
                },
                "required": ["name", "role", "personality"]
            }
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        return f"新增角色「{params['name']}」- {params['role']}，性格：{params['personality']}"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        if not params.get("name"):
            return "角色名称不能为空"
        if len(params.get("name", "")) > 50:
            return "角色名称不能超过50字"
        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        # 1. 获取项目
        project = await self._get_project(project_id)

        # 2. 获取当前角色列表
        characters = project.blueprint.get("characters", [])
        before_state = {"characters": characters.copy()}

        # 3. 检查重名
        if any(c["name"] == params["name"] for c in characters):
            return ToolResult(
                success=False,
                message=f"角色「{params['name']}」已存在"
            )

        # 4. 添加新角色
        new_character = {
            "id": str(uuid4()),
            "name": params["name"],
            "role": params["role"],
            "personality": params["personality"],
            "background": params.get("background", ""),
            "abilities": params.get("abilities", ""),
            "goals": params.get("goals", ""),
        }
        characters.append(new_character)

        # 5. 保存
        await self._update_blueprint(project_id, {"characters": characters})

        return ToolResult(
            success=True,
            message=f"角色「{params['name']}」已添加",
            data={"character": new_character},
            before_state=before_state,
            after_state={"characters": characters}
        )

    async def _get_project(self, project_id: str):
        """获取项目（可抽取到基类）"""
        from app.repositories.novel_repository import NovelRepository
        repo = NovelRepository(self.session)
        return await repo.get_by_id(project_id)

    async def _update_blueprint(self, project_id: str, updates: dict):
        """更新蓝图（可抽取到基类）"""
        from app.services.novel_service import NovelService
        service = NovelService(self.session)
        await service.update_blueprint(project_id, updates)
```

#### GM Service（编排层）

```python
# app/services/gm/gm_service.py

class GMService:
    """GM Agent 对话编排服务 - 只负责调度，不包含业务逻辑"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.llm_service = LLMService(session)
        self.gm_repo = GMRepository(session)
        self.context_builder = ContextBuilder(session)

    async def chat(
        self,
        project_id: str,
        message: str,
        conversation_id: Optional[str] = None,
        user_id: int = None,
    ) -> GMChatResponse:
        """处理对话 - 纯编排逻辑"""

        # 1. 对话管理
        conversation = await self.gm_repo.get_or_create_conversation(
            project_id, conversation_id
        )

        # 2. 构建上下文（委托给 ContextBuilder）
        context = await self.context_builder.build(project_id)

        # 3. 获取工具定义（从 Registry）
        tools = ToolRegistry.get_all_definitions()

        # 4. 调用 LLM
        response = await self.llm_service.chat_with_tools(
            system_prompt=self._load_system_prompt() + context,
            messages=conversation.messages + [{"role": "user", "content": message}],
            tools=tools,
        )

        # 5. 创建待执行操作
        pending_actions = await self._create_pending_actions(
            conversation.id, response.tool_calls
        )

        # 6. 保存对话
        await self.gm_repo.append_message(conversation.id, message, response, pending_actions)

        return GMChatResponse(
            conversation_id=conversation.id,
            message=response.content,
            pending_actions=pending_actions,
        )

    async def apply_actions(self, project_id: str, action_ids: List[str]) -> ApplyResult:
        """执行操作 - 委托给具体执行器"""
        results = []

        for action_id in action_ids:
            action = await self.gm_repo.get_pending_action(action_id)

            # 获取执行器
            executor_class = ToolRegistry.get_executor(action.tool_name)
            executor = executor_class(self.session)

            # 参数校验
            error = await executor.validate_params(action.params)
            if error:
                results.append(ToolResult(success=False, message=error))
                continue

            # 执行
            result = await executor.execute(project_id, action.params)

            # 记录历史
            await self.gm_repo.record_history(project_id, action, result)

            # 更新状态
            await self.gm_repo.update_action_status(
                action_id,
                "applied" if result.success else "failed"
            )

            results.append(result)

        return ApplyResult(applied=action_ids, results=results)

    async def _create_pending_actions(
        self,
        conversation_id: str,
        tool_calls: List[dict]
    ) -> List[GMPendingAction]:
        """解析 LLM 工具调用，创建待执行操作"""
        actions = []
        for call in tool_calls:
            executor_class = ToolRegistry.get_executor(call["name"])
            executor = executor_class(self.session)

            action = GMPendingAction(
                id=str(uuid4()),
                conversation_id=conversation_id,
                tool_name=call["name"],
                params=call["arguments"],
                preview_text=executor.generate_preview(call["arguments"]),
                status="pending",
            )
            await self.gm_repo.save_pending_action(action)
            actions.append(action)

        return actions
```

### 8.4 扩展新工具的步骤

添加新工具只需 3 步：

1. **创建执行器文件**
```python
# app/executors/gm/xxx/new_tool.py

@ToolRegistry.register
class NewToolExecutor(BaseToolExecutor):
    @classmethod
    def get_name(cls) -> str:
        return "new_tool"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(...)

    def generate_preview(self, params: Dict) -> str:
        return "..."

    async def execute(self, project_id: str, params: Dict) -> ToolResult:
        # 业务逻辑
        pass
```

2. **在 `__init__.py` 中导入**
```python
# app/executors/gm/xxx/__init__.py
from .new_tool import NewToolExecutor
```

3. **完成**（无需修改其他文件）

### 8.5 层级职责总结

| 层级 | 文件 | 职责 | 原则 |
|------|------|------|------|
| **API** | `routers/gm.py` | 参数校验、响应格式化 | 薄层，不含业务逻辑 |
| **Service** | `gm_service.py` | 流程编排、调度 | 只做组装，不做实现 |
| **Executor** | `executors/gm/*.py` | 具体业务逻辑 | 单一职责，一个工具一个类 |
| **Repository** | `gm_repository.py` | 数据访问 | 纯 CRUD，无业务逻辑 |
| **Registry** | `tool_registry.py` | 工具管理 | 自动发现，统一接口 |

---

## 9. System Prompt 设计

```markdown
# backend/prompts/gm_system.md

你是这本小说的 GM（Game Master），拥有完整的创作权限。你的职责是帮助作者完善小说的各项设定，包括角色、关系、大纲、世界观等。

## 你的能力

你可以通过调用工具来：
- 添加、修改、删除角色
- 管理角色之间的关系
- 调整章节大纲
- 修改世界观设定
- 搜索小说内容
- 分析剧情一致性

## 工作原则

1. **理解意图**：仔细理解用户的需求，必要时请求澄清
2. **创意建议**：基于现有设定提供有创意但合理的建议
3. **保持一致**：确保新增内容与现有设定不冲突
4. **批量操作**：当用户要求多个修改时，一次性返回所有操作
5. **解释说明**：简要解释为什么这样设计

## 当前小说信息

{novel_context}

## 注意事项

- 所有修改操作都需要用户确认后才会生效
- 对于重大修改（如删除角色、修改主线剧情），请提醒用户谨慎
- 如果用户的要求可能导致剧情矛盾，请指出并建议解决方案
```

---

## 10. 开发计划

### Phase 1: 基础框架
- [ ] 数据模型定义与迁移
- [ ] GM Service 基础结构
- [ ] 对话 API 接口
- [ ] 前端对话界面骨架

### Phase 2: P0 工具实现
- [ ] 角色管理工具（4个）
- [ ] 关系管理工具（3个）
- [ ] 大纲管理工具（3个）
- [ ] 搜索工具（1个）

### Phase 3: 前端完善
- [ ] 操作卡片组件
- [ ] 应用/放弃交互
- [ ] 对话历史管理

### Phase 4: P1/P2 工具
- [ ] 世界观修改
- [ ] 章节内容操作
- [ ] 一致性分析

### Phase 5: 优化
- [ ] 操作历史与撤销
- [ ] 上下文压缩优化
- [ ] 性能调优

---

## 附录：参考资料

- [OpenAI Function Calling 文档](https://platform.openai.com/docs/guides/function-calling)
- [现有小说工作流文档](./novel_workflow.md)
- [RAG 实现文档](./RAG.md)
