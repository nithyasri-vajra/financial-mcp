from fastmcp import FastMCP

mcp = FastMCP()

@mcp.tool()
def get_balance(customer_id: int):
    customers = {
        101: {
            "name": "Raghul",
            "balance": 50000
        },
        102: {
            "name": "Arun",
            "balance": 75000
        }
    }

    customer = customers.get(customer_id)

    if customer is None:
        return "Customer not found"

    return f"{customer['name']}'s balance is ₹{customer['balance']}"

@mcp.tool()
def proccess():    
    return {"proccessdata": "proccess data"}


if __name__=="__main__":
    mcp.run(
    transport="streamable-http",
    host="0.0.0.0",
    port=8000
)