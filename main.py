"""
Centrální sběrný server pro průmyslová data (Industry 4.0)
FastAPI aplikace s HTMX frontendem.

Spuštění: uvicorn main:app --reload
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, SQLModel, create_engine, select

from backend.models import Device, DeviceCreate, Measurement, Tag, TagCreate
from backend.poller import init_poller

# ───────────────────────────────────────
# Konfigurace
# ───────────────────────────────────────
DATABASE_URL = "sqlite:///data.sqlite"
POLL_INTERVAL = 5.0  # sekund

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ───────────────────────────────────────
# Databáze
# ───────────────────────────────────────
engine = create_engine(DATABASE_URL, echo=False)


def create_db_and_tables():
    """Vytvoří databázi a tabulky, pokud neexistují."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Vrátí novou databázovou session."""
    return Session(engine)


# ───────────────────────────────────────
# Lifecycle
# ───────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Spuštění a ukončení aplikace."""
    # Startup
    create_db_and_tables()
    logger.info("Databáze inicializována")
    
    # Spuštění polleru
    poller = init_poller(engine, POLL_INTERVAL)
    poller.start()
    
    yield
    
    # Shutdown
    poller.stop()
    logger.info("Aplikace ukončena")


# ───────────────────────────────────────
# FastAPI aplikace
# ───────────────────────────────────────
app = FastAPI(
    title="Data Gateway - Industry 4.0",
    description="Centrální sběrný server pro průmyslová data",
    version="1.0.0",
    lifespan=lifespan
)

# Statické soubory a šablony
BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "frontend" / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "frontend" / "templates")


# ───────────────────────────────────────
# Pomocné funkce
# ───────────────────────────────────────
def get_last_measurement(session: Session, tag_id: int) -> Optional[Measurement]:
    """Získá poslední měření pro daný tag."""
    return session.exec(
        select(Measurement)
        .where(Measurement.tag_id == tag_id)
        .order_by(Measurement.timestamp.desc())
        .limit(1)
    ).first()


def get_device_last_values(session: Session, device: Device) -> dict:
    """Získá poslední hodnoty všech tagů zařízení."""
    values = {}
    last_update = None
    
    for tag in device.tags:
        measurement = get_last_measurement(session, tag.id)
        if measurement:
            values[tag.name] = {
                "value": measurement.value,
                "quality": measurement.quality,
                "timestamp": measurement.timestamp,
                "data_type": tag.data_type
            }
            if last_update is None or measurement.timestamp > last_update:
                last_update = measurement.timestamp
    
    return {"values": values, "last_update": last_update}


# ───────────────────────────────────────
# ROUTY - Dashboard
# ───────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Hlavní dashboard se seznamem zařízení a jejich hodnotami."""
    with get_session() as session:
        devices = session.exec(select(Device)).all()
        
        # Připravíme data pro každé zařízení
        devices_data = []
        all_tags = set()
        
        for device in devices:
            device_info = get_device_last_values(session, device)
            devices_data.append({
                "device": device,
                "values": device_info["values"],
                "last_update": device_info["last_update"]
            })
            all_tags.update(device_info["values"].keys())
        
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "devices_data": devices_data,
                "all_tags": sorted(all_tags)
            }
        )


@app.get("/dashboard-content", response_class=HTMLResponse)
async def dashboard_content(request: Request):
    """HTMX: Aktualizace obsahu dashboardu."""
    with get_session() as session:
        devices = session.exec(select(Device)).all()
        
        devices_data = []
        all_tags = set()
        
        for device in devices:
            device_info = get_device_last_values(session, device)
            devices_data.append({
                "device": device,
                "values": device_info["values"],
                "last_update": device_info["last_update"]
            })
            all_tags.update(device_info["values"].keys())
        
        return templates.TemplateResponse(
            "partials/dashboard_table.html",
            {
                "request": request,
                "devices_data": devices_data,
                "all_tags": sorted(all_tags)
            }
        )


# ───────────────────────────────────────
# ROUTY - Device CRUD
# ───────────────────────────────────────
@app.get("/device/new", response_class=HTMLResponse)
async def device_form_new(request: Request):
    """Formulář pro vytvoření nového zařízení."""
    return templates.TemplateResponse(
        "device_form.html",
        {"request": request, "device": None, "tags": []}
    )


@app.get("/device/{device_id}", response_class=HTMLResponse)
async def device_detail(request: Request, device_id: int):
    """Detail zařízení s historií měření."""
    with get_session() as session:
        device = session.get(Device, device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Zařízení nenalezeno")
        
        # Získání posledních 100 měření pro každý tag
        measurements_data = []
        for tag in device.tags:
            tag_measurements = session.exec(
                select(Measurement)
                .where(Measurement.tag_id == tag.id)
                .order_by(Measurement.timestamp.desc())
                .limit(100)
            ).all()
            measurements_data.append({
                "tag": tag,
                "measurements": tag_measurements
            })
        
        return templates.TemplateResponse(
            "device_detail.html",
            {
                "request": request,
                "device": device,
                "measurements_data": measurements_data
            }
        )


@app.get("/device/{device_id}/edit", response_class=HTMLResponse)
async def device_form_edit(request: Request, device_id: int):
    """Formulář pro editaci zařízení."""
    with get_session() as session:
        device = session.get(Device, device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Zařízení nenalezeno")
        
        return templates.TemplateResponse(
            "device_form.html",
            {"request": request, "device": device, "tags": device.tags}
        )


@app.post("/device/save", response_class=HTMLResponse)
async def device_save(
    request: Request,
    device_id: Optional[int] = Form(None),
    name: str = Form(...),
    protocol: str = Form(...),
    host: str = Form("127.0.0.1"),
    port: int = Form(...),
    endpoint_url: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    enabled: str = Form("false")
):
    """Uložení zařízení (vytvoření nebo aktualizace)."""
    # Konverze enabled z řetězce na boolean
    is_enabled = enabled.lower() == "true"
    
    with get_session() as session:
        if device_id:
            # Aktualizace existujícího
            device = session.get(Device, device_id)
            if not device:
                raise HTTPException(status_code=404, detail="Zařízení nenalezeno")
            
            device.name = name
            device.protocol = protocol
            device.host = host
            device.port = port
            device.endpoint_url = endpoint_url
            device.description = description
            device.enabled = is_enabled
        else:
            # Vytvoření nového
            device = Device(
                name=name,
                protocol=protocol,
                host=host,
                port=port,
                endpoint_url=endpoint_url,
                description=description,
                enabled=is_enabled
            )
            session.add(device)
        
        session.commit()
        session.refresh(device)
        
        logger.info(f"Zařízení uloženo: {device.name} (ID: {device.id})")
    
    return RedirectResponse(url=f"/device/{device.id}", status_code=303)


@app.post("/device/{device_id}/delete")
async def device_delete(device_id: int):
    """Smazání zařízení."""
    with get_session() as session:
        device = session.get(Device, device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Zařízení nenalezeno")
        
        session.delete(device)
        session.commit()
        
        logger.info(f"Zařízení smazáno: ID {device_id}")
    
    return RedirectResponse(url="/", status_code=303)


@app.post("/device/{device_id}/toggle")
async def device_toggle(device_id: int):
    """Přepnutí enabled/disabled stavu zařízení."""
    with get_session() as session:
        device = session.get(Device, device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Zařízení nenalezeno")
        
        device.enabled = not device.enabled
        session.commit()
        
        logger.info(f"Zařízení {device.name}: enabled={device.enabled}")
    
    return RedirectResponse(url="/", status_code=303)


# ───────────────────────────────────────
# ROUTY - Tag CRUD
# ───────────────────────────────────────
@app.post("/device/{device_id}/tag/add", response_class=HTMLResponse)
async def tag_add(
    request: Request,
    device_id: int,
    tag_name: str = Form(...),
    tag_address: str = Form(...),
    tag_data_type: str = Form("float"),
    tag_description: Optional[str] = Form(None)
):
    """Přidání nového tagu k zařízení."""
    with get_session() as session:
        device = session.get(Device, device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Zařízení nenalezeno")
        
        tag = Tag(
            name=tag_name,
            address=tag_address,
            data_type=tag_data_type,
            description=tag_description,
            device_id=device_id,
            enabled=True
        )
        session.add(tag)
        session.commit()
        
        logger.info(f"Tag přidán: {tag.name} -> {device.name}")
    
    return RedirectResponse(url=f"/device/{device_id}/edit", status_code=303)


@app.post("/tag/{tag_id}/delete")
async def tag_delete(tag_id: int):
    """Smazání tagu."""
    with get_session() as session:
        tag = session.get(Tag, tag_id)
        if not tag:
            raise HTTPException(status_code=404, detail="Tag nenalezen")
        
        device_id = tag.device_id
        session.delete(tag)
        session.commit()
        
        logger.info(f"Tag smazán: ID {tag_id}")
    
    return RedirectResponse(url=f"/device/{device_id}/edit", status_code=303)


@app.post("/tag/{tag_id}/toggle")
async def tag_toggle(tag_id: int):
    """Přepnutí enabled/disabled stavu tagu."""
    with get_session() as session:
        tag = session.get(Tag, tag_id)
        if not tag:
            raise HTTPException(status_code=404, detail="Tag nenalezen")
        
        tag.enabled = not tag.enabled
        device_id = tag.device_id
        session.commit()
        
        logger.info(f"Tag {tag.name}: enabled={tag.enabled}")
    
    return RedirectResponse(url=f"/device/{device_id}/edit", status_code=303)


# ───────────────────────────────────────
# ROUTY - Manuální čtení
# ───────────────────────────────────────
@app.post("/device/{device_id}/poll", response_class=HTMLResponse)
async def device_poll_manual(request: Request, device_id: int):
    """Manuální spuštění čtení dat ze zařízení."""
    from backend.poller import get_poller
    
    poller = get_poller()
    if not poller:
        raise HTTPException(status_code=500, detail="Poller není inicializován")
    
    results = await poller.poll_device_once(device_id)
    
    return templates.TemplateResponse(
        "partials/poll_result.html",
        {"request": request, "results": results, "device_id": device_id}
    )


# ───────────────────────────────────────
# API endpointy (JSON)
# ───────────────────────────────────────
@app.get("/api/devices")
async def api_devices():
    """API: Seznam všech zařízení."""
    with get_session() as session:
        devices = session.exec(select(Device)).all()
        return [
            {
                "id": d.id,
                "name": d.name,
                "protocol": d.protocol,
                "host": d.host,
                "port": d.port,
                "enabled": d.enabled
            }
            for d in devices
        ]


@app.get("/api/device/{device_id}/measurements")
async def api_device_measurements(device_id: int, limit: int = 100):
    """API: Měření pro dané zařízení."""
    with get_session() as session:
        device = session.get(Device, device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Zařízení nenalezeno")
        
        results = {}
        for tag in device.tags:
            measurements = session.exec(
                select(Measurement)
                .where(Measurement.tag_id == tag.id)
                .order_by(Measurement.timestamp.desc())
                .limit(limit)
            ).all()
            
            results[tag.name] = [
                {
                    "value": m.value,
                    "timestamp": m.timestamp.isoformat(),
                    "quality": m.quality
                }
                for m in measurements
            ]
        
        return results


# ───────────────────────────────────────
# Spuštění
# ───────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
