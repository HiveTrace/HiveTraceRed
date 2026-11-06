# app.py
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session
import uuid
import yaml
from database import SessionLocal, Run, get_db
from tasks import schedule_run

app = FastAPI(title="HiveTrace Red Lite", description="Упрощённый enterprise-слой вокруг HiveTrace Red")
templates = Jinja2Templates(directory="templates")

class RunRequest(BaseModel):
    config_yaml: str  # YAML-конфиг HiveTrace Red в виде строки

@app.post("/api/runs", status_code=202)
async def create_run(payload: RunRequest, db: Session = Depends(get_db)):
    """Создаёт новый запуск и ставит его в очередь на выполнение."""
    try:
        config_dict = yaml.safe_load(payload.config_yaml)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Некорректный YAML: {e}")

    run_uuid = str(uuid.uuid4())
    run = Run(uuid=run_uuid, status="pending", config_yaml=payload.config_yaml)
    db.add(run)
    db.commit()
    db.refresh(run)

    # Запускаем фоновую задачу
    schedule_run(run_uuid, config_dict)

    return {"uuid": run_uuid, "status": "pending"}

@app.get("/api/runs")
async def list_runs(db: Session = Depends(get_db)):
    """Список всех запусков (краткая информация)."""
    runs = db.query(Run).order_by(Run.created_at.desc()).all()
    return [
        {
            "uuid": r.uuid,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        }
        for r in runs
    ]

@app.get("/api/runs/{run_uuid}")
async def get_run(run_uuid: str, db: Session = Depends(get_db)):
    """Детали конкретного запуска, включая результаты (если готово)."""
    run = db.query(Run).filter(Run.uuid == run_uuid).first()
    if not run:
        raise HTTPException(status_code=404, detail="Запуск не найден")
    return {
        "uuid": run.uuid,
        "status": run.status,
        "created_at": run.created_at,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "results": run.results_json,
        "report_available": bool(run.report_path),
        "error": run.error_message,
    }

@app.get("/api/runs/{run_uuid}/report")
async def download_report(run_uuid: str, db: Session = Depends(get_db)):
    """Скачать HTML-отчёт (если сгенерирован)."""
    run = db.query(Run).filter(Run.uuid == run_uuid).first()
    if not run or not run.report_path:
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    return FileResponse(run.report_path, media_type="text/html", filename=f"report_{run_uuid}.html")

# --- Простой веб-интерфейс ---
@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    runs = db.query(Run).order_by(Run.created_at.desc()).all()
    return templates.TemplateResponse("index.html", {"request": request, "runs": runs})

@app.get("/ui/runs/{run_uuid}", response_class=HTMLResponse)
async def run_detail(request: Request, run_uuid: str, db: Session = Depends(get_db)):
    run = db.query(Run).filter(Run.uuid == run_uuid).first()
    if not run:
        raise HTTPException(status_code=404, detail="Запуск не найден")
    return templates.TemplateResponse("run_detail.html", {"request": request, "run": run})