-- ================================================================
-- 金融数据爬虫项目数据库设计脚本
-- 用于存储/scrape接口抓取的金融市场数据
-- 创建时间: 2025-07-29
-- ================================================================

-- 创建数据库
CREATE DATABASE IF NOT EXISTS financial_scraper 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE financial_scraper;

-- ================================================================
-- 1. 主记录表 - 存储每次爬取的基本信息
-- ================================================================
CREATE TABLE IF NOT EXISTS scrape_records (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    scrape_time DATETIME NOT NULL COMMENT '爬取时间',
    request_time VARCHAR(100) COMMENT '请求传入的时间参数',
    total_data_sources INT DEFAULT 0 COMMENT '总数据源数量',
    successful_sources INT DEFAULT 0 COMMENT '成功获取数据的源数量',
    failed_sources INT DEFAULT 0 COMMENT '失败的数据源数量',
    processing_duration_ms INT COMMENT '处理耗时(毫秒)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_scrape_time (scrape_time),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB COMMENT='爬取记录主表';

-- ================================================================
-- 2. 全球宏观指标表 - 存储Investing.com数据
-- ================================================================
CREATE TABLE IF NOT EXISTS global_macro_indicators (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    record_id BIGINT NOT NULL COMMENT '关联scrape_records主键',
    indicator_code VARCHAR(20) NOT NULL COMMENT '指标代码(DXY,WTI,XAU_USD,USD_CNH)',
    indicator_name VARCHAR(100) COMMENT '指标名称',
    price DECIMAL(15,6) COMMENT '当前价格',
    price_text VARCHAR(50) COMMENT '原始价格文本',
    change_percent DECIMAL(8,4) COMMENT '涨跌幅百分比',
    change_percent_text VARCHAR(30) COMMENT '原始涨跌幅文本',
    is_error BOOLEAN DEFAULT FALSE COMMENT '是否获取失败',
    error_message TEXT COMMENT '错误信息',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (record_id) REFERENCES scrape_records(id) ON DELETE CASCADE,
    INDEX idx_record_indicator (record_id, indicator_code),
    INDEX idx_indicator_time (indicator_code, created_at)
) ENGINE=InnoDB COMMENT='全球宏观指标数据';

-- ================================================================
-- 3. 美股涨幅榜表 - 存储Yahoo Finance涨幅前五数据
-- ================================================================
CREATE TABLE IF NOT EXISTS us_stock_gainers (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    record_id BIGINT NOT NULL COMMENT '关联scrape_records主键',
    stock_symbol VARCHAR(20) NOT NULL COMMENT '股票代码',
    stock_name VARCHAR(200) COMMENT '股票名称',
    current_price DECIMAL(12,4) COMMENT '当前价格',
    price_change DECIMAL(10,4) COMMENT '价格变动',
    change_percent DECIMAL(8,4) COMMENT '涨跌幅百分比',
    volume BIGINT COMMENT '成交量',
    ranking_position TINYINT COMMENT '排名位置(1-5)',
    is_error BOOLEAN DEFAULT FALSE COMMENT '是否获取失败',
    error_message TEXT COMMENT '错误信息',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (record_id) REFERENCES scrape_records(id) ON DELETE CASCADE,
    INDEX idx_record_ranking (record_id, ranking_position),
    INDEX idx_symbol_time (stock_symbol, created_at)
) ENGINE=InnoDB COMMENT='美股涨幅榜数据';

-- ================================================================
-- 4. A股统计数据表 - 存储同花顺统计数据
-- ================================================================
CREATE TABLE IF NOT EXISTS a_stock_statistics (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    record_id BIGINT NOT NULL COMMENT '关联scrape_records主键',
    metric_name VARCHAR(100) NOT NULL COMMENT '统计指标名称',
    metric_value VARCHAR(200) COMMENT '指标值',
    metric_type VARCHAR(50) COMMENT '指标类型',
    additional_info JSON COMMENT '额外信息(JSON格式)',
    is_error BOOLEAN DEFAULT FALSE COMMENT '是否获取失败',
    error_message TEXT COMMENT '错误信息',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (record_id) REFERENCES scrape_records(id) ON DELETE CASCADE,
    INDEX idx_record_metric (record_id, metric_name),
    INDEX idx_metric_time (metric_name, created_at)
) ENGINE=InnoDB COMMENT='A股统计数据';

-- ================================================================
-- 5. 市场成交额表 - 存储新浪财经总成交额数据  
-- ================================================================
CREATE TABLE IF NOT EXISTS market_turnover (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    record_id BIGINT NOT NULL COMMENT '关联scrape_records主键',
    market_type VARCHAR(20) NOT NULL COMMENT '市场类型(SH沪市/SZ深市)',
    market_name VARCHAR(50) COMMENT '市场名称',
    index_value DECIMAL(10,4) COMMENT '指数点位',
    index_change DECIMAL(8,4) COMMENT '指数涨跌',
    index_change_percent DECIMAL(8,4) COMMENT '指数涨跌幅',
    total_turnover DECIMAL(20,2) COMMENT '总成交额(元)',
    turnover_text VARCHAR(100) COMMENT '原始成交额文本',
    is_error BOOLEAN DEFAULT FALSE COMMENT '是否获取失败',
    error_message TEXT COMMENT '错误信息',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (record_id) REFERENCES scrape_records(id) ON DELETE CASCADE,
    INDEX idx_record_market (record_id, market_type),
    INDEX idx_market_time (market_type, created_at)
) ENGINE=InnoDB COMMENT='市场成交额数据';

-- ================================================================
-- 6. 加密货币数据表 - 存储crypto相关数据(预留)
-- ================================================================
CREATE TABLE IF NOT EXISTS crypto_data (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    record_id BIGINT NOT NULL COMMENT '关联scrape_records主键',
    crypto_symbol VARCHAR(20) NOT NULL COMMENT '加密货币符号',
    crypto_name VARCHAR(100) COMMENT '加密货币名称',
    current_price DECIMAL(20,8) COMMENT '当前价格',
    price_change_24h DECIMAL(15,8) COMMENT '24小时价格变动',
    change_percent_24h DECIMAL(8,4) COMMENT '24小时涨跌幅',
    market_cap DECIMAL(25,2) COMMENT '市值',
    volume_24h DECIMAL(25,2) COMMENT '24小时交易量',
    is_error BOOLEAN DEFAULT FALSE COMMENT '是否获取失败',
    error_message TEXT COMMENT '错误信息',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (record_id) REFERENCES scrape_records(id) ON DELETE CASCADE,
    INDEX idx_record_crypto (record_id, crypto_symbol),
    INDEX idx_crypto_time (crypto_symbol, created_at)
) ENGINE=InnoDB COMMENT='加密货币数据';

-- ================================================================
-- 7. 原始数据存储表 - 存储完整JSON数据备份
-- ================================================================
CREATE TABLE IF NOT EXISTS raw_data_backup (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    record_id BIGINT NOT NULL COMMENT '关联scrape_records主键',
    data_source VARCHAR(50) NOT NULL COMMENT '数据源标识',
    raw_json LONGTEXT COMMENT '原始JSON数据',
    data_size INT COMMENT '数据大小(bytes)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (record_id) REFERENCES scrape_records(id) ON DELETE CASCADE,
    INDEX idx_record_source (record_id, data_source)
) ENGINE=InnoDB COMMENT='原始数据备份';

-- ================================================================
-- 创建视图 - 便于数据查询和分析
-- ================================================================

-- 最新爬取记录视图
CREATE OR REPLACE VIEW v_latest_scrape_summary AS
SELECT 
    sr.id,
    sr.scrape_time,
    sr.total_data_sources,
    sr.successful_sources,
    sr.failed_sources,
    sr.processing_duration_ms,
    COUNT(DISTINCT gmi.indicator_code) as macro_indicators_count,
    COUNT(DISTINCT usg.stock_symbol) as us_gainers_count,
    COUNT(DISTINCT ass.metric_name) as a_stock_metrics_count,
    COUNT(DISTINCT mt.market_type) as market_turnover_count
FROM scrape_records sr
LEFT JOIN global_macro_indicators gmi ON sr.id = gmi.record_id AND gmi.is_error = FALSE
LEFT JOIN us_stock_gainers usg ON sr.id = usg.record_id AND usg.is_error = FALSE  
LEFT JOIN a_stock_statistics ass ON sr.id = ass.record_id AND ass.is_error = FALSE
LEFT JOIN market_turnover mt ON sr.id = mt.record_id AND mt.is_error = FALSE
WHERE sr.created_at >= DATE_SUB(NOW(), INTERVAL 1 DAY)
GROUP BY sr.id, sr.scrape_time, sr.total_data_sources, sr.successful_sources, sr.failed_sources, sr.processing_duration_ms
ORDER BY sr.scrape_time DESC;

-- ================================================================
-- 初始化配置数据
-- ================================================================

-- 插入数据源配置信息
INSERT IGNORE INTO raw_data_backup (record_id, data_source, raw_json, data_size) 
VALUES (0, 'config', '{"version": "1.0", "created_by": "financial_scraper", "description": "数据库初始化完成"}', 100);

-- ================================================================
-- 数据库权限设置建议 (请根据实际需求调整)
-- ================================================================

-- 创建应用专用用户 (可选)
-- CREATE USER 'scraper_app'@'localhost' IDENTIFIED BY 'your_secure_password';
-- GRANT SELECT, INSERT, UPDATE ON financial_scraper.* TO 'scraper_app'@'localhost';
-- FLUSH PRIVILEGES;

-- ================================================================
-- 索引优化建议
-- ================================================================

-- 如果数据量很大，可以考虑添加分区表
-- ALTER TABLE scrape_records 
-- PARTITION BY RANGE (TO_DAYS(scrape_time)) (
--     PARTITION p_2025_01 VALUES LESS THAN (TO_DAYS('2025-02-01')),
--     PARTITION p_2025_02 VALUES LESS THAN (TO_DAYS('2025-03-01')),
--     -- 继续添加分区...
-- );

-- ================================================================
-- 数据清理定时任务建议 (可选)
-- ================================================================

-- 清理30天前的数据 (根据需要调整保留时间)
-- CREATE EVENT IF NOT EXISTS cleanup_old_data
-- ON SCHEDULE EVERY 1 DAY
-- DO
--   DELETE FROM scrape_records WHERE created_at < DATE_SUB(NOW(), INTERVAL 30 DAY);