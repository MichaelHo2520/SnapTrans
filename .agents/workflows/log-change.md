---
description: 記錄自上次 commit 以來的修改內容到 DEVELOPMENT_LOG.md
---

// turbo-all

1. 將目前的修改摘要寫入記錄檔 (附加模式)
2. run_command: powershell -Command "echo '---' >> DEVELOPMENT_LOG.md; echo '記錄時間: $(Get-Date)' >> DEVELOPMENT_LOG.md; echo '修改摘要:' >> DEVELOPMENT_LOG.md; git diff --stat >> DEVELOPMENT_LOG.md"

3. 提示使用者修改已記錄
4. echo "修改內容已成功記錄到 DEVELOPMENT_LOG.md，您可以隨時查看該檔案。"
