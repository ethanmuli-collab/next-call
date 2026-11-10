# Next Call web app. Runs in offline mode unless OPENAI_API_KEY is provided at run time.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN useradd -m -u 1000 user
USER user
ENV PATH=/home/user/.local/bin:$PATH
WORKDIR /home/user/app
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt gunicorn==23.0.0
COPY --chown=user . .
EXPOSE 7860
# one worker: the app keeps the state of the running Flow in memory
CMD ["gunicorn", "-w", "1", "--threads", "8", "--timeout", "300", "-b", "0.0.0.0:7860", "server:app"]
