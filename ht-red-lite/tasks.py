# tasks.py
import asyncio
import uuid
import yaml
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from database import SessionLocal, Run

RUNS_DIR = Path("runs")
RUNS_DIR.mkdir(exist_ok=True)

async def run_hivetrace(run_uuid: str, config_dict: dict):
    """Фоновая задача: запускает hivetracered и обновляет статус в БД."""
    db = SessionLocal()
    run = db.query(Run).filter(Run.uuid == run_uuid).first()
    if not run:
        db.close()
        return

    run.status = "running"
    run.started_at = datetime.utcnow()
    db.commit()

    run_dir = RUNS_DIR / run_uuid
    run_dir.mkdir(exist_ok=True)
    config_path = run_dir / "config.yaml"

    # Сохраняем конфиг на диск
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config_dict, f, allow_unicode=True)

    try:
        # Запускаем CLI HiveTrace Red
        process = await asyncio.create_subprocess_exec(
            "hivetracered", "--config", str(config_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(run_dir)
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(f"hivetracered завершился с кодом {process.returncode}:\n{stderr.decode()}")

        # Ищем сгенерированный HTML-отчёт (hivetracered создаёт его в output_dir)
        html_files = list(run_dir.rglob("*.html"))
        report_path = str(html_files[0]) if html_files else None

        # Пытаемся прочитать агрегированные результаты (если есть results.json)
        results_json = None
        json_files = list(run_dir.rglob("results.json"))
        if json_files:
            import json
            with open(json_files[0], "r", encoding="utf-8") as jf:
                results_json = json.load(jf)

        run.status = "completed"
        run.report_path = report_path
        run.results_json = results_json
        run.finished_at = datetime.utcnow()
        db.commit()

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        run.finished_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()

def schedule_run(run_uuid: str, config_dict: dict):
    """Запускает фоновую задачу (в текущем event loop)."""
    asyncio.create_task(run_hivetrace(run_uuid, config_dict))