import asyncio

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_ollama import ChatOllama
from langchain.agents import create_agent


async def main():

    # ==============================================
    # CONNECT TO MCP SERVER
    # ==============================================

    client = MultiServerMCPClient(
        {
            "financial": {
                "transport": "streamable_http",
                "url": "https://financial-mcp-fj0m.onrender.com/mcp",
            }
        }
    )


    # ==============================================
    # GET TOOLS FROM MCP SERVER
    # ==============================================

    tools = await client.get_tools()


    # ==============================================
    # LOCAL AI MODEL
    # ==============================================

    model = ChatOllama(
        model="qwen3:4b"
    )


    # ==============================================
    # CREATE AGENT
    # ==============================================

    agent = create_agent(
        model,
        tools
    )


    # ==============================================
    # USER REQUEST
    # ==============================================

    question = input("Ask your question: ")


    # ==============================================
    # SEND REQUEST TO AGENT
    # ==============================================

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


    # ==============================================
    # PRINT FINAL RESPONSE
    # ==============================================

    print(
        response["messages"][-1].content
    )


# ==============================================
# START
# ==============================================

asyncio.run(main())