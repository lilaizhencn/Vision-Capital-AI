# API 概览

## Auth

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/auth/ai-usage`：返回当前用户按新加坡自然日统计的 AI 限额、已用次数、剩余次数和重置时间。

预览环境中，聊天问答、报告生成和每个文件的 AI 解析共享每日 10 次额度。同一文件的后台重试不重复计数；
第 11 次同步调用返回 `429 Too Many Requests`，并携带 `Retry-After`、`X-AI-Limit`、
`X-AI-Remaining` 和 `X-AI-Reset` 响应头。

## Projects

- `POST /api/projects`
- `GET /api/projects`
- `GET /api/projects/{project_id}`
- `PUT /api/projects/{project_id}`
- `DELETE /api/projects/{project_id}`

## Files

- `POST /api/projects/{project_id}/files/upload`
- `GET /api/projects/{project_id}/files`
- `GET /api/files/{file_id}`
- `DELETE /api/files/{file_id}`
- `POST /api/files/{file_id}/retry`
- `POST /api/projects/{project_id}/file-batches`
- `POST /api/file-batches/{batch_id}/files/{file_id}/content`
- `GET /api/file-batches/{batch_id}/files/{file_id}/parts/{part_number}/url`
- `GET /api/file-batches/{batch_id}/files/{file_id}/parts`
- `POST /api/file-batches/{batch_id}/files/{file_id}/complete-multipart`
- `POST /api/file-batches/{batch_id}/complete`
- `WS /api/ws/batches/{batch_id}?token=<JWT>`

`FileRead.extracted_data` contains optional structured investment fields produced by the LLM stage. If no LLM key is configured, the field is `null` while deterministic parsing and chunking still complete.

## Chat

- `POST /api/projects/{project_id}/chat`

## Reports

- `GET /api/reports` lists the current user's most recent reports for the report center.
- `POST /api/projects/{project_id}/reports/generate`
- `GET /api/projects/{project_id}/reports`

## Dashboard

- `GET /api/dashboard/summary`

## Investment lifecycle

- `GET /api/projects/{project_id}/lifecycle`
- `PUT /api/projects/{project_id}/lifecycle/transaction`
- `POST /api/projects/{project_id}/lifecycle/metrics`
- `POST /api/projects/{project_id}/lifecycle/metrics/{metric_id}/observations`
- `POST /api/projects/{project_id}/lifecycle/risks`
- `PATCH /api/projects/{project_id}/lifecycle/risks/{risk_id}`
- `GET /api/projects/{project_id}/lifecycle/opinions`
- `POST /api/projects/{project_id}/lifecycle/opinions/refresh`
- `POST /api/projects/{project_id}/lifecycle/data-sources`
- `PATCH /api/projects/{project_id}/lifecycle/data-sources/{source_id}`
- `POST /api/projects/{project_id}/lifecycle/data-sources/{source_id}/run`

Closing a transaction requires an approved IC decision, every closing condition in `satisfied` or `waived` state,
and at least one project-owned evidence file. KPI observations are unique per metric and period. Threshold breaches
create risk events and append a new investment-opinion version when the evidence hash changes.
