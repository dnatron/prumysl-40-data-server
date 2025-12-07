# Data Gateway - Průmysl 4.0

Centrální sběrný server pro průmyslová data s podporou protokolů **OPC UA** a **Modbus TCP**.

## 🎯 Funkce

- **Správa zařízení**: Přidávání, editace a mazání průmyslových zařízení (PLC, senzory)
- **Definice tagů**: Konfigurace datových bodů s protokol-specifickými adresami
- **Automatický sběr**: Pravidelné čtení hodnot každých 5 sekund
- **Webové rozhraní**: Dashboard s přehledem zařízení a aktuálními hodnotami
- **Historie měření**: Uložení všech hodnot s časovým razítkem

## 🔧 Technologie

- **Backend**: Python 3.12 + FastAPI
- **Databáze**: SQLite + SQLModel
- **Frontend**: Jinja2 + Bootstrap 5 + HTMX
- **Protokoly**: OPC UA (asyncua), Modbus TCP (pymodbus)

## 📦 Instalace

### Pomocí uv (doporučeno)

```bash
# Instalace závislostí
uv sync

# Spuštění serveru
uv run uvicorn main:app --reload
```

### Pomocí pip

```bash
# Vytvoření virtuálního prostředí
python -m venv venv
source venv/bin/activate  # Linux/Mac
# nebo: venv\Scripts\activate  # Windows

# Instalace závislostí
pip install -r requirements.txt

# Spuštění serveru
uvicorn main:app --reload
```

## 🚀 Spuštění

Po spuštění je aplikace dostupná na: **http://localhost:8080**

## 📖 Použití

### 1. Přidání zařízení

1. Klikněte na "Přidat zařízení"
2. Vyplňte údaje:
   - **Název**: např. "Lis-01"
   - **Protokol**: OPC UA nebo Modbus TCP
   - **Host**: IP adresa zařízení
   - **Port**: 4840 (OPC UA) / 502 (Modbus)

### 2. Přidání tagů

Pro každé zařízení definujte tagy (datové body):

**OPC UA formát adresy:**
- `ns=2;s=Teplota` - String identifikátor
- `i=2258` - Numerický identifikátor

**Modbus formát adresy:**
- `hr_0` - Holding Register (adresa 0)
- `ir_0` - Input Register
- `co_0` - Coil (boolean)
- `di_0` - Discrete Input

### 3. Jak zjistit hodnoty pro nastavení

#### OPC UA - zjištění Node ID

**Pomocí nástroje UaExpert (doporučeno):**
1. Stáhněte [UaExpert](https://www.unified-automation.com/products/development-tools/uaexpert.html) (zdarma)
2. Připojte se k OPC UA serveru (např. `opc.tcp://127.0.0.1:4840`)
3. V levém panelu procházejte strom uzlů
4. Klikněte na uzel → v pravém panelu najdete **NodeId** (např. `ns=2;s=Teplota`)

**Pomocí Python skriptu:**
```python
from asyncua import Client

async def browse_nodes():
    client = Client("opc.tcp://127.0.0.1:4840")
    await client.connect()
    
    # Procházení uzlů od root
    root = client.nodes.objects
    children = await root.get_children()
    for child in children:
        name = await child.read_browse_name()
        print(f"{name.Name}: {child.nodeid}")
    
    await client.disconnect()

import asyncio
asyncio.run(browse_nodes())
```

**Simulátor z Fáze 1 (port 8000):**
- Endpoint: `opc.tcp://127.0.0.1:4840`
- Dostupné tagy viz API simulátoru: `http://localhost:8000/api/tags`

#### Modbus - zjištění adres registrů

**Z dokumentace zařízení:**
- Každé PLC/zařízení má dokumentaci s mapou registrů
- Typicky tabulka: `Registr | Adresa | Popis | Datový typ`

**Běžné konvence Modbus adres:**
| Typ | Rozsah | Prefix | Popis |
|-----|--------|--------|-------|
| Coil | 00001-09999 | `co_` | Digitální výstup (R/W) |
| Discrete Input | 10001-19999 | `di_` | Digitální vstup (R) |
| Input Register | 30001-39999 | `ir_` | Analogový vstup (R) |
| Holding Register | 40001-49999 | `hr_` | Analogový výstup (R/W) |

**Příklad:** Registr 40001 → adresa v Data Gateway: `hr_0` (offset od 40001)

**Testování pomocí modbus-cli:**
```bash
# Instalace
pip install modbus-cli

# Čtení holding registru 0
modbus read 127.0.0.1:502 h@0

# Čtení 10 registrů od adresy 0
modbus read 127.0.0.1:502 h@0/10
```

### 4. Sběr dat

- Data se automaticky sbírají každých 5 sekund
- Manuální čtení: tlačítko "Načíst nyní" v detailu zařízení

## 📁 Struktura projektu

```
├── backend/
│   ├── models.py          # SQLModel entity (Device, Tag, Measurement)
│   ├── opc_client.py      # Async OPC UA klient
│   ├── modbus_client.py   # Async Modbus klient
│   └── poller.py          # Polling smyčka pro sběr dat
│
├── frontend/
│   ├── templates/         # Jinja2 šablony
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── device_form.html
│   │   ├── device_detail.html
│   │   └── partials/
│   └── static/
│       └── style.css
│
├── main.py                # FastAPI aplikace
├── data.sqlite            # SQLite databáze (vytvoří se automaticky)
├── requirements.txt
└── README.md
```

## 🧪 Testování

Pro testování potřebujete simulátor PLC:

### OPC UA simulátor
Použijte projekt z Fáze 1 nebo jakýkoliv OPC UA server na portu 4840.

### Modbus simulátor
```bash
# Instalace diagslave (Modbus simulátor)
# nebo použijte pymodbus server
```

## ✅ Rychlý návod: Přidání zařízení a tagů

### Krok 1: OPC UA zařízení (simulátor na portu 4840)

**A) Přidání zařízení:**

1. Otevřete http://localhost:8080
2. Klikněte na **"Přidat zařízení"**
3. Vyplňte formulář:

| Pole | Hodnota |
|------|---------|
| Název | `Lis-01` |
| Protokol | `OPC UA` |
| Host | `127.0.0.1` |
| Port | `4840` |
| Endpoint URL | `opc.tcp://127.0.0.1:4840` |

4. Klikněte **"Vytvořit zařízení"**

**B) Přidání tagů:**

Po vytvoření zařízení se dostanete na stránku editace. V sekci "Tagy" přidejte:

| Název | Adresa | Datový typ |
|-------|--------|------------|
| Teplota | `ns=2;i=2` | float |
| Tlak | `ns=2;i=3` | float |
| Stav_RUN | `ns=2;i=4` | bool |

> 💡 **Tip:** Adresy tagů zjistíte v API simulátoru: `http://localhost:8000/api/tags`

---

### Krok 2: Modbus TCP zařízení (simulátor na portu 5020)

**A) Přidání zařízení:**

1. Na dashboardu klikněte **"Přidat zařízení"**
2. Vyplňte formulář:

| Pole | Hodnota |
|------|---------|
| Název | `Cerpadlo-01` |
| Protokol | `Modbus TCP` |
| Host | `127.0.0.1` |
| Port | `5020` |

4. Klikněte **"Vytvořit zařízení"**

**B) Přidání tagů:**

Modbus simulátor mapuje senzory na **Holding Registry** od adresy 0:

| Název | Adresa | Datový typ | Popis |
|-------|--------|------------|-------|
| Teplota | `hr_0` | float | Registry 0-1 (IEEE 754 float) |
| Tlak | `hr_2` | float | Registry 2-3 |
| Otacky | `hr_4` | float | Registry 4-5 |
| Stav | `co_0` | bool | Coil 0 |

**Formát Modbus adres:**
- `hr_N` - Holding Register na adrese N (float používá 2 registry: N a N+1)
- `ir_N` - Input Register
- `co_N` - Coil (boolean)
- `di_N` - Discrete Input

---

### Krok 3: Ověření sběru dat

1. Po přidání tagů se vraťte na **Dashboard** (/)
2. Data by se měla zobrazit do 5 sekund
3. Pro okamžité čtení klikněte na **Detail zařízení** → **"Načíst nyní"**

---

## 📋 Referenční příklady JSON (pro API)

### OPC UA zařízení
```json
{
  "name": "Lis-01",
  "protocol": "opcua",
  "host": "127.0.0.1",
  "port": 4840,
  "endpoint_url": "opc.tcp://127.0.0.1:4840"
}
```

### Modbus zařízení
```json
{
  "name": "Cerpadlo-01",
  "protocol": "modbus",
  "host": "127.0.0.1",
  "port": 5020
}
```

## 📝 API Endpointy

| Endpoint | Metoda | Popis |
|----------|--------|-------|
| `/` | GET | Dashboard |
| `/device/new` | GET | Formulář pro nové zařízení |
| `/device/{id}` | GET | Detail zařízení |
| `/device/{id}/edit` | GET | Editace zařízení |
| `/device/save` | POST | Uložení zařízení |
| `/device/{id}/poll` | POST | Manuální čtení |
| `/api/devices` | GET | JSON seznam zařízení |
| `/api/device/{id}/measurements` | GET | JSON měření |

## 📄 Licence

MIT License
