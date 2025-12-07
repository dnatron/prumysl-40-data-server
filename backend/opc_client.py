"""
Async OPC UA klient pro čtení hodnot z OPC UA serveru.
Využívá knihovnu asyncua (opcua-asyncio).
"""

import logging
from typing import Any, Optional

from asyncua import Client
from asyncua.ua import NodeId, NodeIdType

logger = logging.getLogger(__name__)


async def read_opcua_value(endpoint: str, node_id: str) -> tuple[Optional[float], str]:
    """
    Přečte hodnotu z OPC UA serveru.
    
    Args:
        endpoint: OPC UA endpoint URL (např. 'opc.tcp://127.0.0.1:4840')
        node_id: Identifikátor uzlu (např. 'ns=2;s=Teplota' nebo 'i=2258')
    
    Returns:
        Tuple (hodnota jako float nebo None, kvalita 'good'/'bad')
    """
    client = Client(url=endpoint)
    
    try:
        await client.connect()
        logger.debug(f"Připojeno k OPC UA serveru: {endpoint}")
        
        # Získání uzlu podle node_id
        node = client.get_node(node_id)
        
        # Přečtení hodnoty
        value = await node.read_value()
        
        # Konverze na float
        if isinstance(value, bool):
            result = 1.0 if value else 0.0
        elif isinstance(value, (int, float)):
            result = float(value)
        else:
            logger.warning(f"Neočekávaný typ hodnoty pro {node_id}: {type(value)}")
            result = float(value) if value is not None else None
        
        logger.debug(f"OPC UA čtení {node_id}: {result}")
        return result, "good"
        
    except Exception as e:
        logger.error(f"Chyba při čtení OPC UA {endpoint}/{node_id}: {e}")
        return None, "bad"
        
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


async def read_opcua_values_batch(
    endpoint: str, 
    node_ids: list[str]
) -> dict[str, tuple[Optional[float], str]]:
    """
    Přečte více hodnot z OPC UA serveru v jednom připojení.
    
    Args:
        endpoint: OPC UA endpoint URL
        node_ids: Seznam identifikátorů uzlů
    
    Returns:
        Slovník {node_id: (hodnota, kvalita)}
    """
    client = Client(url=endpoint)
    results = {}
    
    try:
        await client.connect()
        logger.debug(f"Batch čtení z OPC UA serveru: {endpoint}")
        
        for node_id in node_ids:
            try:
                node = client.get_node(node_id)
                value = await node.read_value()
                
                # Konverze na float
                if isinstance(value, bool):
                    result = 1.0 if value else 0.0
                elif isinstance(value, (int, float)):
                    result = float(value)
                else:
                    result = float(value) if value is not None else None
                
                results[node_id] = (result, "good")
                
            except Exception as e:
                logger.error(f"Chyba při čtení uzlu {node_id}: {e}")
                results[node_id] = (None, "bad")
        
        return results
        
    except Exception as e:
        logger.error(f"Chyba při připojení k OPC UA {endpoint}: {e}")
        # Všechny node_ids označíme jako chybné
        return {node_id: (None, "bad") for node_id in node_ids}
        
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
