# Python slim base
FROM python:3.11-slim

# system deps for Pillow / opencv / pymupdf
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      build-essential libgl1 libglib2.0-0 libsm6 libxrender1 libxext6 poppler-utils tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

# create tmp dirs
RUN mkdir -p /tmp/uploads /tmp/out
ENV UPLOAD_TMP=/tmp/uploads
ENV OUT_TMP=/tmp/out
ENV MAX_CONTENT_LENGTH=26214400

# set port
ENV PORT=5000

# Run with gunicorn in production
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "2", "server:app"]
