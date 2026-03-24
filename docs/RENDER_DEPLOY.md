# Render Deployment

This project can be deployed to Render as a public FastAPI web service.

## Files already prepared

- `render.yaml`
- `.python-version`
- `main.py` with `/healthz`
- `app/config.py` with writable paths configurable through environment variables

## Recommended deployment steps

1. Push this project to a GitHub repository.
2. In Render, choose `New +` -> `Blueprint`.
3. Connect your GitHub repository.
4. Render will detect `render.yaml` and create the web service automatically.
5. After the first deploy finishes, open the generated public URL.

## Important notes

- For the free Render plan, persistent disks are not available.
- The app now stores writable runtime data under:
  - `VIDEOTUTOR_APPDATA_PATH=/tmp/AppData`
  - `VIDEOTUTOR_WORK_PATH=/tmp/work-dir`
- These paths are ephemeral and will be reset when the instance restarts or redeploys.
- The health check endpoint is `GET /healthz`.

## Optional environment variables

Set these in Render if you want LLM responses instead of retrieval-only answers:

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `VIDEOTUTOR_LLM_API_KEY`
- `VIDEOTUTOR_LLM_BASE_URL`
- `VIDEOTUTOR_LLM_MODEL`
- `VIDEOTUTOR_TOP_K`

## Start command

Render runs the service with:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

## Public URLs after deployment

- Home page: `https://<your-service>.onrender.com/`
- API docs: `https://<your-service>.onrender.com/docs`
