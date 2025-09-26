
FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends     build-essential curl ca-certificates &&     rm -rf /var/lib/apt/lists/*

# Copy project (user will mount or copy their code here in compose)
COPY . /app

# Install Python deps
RUN python -m venv .venv && . .venv/bin/activate &&     pip install --no-cache-dir -r requirements.txt

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

EXPOSE 8010
CMD ["uvicorn", "agent.app.server:app", "--host", "0.0.0.0", "--port", "8010"]
