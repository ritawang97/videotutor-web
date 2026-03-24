"""
VideoTutor (VideoCaptioner) entrypoint

- Desktop mode: `python main.py` (launches existing PyQt GUI)
- Web mode (Render-ready): `uvicorn main:app --host 0.0.0.0 --port 10000`

Important:
This file is intentionally written so that importing it (e.g. by uvicorn)
does NOT import/initialize PyQt. Desktop-only imports live inside `run_desktop()`.
"""

from __future__ import annotations

import os
import sys
import traceback
from typing import Any, Dict, Optional

from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.config import APPDATA_PATH
from app.core.pdf_vector_db import PDFVectorStore
from app.core.rag.embedding import EmbeddingGenerator
from app.core.rag.rag_engine import RAGEngine
from app.core.utils.logger import setup_logger

logger = setup_logger("WebApp")


# ----------------------------
# Web (FastAPI)
# ----------------------------

app = FastAPI(title="VideoTutor Web", version="1.0.0")
templates = Jinja2Templates(directory="templates")


class ChatRequest(BaseModel):
    query: str


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


_pipeline: Optional[Dict[str, Any]] = None


def _get_pipeline() -> Dict[str, Any]:
    """
    Lazy-init the existing core pipeline pieces.

    We avoid touching any desktop-only modules here.
    """
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    vector_store_path = str(APPDATA_PATH / "pdf_vector_db")

    # Embedding: default to local sentence-transformers (no external API required)
    embedding_type = os.getenv("VIDEOTUTOR_EMBEDDING_TYPE", "local").strip().lower()
    embedding_model = os.getenv(
        "VIDEOTUTOR_EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"
    ).strip()

    vector_store = PDFVectorStore(vector_store_path)
    embedding_generator = EmbeddingGenerator(
        model_type=embedding_type,
        model_name=embedding_model,
        api_key=os.getenv("OPENAI_API_KEY") or None,
        api_base=os.getenv("OPENAI_BASE_URL") or None,
    )

    # LLM: keep existing behavior — if you configure an OpenAI-compatible local endpoint
    # (e.g. Ollama / LM Studio), it will work without changing algorithm logic.
    llm_client = None
    try:
        from openai import OpenAI  # local import to keep startup light

        llm_base = os.getenv("VIDEOTUTOR_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")
        llm_key = os.getenv("VIDEOTUTOR_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        llm_model = os.getenv("VIDEOTUTOR_LLM_MODEL", "gpt-4o-mini")

        if llm_base and llm_key:
            _client = OpenAI(api_key=llm_key, base_url=llm_base)

            class _OpenAICompatLLM:
                def generate(self, prompt: str, temperature: float = 0.7) -> str:
                    resp = _client.chat.completions.create(
                        model=llm_model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=temperature,
                        timeout=60,
                    )
                    return resp.choices[0].message.content or ""

            llm_client = _OpenAICompatLLM()
            logger.info(f"LLM configured (OpenAI-compatible): base={llm_base}, model={llm_model}")
        else:
            logger.info("LLM not configured; will fall back to retrieval-only answer.")
    except Exception as e:
        logger.warning(f"LLM init skipped/failed, using retrieval-only mode. Error: {e}")

    rag_engine = RAGEngine(
        vector_store=vector_store,
        embedding_generator=embedding_generator,
        llm_client=llm_client,
        top_k=int(os.getenv("VIDEOTUTOR_TOP_K", "5")),
    )

    _pipeline = {
        "rag_engine": rag_engine,
    }
    return _pipeline


@app.post("/chat")
async def chat(body: ChatRequest):
    query = (body.query or "").strip()
    if not query:
        return JSONResponse(status_code=400, content={"detail": "query is required"})

    try:
        pipeline = _get_pipeline()
        rag_engine: RAGEngine = pipeline["rag_engine"]

        result = rag_engine.query(question=query, use_llm=True)
        answer = result.get("answer") or ""
        return {"response": answer}
    except Exception as e:
        logger.error(f"/chat failed: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"detail": str(e)})


# ----------------------------
# Desktop (PyQt) — unchanged logic, only moved behind a function
# ----------------------------

def run_desktop():
    """
    Launch the existing PyQt desktop app.
    Kept functionally identical to the previous top-level script.
    """
    import platform

    # Add project root directory to Python path
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.append(project_root)

    # Use appropriate library folder name based on OS
    lib_folder = "Lib" if platform.system() == "Windows" else "lib"
    plugin_path = os.path.join(
        sys.prefix, lib_folder, "site-packages", "PyQt5", "Qt5", "plugins"
    )
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = plugin_path

    # Delete pyd files app*.pyd
    for file in os.listdir():
        if file.startswith("app") and file.endswith(".pyd"):
            os.remove(file)

    # Desktop-only imports
    from PyQt5.QtCore import Qt, QTranslator
    from PyQt5.QtWidgets import QApplication
    from qfluentwidgets import FluentTranslator

    from app.common.config import cfg
    from app.config import RESOURCE_PATH
    from app.view.main_window import MainWindow

    desktop_logger = setup_logger("VideoCaptioner")

    def exception_hook(exctype, value, tb):
        desktop_logger.error("".join(traceback.format_exception(exctype, value, tb)))
        sys.__excepthook__(exctype, value, tb)  # 调用默认的异常处理

    sys.excepthook = exception_hook

    # Enable DPI Scale
    if cfg.get(cfg.dpiScale) == "Auto":
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough  # type: ignore
        )
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)  # type: ignore
    else:
        os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
        os.environ["QT_SCALE_FACTOR"] = str(cfg.get(cfg.dpiScale))
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)  # type: ignore

    qt_app = QApplication(sys.argv)
    qt_app.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings, True)  # type: ignore

    # Internationalization (Multi-language)
    locale = cfg.get(cfg.language).value
    translator = FluentTranslator(locale)
    myTranslator = QTranslator()
    translations_path = RESOURCE_PATH / "translations" / f"VideoCaptioner_{locale.name()}.qm"
    myTranslator.load(str(translations_path))
    qt_app.installTranslator(translator)
    qt_app.installTranslator(myTranslator)

    w = MainWindow()
    w.show()
    sys.exit(qt_app.exec_())


if __name__ == "__main__":
    run_desktop()
