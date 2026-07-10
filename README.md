# Vision Capital AI

Vision Capital AI 是一个企业级 AI 投资研究平台，围绕投前分析、投中跟踪、投后管理构建项目知识库、智能问答与研究报告能力。

## 功能列表

- 用户注册、登录、JWT 鉴权
- 投资项目管理
- 多类型文档上传与解析
- Cloudflare R2 存储，未配置时本地回退
- Celery + Redis 异步文档解析
- PostgreSQL + pgvector 文档切片与向量检索
- 项目级 AI 问答
- AI 投资研究报告生成
- Dashboard 统计面板

## 技术栈

- Backend: Python, FastAPI, Pydantic, SQLAlchemy, PostgreSQL, pgvector, Alembic, Redis, Celery, boto3, OpenAI SDK
- Frontend: React, TypeScript, Vite, Ant Design, React Router, Axios, CSS
- Deployment: Docker, Docker Compose

## 项目结构

```text
vision-capital-ai/
├── backend/
├── frontend/
├── docs/
├── docker-compose.yml
└── README.md
```

## 架构图入口

- [docs/architecture.md](./docs/architecture.md)
- [docs/rag-flow.md](./docs/rag-flow.md)
- [docs/api.md](./docs/api.md)

## 本地启动步骤

1. 复制环境变量示例：
   - `backend/.env.example` 另存为 `backend/.env`
   - `frontend/.env.example` 另存为 `frontend/.env`
2. 启动 PostgreSQL 与 Redis。
3. 安装后端依赖并执行迁移：
   - `cd backend`
   - `pip install -r requirements.txt`
   - `alembic upgrade head`
4. 启动后端：
   - `uvicorn app.main:app --reload`
5. 启动 Celery Worker：
   - `celery -A app.workers.celery_app.celery_app worker --loglevel=info`
6. 安装前端依赖并启动前端：
   - `cd frontend`
   - `npm install`
   - `npm run dev`

## Docker Compose 启动方式

在仓库根目录运行：

```bash
docker compose up --build
```

启动后访问：

- FastAPI Swagger: [http://localhost:8000/docs](http://localhost:8000/docs)
- React Web: [http://localhost:5173](http://localhost:5173)

## 环境变量说明

### backend/.env.example

- `APP_NAME`: 应用名称
- `APP_ENV`: 运行环境
- `APP_SECRET_KEY`: 应用级密钥
- `DATABASE_URL`: PostgreSQL 连接串
- `REDIS_URL`: Redis 连接串
- `JWT_SECRET_KEY`: JWT 签名密钥
- `JWT_ALGORITHM`: JWT 算法
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`: Token 有效期
- `R2_ENDPOINT_URL`: R2 Endpoint
- `R2_ACCESS_KEY_ID`: R2 Access Key
- `R2_SECRET_ACCESS_KEY`: R2 Secret Key
- `R2_BUCKET_NAME`: R2 Bucket
- `R2_PUBLIC_BASE_URL`: R2 公网访问前缀
- `LLM_BASE_URL`: OpenAI-compatible API 地址
- `LLM_API_KEY`: 模型 API Key
- `LLM_MODEL`: 对话模型
- `EMBEDDING_MODEL`: 向量模型
- `LOCAL_STORAGE_PATH`: 本地回退存储目录
- `CHUNK_SIZE`: 文本切片大小
- `CHUNK_OVERLAP`: 文本切片重叠长度
- `EMBEDDING_DIMENSION`: 向量维度

### frontend/.env.example

- `VITE_API_BASE_URL`: 前端访问的后端 API 根地址

## 数据库迁移命令

```bash
cd backend
alembic upgrade head
```

## Celery Worker 启动方式

```bash
cd backend
celery -A app.workers.celery_app.celery_app worker --loglevel=info
```

## R2 配置说明

系统默认优先使用 Cloudflare R2。如果 `R2_*` 环境变量没有配置，后端会自动回退到 `LOCAL_STORAGE_PATH` 本地目录，方便本地学习与开发。

浏览器直传使用 R2 presigned PUT / multipart URL。R2 bucket 需要允许实际前端来源的 `PUT`、`POST`、`GET`、`HEAD`、`DELETE`，并在 CORS `ExposeHeaders` 中暴露 `ETag`。如果 bucket 权限暂时不能配置 CORS，前端会在直传失败时自动切换到受 JWT 保护的后端分片兜底路径，文件仍然写入 R2。

## OpenAI / DeepSeek 配置说明

- `LLM_BASE_URL` 可指向 OpenAI 官方地址，也可指向 DeepSeek 或其他 OpenAI-compatible 服务。
- 如果 `LLM_API_KEY` 未配置，Embedding 与报告 / 问答生成会返回清晰错误，不会直接让服务崩溃。

## 常见问题

### 1. 为什么上传成功但解析失败？

常见原因是文件格式不受支持、数据库未启动、Worker 未启动，或本地未配置模型 API Key。

### 2. 为什么没有生成向量？

如果 `LLM_API_KEY` 未配置，系统仍会解析文本并入库，但不会生成 embedding 向量，检索会回退到最近文本片段。

### 3. 为什么没有使用 R2？

因为当前环境缺少 `R2_ENDPOINT_URL`、`R2_ACCESS_KEY_ID`、`R2_SECRET_ACCESS_KEY` 或 `R2_BUCKET_NAME` 中的一个或多个。

## 后续规划

- 增加 OCR 结果校对与人工审核流程
- 增加系统级报告中心与全文检索
- 增加投后提醒、舆情追踪、自动尽调 Agent
- 增加权限分级、组织空间、多用户协作

## Production parsing pipeline

The upload pipeline is split into independent Celery stages: validation and checksum, ClamAV scan, OCR/text extraction, table extraction, structured LLM extraction, and persistence. Each file/stage has a durable idempotency record, retry/backoff behavior, and a dead-letter record after the configured retry limit.

Production Compose starts ClamAV and sets `VIRUS_SCAN_ENABLED=true`. The backend rejects production startup when virus scanning is disabled. Legacy `.doc` files use `antiword`; legacy `.xls` files use `xlrd`.
