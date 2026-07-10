# Vision Capital AI Architecture

## 总体系统架构图

```mermaid
flowchart TD
    User["用户浏览器"] --> Web["React Web"]
    Web --> API["FastAPI Backend + WebSocket"]
    API --> DB["PostgreSQL + pgvector"]
    API --> Redis["Redis"]
    Web -. "Presigned PUT / Multipart" .-> R2["Cloudflare R2 / Local Storage Fallback"]
    Redis --> Worker["Celery Worker"]
    Worker --> R2
    Worker --> DB
    Worker --> Parser["Document Parser + Vision OCR"]
    Worker --> Embedding["OpenAI Compatible Embedding API"]
    API --> LLM["OpenAI / DeepSeek Compatible LLM"]
    API --> RAG["RAG Pipeline"]
    RAG --> DB
```

## 文件上传与解析流程图

```mermaid
flowchart LR
    U["用户上传文件"] --> A["FastAPI Upload API"]
    A --> B["Cloudflare R2 / Local Storage"]
    A --> C["PostgreSQL 保存文件元数据"]
    C --> D["Celery 解析任务"]
    D --> E["Worker 下载文件"]
    E --> F["Document Parser"]
    F --> G["文本切片"]
    G --> H["Embedding"]
    H --> I["pgvector / document_chunks"]
    I --> J["解析完成并更新状态"]
```

## RAG 问答流程图

```mermaid
flowchart LR
    U["用户提问"] --> A["FastAPI Chat API"]
    A --> B["Question Embedding"]
    B --> C["pgvector 相似度检索"]
    C --> D["召回上下文片段"]
    D --> E["Prompt 组装"]
    E --> F["OpenAI Compatible LLM"]
    F --> G["返回答案与引用"]
```

## 模块说明

- `backend/app/api`: REST API 路由层。
- `backend/app/services`: 业务服务层，聚合认证、项目、文件、聊天、报告等核心流程。
- `backend/app/repositories`: 数据访问层。
- `backend/app/storage`: R2 与本地回退存储封装。
- `backend/app/workers`: Celery 任务与 worker 入口。
- `backend/app/rag` 与 `backend/app/ai`: 文本切片、Embedding、LLM 与检索增强问答能力。
## Parsing worker stages

```mermaid
flowchart LR
    Validate[Validate size hash signature] --> Scan[ClamAV scan]
    Scan --> OCR[OCR and text extraction]
    OCR --> Tables[Table extraction]
    Tables --> LLM[Structured LLM extraction]
    LLM --> Persist[Chunk embedding and persistence]
```

Each stage is a separate Celery task. The `parse_stage_runs` table stores a durable idempotency key for `batch + file + stage`, so retries do not duplicate completed work.
