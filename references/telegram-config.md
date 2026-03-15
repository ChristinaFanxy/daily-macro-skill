# Telegram 推送配置

## Bot 信息
- **Bot Token**: `8268782703:AAFAZpL0NWQcN916QmvDzUonxPOqSKdSCss`
- **Chat ID**: `5118958859`
- **Bot Username**: @Christina_ocFinance_bot

## 推送设置
- **默认推送**: Brief 模式（适合手机阅读）
- **Full 模式**: 仅发送 TL;DR 摘要 + 关注清单，完整报告保存本地

## 使用方式

### 手动推送
运行 `/daily-macro` 后，报告会自动发送到 Telegram。

### API 调用
```bash
curl -s -X POST "https://api.telegram.org/bot8268782703:AAFAZpL0NWQcN916QmvDzUonxPOqSKdSCss/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{
    "chat_id": "5118958859",
    "text": "报告内容",
    "parse_mode": "Markdown"
  }'
```

## 注意事项
- Telegram 消息长度限制 4096 字符
- 超长内容需拆分发送
- 使用 Markdown 格式化（`*bold*`, `_italic_`, `` `code` ``）
