-- SQLite 迁移脚本
-- 将旧版数据库升级到最新 schema
-- 执行方式: sqlite3 novel.db < migrate_sqlite.sql

-- ============================================
-- 1. novel_blueprints 表新增字段
-- ============================================
ALTER TABLE novel_blueprints ADD COLUMN volumes JSON;
ALTER TABLE novel_blueprints ADD COLUMN foreshadowing JSON;

-- ============================================
-- 2. volumes 表（新建）
-- ============================================
CREATE TABLE IF NOT EXISTS volumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id CHAR(36) NOT NULL,
    volume_number INTEGER NOT NULL,
    title VARCHAR(255) NOT NULL,
    summary TEXT,
    core_conflict TEXT,
    climax TEXT,
    status VARCHAR(32) DEFAULT 'planned',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES novel_projects(id) ON DELETE CASCADE,
    UNIQUE (project_id, volume_number)
);

-- ============================================
-- 3. chapter_outlines 表新增字段
-- ============================================
ALTER TABLE chapter_outlines ADD COLUMN volume_id INTEGER REFERENCES volumes(id) ON DELETE SET NULL;

-- ============================================
-- 4. gm_conversations 表（新建）
-- ============================================
CREATE TABLE IF NOT EXISTS gm_conversations (
    id CHAR(36) PRIMARY KEY,
    project_id CHAR(36) NOT NULL,
    title VARCHAR(200),
    messages JSON DEFAULT '[]',
    is_archived INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES novel_projects(id) ON DELETE CASCADE
);

-- ============================================
-- 5. gm_pending_actions 表（新建）
-- ============================================
CREATE TABLE IF NOT EXISTS gm_pending_actions (
    id CHAR(36) PRIMARY KEY,
    conversation_id CHAR(36) NOT NULL,
    message_index INTEGER NOT NULL,
    tool_name VARCHAR(64) NOT NULL,
    params JSON NOT NULL,
    preview_text TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    applied_at TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES gm_conversations(id) ON DELETE CASCADE
);

-- ============================================
-- 6. gm_action_history 表（新建）
-- ============================================
CREATE TABLE IF NOT EXISTS gm_action_history (
    id CHAR(36) PRIMARY KEY,
    project_id CHAR(36) NOT NULL,
    action_id CHAR(36) UNIQUE,
    tool_name VARCHAR(64) NOT NULL,
    params JSON NOT NULL,
    before_state JSON,
    after_state JSON,
    is_reverted INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reverted_at TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES novel_projects(id) ON DELETE CASCADE,
    FOREIGN KEY (action_id) REFERENCES gm_pending_actions(id) ON DELETE SET NULL
);

-- ============================================
-- 7. author_notes 表（新建）
-- ============================================
CREATE TABLE IF NOT EXISTS author_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id CHAR(36) NOT NULL,
    type VARCHAR(32) NOT NULL,
    chapter_number INTEGER,
    character_id INTEGER,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES novel_projects(id) ON DELETE CASCADE,
    FOREIGN KEY (character_id) REFERENCES blueprint_characters(id) ON DELETE SET NULL
);

-- ============================================
-- 8. character_states 表（新建）
-- ============================================
CREATE TABLE IF NOT EXISTS character_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL,
    chapter_number INTEGER NOT NULL,
    data JSON DEFAULT '{}',
    change_note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (character_id) REFERENCES blueprint_characters(id) ON DELETE CASCADE
);

-- ============================================
-- 9. state_templates 表（新建）
-- ============================================
CREATE TABLE IF NOT EXISTS state_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(64) UNIQUE NOT NULL,
    display_name VARCHAR(128) NOT NULL,
    description TEXT,
    schema JSON DEFAULT '{}',
    is_system INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 10. generation_contexts 表（新建）
-- ============================================
CREATE TABLE IF NOT EXISTS generation_contexts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER NOT NULL,
    selected_note_ids JSON,
    selected_state_ids JSON,
    extra_instruction TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
);

-- ============================================
-- 创建索引
-- ============================================
CREATE INDEX IF NOT EXISTS idx_gm_conversations_project ON gm_conversations(project_id);
CREATE INDEX IF NOT EXISTS idx_gm_pending_actions_conversation ON gm_pending_actions(conversation_id);
CREATE INDEX IF NOT EXISTS idx_gm_pending_actions_status ON gm_pending_actions(status);
CREATE INDEX IF NOT EXISTS idx_gm_action_history_project ON gm_action_history(project_id);
CREATE INDEX IF NOT EXISTS idx_author_notes_project ON author_notes(project_id);
CREATE INDEX IF NOT EXISTS idx_author_notes_type ON author_notes(type);
CREATE INDEX IF NOT EXISTS idx_character_states_character ON character_states(character_id);
CREATE INDEX IF NOT EXISTS idx_character_states_chapter ON character_states(chapter_number);

-- ============================================
-- 11. author_notes 表新增 volume_id 字段
-- ============================================
ALTER TABLE author_notes ADD COLUMN volume_id INTEGER REFERENCES volumes(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_author_notes_volume ON author_notes(volume_id);
