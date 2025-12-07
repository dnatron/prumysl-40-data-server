"""
Asynchronní poller pro pravidelné dotazování všech aktivních zařízení.
Každých N sekund prochází aktivní Device a jejich Tag, čte hodnoty
a ukládá je jako Measurement.
"""

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Session, select

from .modbus_client import read_modbus_value
from .opc_client import read_opcua_value

if TYPE_CHECKING:
    from sqlalchemy import Engine

logger = logging.getLogger(__name__)


class DataPoller:
    """
    Třída pro pravidelný sběr dat ze všech aktivních zařízení.
    """
    
    def __init__(self, engine: "Engine", interval: float = 5.0):
        """
        Args:
            engine: SQLAlchemy engine pro přístup k databázi
            interval: Interval mezi sběry dat v sekundách (default: 5)
        """
        self.engine = engine
        self.interval = interval
        self._running = False
        self._task: asyncio.Task | None = None
    
    def start(self):
        """Spustí polling jako background task."""
        if self._running:
            logger.warning("Poller již běží")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(f"Poller spuštěn s intervalem {self.interval}s")
    
    def stop(self):
        """Zastaví polling."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Poller zastaven")
    
    async def _poll_loop(self):
        """Hlavní polling smyčka."""
        # Import zde kvůli circular imports
        from .models import Device, Measurement, Tag
        
        while self._running:
            try:
                await self._poll_all_devices()
            except Exception as e:
                logger.error(f"Chyba v polling smyčce: {e}")
            
            await asyncio.sleep(self.interval)
    
    async def _poll_all_devices(self):
        """Projde všechna aktivní zařízení a přečte jejich tagy."""
        from .models import Device, Measurement, Tag
        
        with Session(self.engine) as session:
            # Načtení všech aktivních zařízení
            devices = session.exec(
                select(Device).where(Device.enabled == True)
            ).all()
            
            for device in devices:
                await self._poll_device(session, device)
            
            session.commit()
    
    async def _poll_device(self, session: Session, device: "Device"):
        """
        Přečte všechny aktivní tagy daného zařízení.
        """
        from .models import Measurement, Tag
        
        # Načtení aktivních tagů zařízení
        tags = session.exec(
            select(Tag).where(Tag.device_id == device.id, Tag.enabled == True)
        ).all()
        
        if not tags:
            return
        
        logger.debug(f"Polling zařízení {device.name} ({device.protocol}), {len(tags)} tagů")
        
        for tag in tags:
            try:
                value, quality = await self._read_tag_value(device, tag)
                
                # Uložení měření
                measurement = Measurement(
                    tag_id=tag.id,
                    value=value if value is not None else 0.0,
                    timestamp=datetime.utcnow(),
                    quality=quality
                )
                session.add(measurement)
                
                logger.debug(f"  Tag {tag.name}: {value} ({quality})")
                
            except Exception as e:
                logger.error(f"Chyba při čtení tagu {tag.name}: {e}")
    
    async def _read_tag_value(
        self, 
        device: "Device", 
        tag: "Tag"
    ) -> tuple[float | None, str]:
        """
        Přečte hodnotu tagu podle protokolu zařízení.
        """
        if device.protocol.lower() == "opcua":
            # OPC UA
            endpoint = device.endpoint_url or f"opc.tcp://{device.host}:{device.port}"
            return await read_opcua_value(endpoint, tag.address)
        
        elif device.protocol.lower() == "modbus":
            # Modbus TCP
            return await read_modbus_value(
                device.host, 
                device.port, 
                tag.address,
                tag.data_type
            )
        
        else:
            logger.error(f"Neznámý protokol: {device.protocol}")
            return None, "bad"
    
    async def poll_device_once(self, device_id: int) -> dict[str, tuple[float | None, str]]:
        """
        Jednorázové čtení všech tagů daného zařízení (pro manuální test).
        
        Returns:
            Slovník {název_tagu: (hodnota, kvalita)}
        """
        from .models import Device, Measurement, Tag
        
        results = {}
        
        with Session(self.engine) as session:
            device = session.get(Device, device_id)
            if not device:
                return {"error": (None, "bad")}
            
            tags = session.exec(
                select(Tag).where(Tag.device_id == device.id, Tag.enabled == True)
            ).all()
            
            for tag in tags:
                value, quality = await self._read_tag_value(device, tag)
                results[tag.name] = (value, quality)
                
                # Uložení měření
                measurement = Measurement(
                    tag_id=tag.id,
                    value=value if value is not None else 0.0,
                    timestamp=datetime.utcnow(),
                    quality=quality
                )
                session.add(measurement)
            
            session.commit()
        
        return results


# Globální instance polleru (bude nastavena v main.py)
poller: DataPoller | None = None


def get_poller() -> DataPoller | None:
    """Vrátí globální instanci polleru."""
    return poller


def init_poller(engine: "Engine", interval: float = 5.0) -> DataPoller:
    """Inicializuje a vrátí globální poller."""
    global poller
    poller = DataPoller(engine, interval)
    return poller
