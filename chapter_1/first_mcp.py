from fastmcp import FastMCP

mcp = FastMCP()


customers = {
    101: {
        "name": "Raghul",
        "balance": 50000,
        "transactions": [
            "₹5000 - Grocery",
            "₹2000 - Fuel",
            "₹10000 - Rent",
            "₹1500 - Food",
            "₹3000 - Shopping"
        ],
        "loan": {
            "status": "Active",
            "amount": 200000,
            "remaining": 120000
        }
    },
    102: {
        "name": "Arun",
        "balance": 75000,
        "transactions": [
            "₹3000 - Grocery",
            "₹5000 - Shopping",
            "₹1500 - Food",
            "₹7000 - Rent",
            "₹2000 - Fuel"
        ],
        "loan": {
            "status": "Closed",
            "amount": 150000,
            "remaining": 0
        }
    }
}


@mcp.tool()
def get_balance(customer_id: int):
    customer = customers.get(customer_id)

    if customer is None:
        return "Customer not found"

    return f"{customer['name']}'s balance is ₹{customer['balance']}"

@mcp.tool()
def find_customer(name: str):
    for customer_id, customer in customers.items():
        if customer["name"].lower() == name.lower():
            return {
                "customer_id": customer_id,
                "name": customer["name"]
            }

    return "Customer not found"

@mcp.tool()
def get_customer_name(customer_id: int):
    customer = customers.get(customer_id)

    if customer is None:
        return "Customer not found"

    return customer["name"]


@mcp.tool()
def get_transactions(customer_id: int, limit: int = 5):
    customer = customers.get(customer_id)

    if customer is None:
        return "Customer not found"

    return {
        "customer": customer["name"],
        "transactions": customer["transactions"][:limit]
    }


@mcp.tool()
def get_loan_status(customer_id: int):
    customer = customers.get(customer_id)

    if customer is None:
        return "Customer not found"

    return {
        "customer": customer["name"],
        "loan_status": customer["loan"]["status"],
        "loan_amount": customer["loan"]["amount"],
        "remaining_amount": customer["loan"]["remaining"]
    }


@mcp.tool()
def get_customer_details(customer_id: int):
    customer = customers.get(customer_id)

    if customer is None:
        return "Customer not found"

    return {
        "customer_id": customer_id,
        "name": customer["name"],
        "balance": customer["balance"],
        "loan_status": customer["loan"]["status"]
    }


@mcp.tool()
def proccess():
    return {"proccessdata": "proccess data"}


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8000
    )