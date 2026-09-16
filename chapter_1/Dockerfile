FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir fastmcp

COPY chapter_1 ./chapter_1

EXPOSE 8000

CMD ["python", "chapter_1/first_mcp.py"]