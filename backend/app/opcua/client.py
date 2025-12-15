import asyncio
# from asyncua import Client

class OPCUAClient:
    def __init__(self, url: str):
        self.url = url
        self.client = None

    async def connect(self):
        # self.client = Client(url=self.url)
        # await self.client.connect()
        print(f"Connecting to OPC UA at {self.url}")
        pass

    async def disconnect(self):
        # if self.client:
        #     await self.client.disconnect()
        pass

    async def read_node(self, node_id: str):
        # return await self.client.get_node(node_id).read_value()
        pass

# Singleton instance or factory can be provided here
