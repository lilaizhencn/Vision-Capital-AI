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

## Chat

- `POST /api/projects/{project_id}/chat`

## Reports

- `POST /api/projects/{project_id}/reports/generate`
- `GET /api/projects/{project_id}/reports`

## Dashboard

- `GET /api/dashboard/summary`

