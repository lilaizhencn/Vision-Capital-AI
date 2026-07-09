# RAG Flow

1. 用户把 BP、财报、合同、尽调报告等资料上传到项目。
2. 后端把原始文件保存到 Cloudflare R2；若未配置 R2，则回退到本地存储。
3. Celery worker 读取文件并按类型调用对应解析器。
4. 解析后的长文本会按 `chunk_size` 和 `chunk_overlap` 切成多个 chunk。
5. 如果配置了 `LLM_API_KEY`，系统会调用 OpenAI-compatible Embedding API 为 chunk 生成向量。
6. chunk 与向量共同写入 PostgreSQL `document_chunks` 表。
7. 用户提问时，系统先为问题生成向量，再做相似度检索。
8. 检索结果会进入 Prompt，最后由 LLM 生成回答与引用片段。

