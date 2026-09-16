      

import asyncio

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_ollama import ChatOllama
from langchain.agents import create_agent


async def main():

    # MCP server connect
    client = MultiServerMCPClient(
        {
            "financial": {
                "transport": "streamable_http",
                "url": "https://financial-mcp-fj0m.onrender.com/mcp",
            }
        }
    )

    # MCP server-la irukkura tools eduthukkum
    tools = await client.get_tools()

    # Local AI
    model = ChatOllama(
        model="qwen3:4b"
    )

    # AI + tools
    agent = create_agent(
        model,
        tools
    )

    # User question
    question = input("Ask your question: ")

    # AI question understand panni tool choose/call pannum
    response = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": question
                }
            ]
        }
    )

    print(response["messages"][-1].content)


asyncio.run(main())