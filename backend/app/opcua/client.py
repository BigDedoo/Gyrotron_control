import asyncio
import logging

logger = logging.getLogger(__name__)

class OPCUAClient:
    def __init__(self, url="opc.tcp://localhost:4840"):
        self.url = url
        self.client = None
        logger.info(f"Connecting to OPC UA Server (PLC) at {self.url}")
        
    async def connect(self):
        """
        Connect to the PLC's OPC UA Server.
        The PLC acts as the server, and this backend application acts as the client.
        """
        pass

    async def disconnect(self):
        pass

    async def read_node(self, node_id: str):
        pass
