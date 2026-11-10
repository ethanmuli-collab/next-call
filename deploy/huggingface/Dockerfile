# Hugging Face Space (Docker SDK): builds the app straight from the public GitHub repo.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 NEXT_CALL_OFFLINE=1
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 user
USER user
ENV PATH=/home/user/.local/bin:$PATH
WORKDIR /home/user/app
RUN git clone --depth 1 https://github.com/ethanmuli-collab/next-call.git .
RUN pip install --no-cache-dir --user -r requirements.txt gunicorn==23.0.0
EXPOSE 7860
CMD ["gunicorn", "-w", "1", "--threads", "8", "--timeout", "300", "-b", "0.0.0.0:7860", "server:app"]
