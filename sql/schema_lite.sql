-- SQLite schema for fastfish-lite（开源精简版）
-- 不含微信、激活、账号相关表
PRAGMA foreign_keys = OFF;

-- 1. 本地用户（单机可仅一条）
DROP TABLE IF EXISTS local_user;
CREATE TABLE local_user (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL,
    nickname        TEXT,
    status          TEXT DEFAULT 'normal',
    create_time     INTEGER,
    update_time     INTEGER
);

-- 2. 媒体平台（种子数据占位）
DROP TABLE IF EXISTS media_platform;
CREATE TABLE media_platform (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    code            TEXT NOT NULL,
    api_base_url    TEXT,
    status          INTEGER DEFAULT 1,
    create_time     INTEGER,
    update_time     INTEGER
);

-- 3. 原始文章池
DROP TABLE IF EXISTS hot_article;
CREATE TABLE hot_article (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id             INTEGER DEFAULT 0,
    category_id         INTEGER DEFAULT 0,
    source_title        TEXT,
    source_pic          TEXT,
    source_content      TEXT,
    source_url          TEXT,
    rewritten_title     TEXT,
    rewritten_pic       TEXT,
    rewritten_content   TEXT,
    quality_score       REAL,
    status              INTEGER DEFAULT 0,
    published_count     INTEGER DEFAULT 0,
    last_publish_time   INTEGER,
    create_time         INTEGER,
    update_time         INTEGER,
    allocation_status   INTEGER NOT NULL DEFAULT 0,
    locked_by_user_id   INTEGER DEFAULT 0,
    locked_time         INTEGER,
    source_id           INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_hot_article_allocation ON hot_article(allocation_status);
CREATE INDEX IF NOT EXISTS idx_hot_article_status ON hot_article(status);

-- 4. 改写文章池（可发稿件来源）
DROP TABLE IF EXISTS hot_article_rewritten;
CREATE TABLE hot_article_rewritten (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    original_article_id     INTEGER NOT NULL,
    style_template_id       INTEGER DEFAULT 0,
    task_id                INTEGER DEFAULT 0,
    category_id             INTEGER DEFAULT 0,
    rewritten_title        TEXT,
    rewritten_pic          TEXT,
    rewritten_content      TEXT,
    author                 TEXT,
    digest                 TEXT,
    quality_score          REAL,
    status                 INTEGER DEFAULT 0,
    allocation_status      INTEGER NOT NULL DEFAULT 0,
    locked_by_user_id      INTEGER DEFAULT 0,
    locked_time            INTEGER,
    published_count        INTEGER DEFAULT 0,
    last_publish_time      INTEGER,
    create_time            INTEGER,
    update_time            INTEGER,
    source_id              INTEGER DEFAULT 0,
    source_url             TEXT,
    format_style            TEXT DEFAULT 'minimal',
    content_format          TEXT DEFAULT 'html'
);
CREATE INDEX IF NOT EXISTS idx_hot_article_rewritten_allocation ON hot_article_rewritten(allocation_status);
CREATE INDEX IF NOT EXISTS idx_hot_article_rewritten_status ON hot_article_rewritten(status);

-- 5. 微信排版模板（精简版）
DROP TABLE IF EXISTS wechat_format_template;
CREATE TABLE wechat_format_template (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    template_name       TEXT NOT NULL,
    template_category   TEXT,
    ai_prompt           TEXT,
    css_styles          TEXT,
    html_template       TEXT,
    markdown_extensions TEXT,
    is_active           INTEGER DEFAULT 1,
    sort_order          INTEGER DEFAULT 0,
    created_at          INTEGER,
    updated_at          INTEGER
);

-- 6. 每日热点推送：原始拉取数据
DROP TABLE IF EXISTS hot_items_raw;
CREATE TABLE hot_items_raw (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL,
    title           TEXT,
    link            TEXT,
    desc_text       TEXT,
    hot             TEXT,
    rank            INTEGER DEFAULT 0,
    fetched_at      INTEGER NOT NULL,
    create_time     INTEGER
);
CREATE INDEX IF NOT EXISTS idx_hot_items_raw_source_fetched ON hot_items_raw(source, fetched_at);

-- 7. 每日热点推送：推送配置
DROP TABLE IF EXISTS hot_push_config;
CREATE TABLE hot_push_config (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    category_code       TEXT NOT NULL,
    category_name       TEXT NOT NULL,
    sources             TEXT NOT NULL,
    include_keywords    TEXT,
    exclude_keywords    TEXT,
    push_time           TEXT NOT NULL,
    im_channel          TEXT NOT NULL,
    webhook_url         TEXT NOT NULL,
    max_items           INTEGER DEFAULT 10,
    is_active           INTEGER DEFAULT 1,
    create_time         INTEGER,
    update_time         INTEGER
);

-- 8. 每日热点推送：推送历史
DROP TABLE IF EXISTS hot_push_history;
CREATE TABLE hot_push_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id       INTEGER NOT NULL,
    pushed_at       INTEGER NOT NULL,
    items_count     INTEGER DEFAULT 0,
    item_ids        TEXT,
    status          INTEGER NOT NULL DEFAULT 0,
    error_msg       TEXT,
    create_time     INTEGER,
    FOREIGN KEY (config_id) REFERENCES hot_push_config(id)
);
CREATE INDEX IF NOT EXISTS idx_hot_push_history_config_pushed ON hot_push_history(config_id, pushed_at);

PRAGMA foreign_keys = ON;
