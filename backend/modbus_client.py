"""
Async Modbus TCP klient pro čtení hodnot z Modbus serveru.
Využívá knihovnu pymodbus v async režimu.

Podporované formáty adres:
- hr_N: Holding Register (čtení/zápis) - adresa N
- ir_N: Input Register (jen čtení) - adresa N
- co_N: Coil (čtení/zápis, bool) - adresa N
- di_N: Discrete Input (jen čtení, bool) - adresa N
"""

import logging
import re
import struct
from typing import Optional

from pymodbus.client import AsyncModbusTcpClient

logger = logging.getLogger(__name__)


def parse_modbus_address(address: str) -> tuple[str, int]:
    """
    Parsuje Modbus adresu ve formátu 'prefix_číslo'.
    
    Args:
        address: Adresa ve formátu 'hr_0', 'co_1', 'ir_30001', 'di_0'
    
    Returns:
        Tuple (typ registru, adresa)
    
    Raises:
        ValueError: Pokud je formát neplatný
    """
    match = re.match(r'^(hr|ir|co|di)_(\d+)$', address.lower())
    if not match:
        raise ValueError(f"Neplatný formát Modbus adresy: {address}. "
                        f"Očekávaný formát: hr_N, ir_N, co_N, di_N")
    
    register_type = match.group(1)
    register_address = int(match.group(2))
    
    return register_type, register_address


async def read_modbus_value(
    host: str, 
    port: int, 
    address: str,
    data_type: str = "float"
) -> tuple[Optional[float], str]:
    """
    Přečte hodnotu z Modbus TCP serveru.
    
    Args:
        host: IP adresa serveru
        port: Port serveru (typicky 502 nebo 5020)
        address: Adresa ve formátu 'hr_N', 'ir_N', 'co_N', 'di_N'
        data_type: Datový typ ('float', 'int', 'bool')
    
    Returns:
        Tuple (hodnota jako float nebo None, kvalita 'good'/'bad')
    """
    try:
        register_type, reg_addr = parse_modbus_address(address)
    except ValueError as e:
        logger.error(str(e))
        return None, "bad"
    
    client = AsyncModbusTcpClient(host=host, port=port)
    
    try:
        await client.connect()
        
        if not client.connected:
            logger.error(f"Nepodařilo se připojit k Modbus serveru {host}:{port}")
            return None, "bad"
        
        logger.debug(f"Připojeno k Modbus serveru: {host}:{port}")
        
        # Čtení podle typu registru
        if register_type == "hr":
            # Holding Register - pro float čteme 2 registry
            count = 2 if data_type == "float" else 1
            result = await client.read_holding_registers(address=reg_addr, count=count)
            
        elif register_type == "ir":
            # Input Register
            count = 2 if data_type == "float" else 1
            result = await client.read_input_registers(address=reg_addr, count=count)
            
        elif register_type == "co":
            # Coil (boolean)
            result = await client.read_coils(address=reg_addr, count=1)
            
        elif register_type == "di":
            # Discrete Input (boolean)
            result = await client.read_discrete_inputs(address=reg_addr, count=1)
        
        else:
            logger.error(f"Neznámý typ registru: {register_type}")
            return None, "bad"
        
        # Zpracování výsledku
        if result.isError():
            logger.error(f"Modbus chyba při čtení {address}: {result}")
            return None, "bad"
        
        # Konverze na hodnotu
        if register_type in ("co", "di"):
            # Boolean hodnota
            value = 1.0 if result.bits[0] else 0.0
            
        elif data_type == "float" and len(result.registers) >= 2:
            # Float z dvou registrů (IEEE 754)
            high = result.registers[0]
            low = result.registers[1]
            packed = struct.pack('>HH', high, low)
            value = struct.unpack('>f', packed)[0]
            
        elif data_type == "int":
            # Integer z jednoho registru
            value = float(result.registers[0])
            
        else:
            # Výchozí - jeden registr jako int
            value = float(result.registers[0])
        
        logger.debug(f"Modbus čtení {address}: {value}")
        return value, "good"
        
    except Exception as e:
        logger.error(f"Chyba při čtení Modbus {host}:{port}/{address}: {e}")
        return None, "bad"
        
    finally:
        client.close()


async def read_modbus_values_batch(
    host: str,
    port: int,
    addresses: list[tuple[str, str]]  # [(address, data_type), ...]
) -> dict[str, tuple[Optional[float], str]]:
    """
    Přečte více hodnot z Modbus serveru v jednom připojení.
    
    Args:
        host: IP adresa serveru
        port: Port serveru
        addresses: Seznam tuple (adresa, datový_typ)
    
    Returns:
        Slovník {adresa: (hodnota, kvalita)}
    """
    client = AsyncModbusTcpClient(host=host, port=port)
    results = {}
    
    try:
        await client.connect()
        
        if not client.connected:
            logger.error(f"Nepodařilo se připojit k Modbus serveru {host}:{port}")
            return {addr: (None, "bad") for addr, _ in addresses}
        
        for address, data_type in addresses:
            try:
                register_type, reg_addr = parse_modbus_address(address)
                
                # Čtení podle typu registru
                if register_type == "hr":
                    count = 2 if data_type == "float" else 1
                    result = await client.read_holding_registers(address=reg_addr, count=count)
                elif register_type == "ir":
                    count = 2 if data_type == "float" else 1
                    result = await client.read_input_registers(address=reg_addr, count=count)
                elif register_type == "co":
                    result = await client.read_coils(address=reg_addr, count=1)
                elif register_type == "di":
                    result = await client.read_discrete_inputs(address=reg_addr, count=1)
                else:
                    results[address] = (None, "bad")
                    continue
                
                if result.isError():
                    results[address] = (None, "bad")
                    continue
                
                # Konverze na hodnotu
                if register_type in ("co", "di"):
                    value = 1.0 if result.bits[0] else 0.0
                elif data_type == "float" and len(result.registers) >= 2:
                    high = result.registers[0]
                    low = result.registers[1]
                    packed = struct.pack('>HH', high, low)
                    value = struct.unpack('>f', packed)[0]
                else:
                    value = float(result.registers[0])
                
                results[address] = (value, "good")
                
            except Exception as e:
                logger.error(f"Chyba při čtení {address}: {e}")
                results[address] = (None, "bad")
        
        return results
        
    except Exception as e:
        logger.error(f"Chyba při připojení k Modbus {host}:{port}: {e}")
        return {addr: (None, "bad") for addr, _ in addresses}
        
    finally:
        client.close()
