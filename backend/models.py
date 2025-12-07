"""
SQLModel definice pro Kepware-style architekturu.
Entity: Device → Tag → Measurement
"""

from datetime import datetime
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


# ───────────────────────────────────────
# 1. ZAŘÍZENÍ (Device / PLC / Stroj)
# ───────────────────────────────────────
class Device(SQLModel, table=True):
    """Reprezentuje jedno průmyslové zařízení (např. PLC 'Lis-01')."""
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, description="Např. 'Lis-01', 'Čerpadlo-A'")
    protocol: str = Field(description="Protokol: 'opcua' nebo 'modbus'")
    host: str = Field(default="127.0.0.1", description="IP adresa zařízení")
    port: int = Field(description="Port: 4840 pro OPC UA, 5020 pro Modbus")
    endpoint_url: Optional[str] = Field(
        default=None, 
        description="OPC UA endpoint URL, např. 'opc.tcp://127.0.0.1:4840'"
    )
    enabled: bool = Field(default=True, description="Zda je zařízení aktivní pro sběr")
    description: Optional[str] = Field(default=None, description="Popis zařízení")
    
    # Vztah k tagům
    tags: List["Tag"] = Relationship(back_populates="device", sa_relationship_kwargs={"cascade": "all, delete-orphan"})


# ───────────────────────────────────────
# 2. TAG (Proměnná / Senzor / Datový bod)
# ───────────────────────────────────────
class Tag(SQLModel, table=True):
    """Reprezentuje jeden datový bod (senzor, stav, čítač)."""
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(description="Např. 'Teplota_motoru', 'Stav_RUN'")
    address: str = Field(description="""
        Protokol-specifická adresa:
        - OPC UA: 'ns=2;s=Teplota' nebo 'i=2258'
        - Modbus: 'hr_0' (holding register), 'co_1' (coil), 
                  'ir_0' (input register), 'di_0' (discrete input)
    """)
    data_type: str = Field(default="float", description="Datový typ: float, int, bool")
    description: Optional[str] = Field(default=None, description="Popis tagu")
    enabled: bool = Field(default=True, description="Zda je tag aktivní pro sběr")
    
    # Vazba na zařízení
    device_id: int = Field(foreign_key="device.id")
    device: Device = Relationship(back_populates="tags")
    
    # Vztah k měřením
    measurements: List["Measurement"] = Relationship(
        back_populates="tag", 
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


# ───────────────────────────────────────
# 3. MĚŘENÍ (Hodnota v čase)
# ───────────────────────────────────────
class Measurement(SQLModel, table=True):
    """Historická hodnota tagu v čase."""
    
    id: Optional[int] = Field(default=None, primary_key=True)
    value: float = Field(description="Normalizovaná hodnota (bool: 0/1, int/float: hodnota)")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, 
        description="Čas měření"
    )
    quality: str = Field(default="good", description="Kvalita měření: good, bad, uncertain")
    
    # Vazba na tag
    tag_id: int = Field(foreign_key="tag.id")
    tag: Tag = Relationship(back_populates="measurements")


# ───────────────────────────────────────
# Pomocné modely pro API/formuláře
# ───────────────────────────────────────
class DeviceCreate(SQLModel):
    """Model pro vytvoření nového zařízení."""
    name: str
    protocol: str
    host: str = "127.0.0.1"
    port: int
    endpoint_url: Optional[str] = None
    description: Optional[str] = None


class TagCreate(SQLModel):
    """Model pro vytvoření nového tagu."""
    name: str
    address: str
    data_type: str = "float"
    description: Optional[str] = None
