FROM mcr.microsoft.com/playwright/python:v1.53.0

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*


RUN pip install --no-cache-dir \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir \
    git+https://github.com/linto-ai/whisper-timestamped.git \
    fastapi \
    uvicorn    

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt



COPY . .

EXPOSE  8100

RUN playwright install --with-deps

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8100"]