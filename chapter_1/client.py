import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


server_params = StdioServerParameters(
    command="python",
    args=["chapter_1/first_mcp.py"],
)


async def main():

    async with stdio_client(server_params) as (read, write):

        async with ClientSession(read, write) as session:

            await session.initialize()

            tools = await session.list_tools()

            print("Available tools:")

            for tool in tools.tools:
                print(tool.name)

            result = await session.call_tool(
                "find_meeting",
                arguments={
                    "date": "2026-09-16",
                    "keyword": "client"
                }
            )

            print("Result:")
            print(result)


if __name__ == "__main__":
    asyncio.run(main())