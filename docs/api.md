# API 概览

## Auth

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`

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
