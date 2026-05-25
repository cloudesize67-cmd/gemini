FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agents/ ./agents/
COPY mcp/ ./mcp/
COPY pipeline.py .
COPY server.py .

# Create __init__ files
RUN touch agents/__init__.py mcp/__init__.py

ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE 8000

CMD ["python", "server.py"]
