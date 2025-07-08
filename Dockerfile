FROM mcr.microsoft.com/playwright/python:v1.53.0

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE  8100

RUN playwright install --with-deps

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8100"]