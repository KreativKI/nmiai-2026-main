FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir \
    torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir \
    onnxruntime==1.20.0 \
    opencv-python-headless==4.9.0.80 \
    numpy==1.26.4 \
    Pillow==10.2.0 \
    ensemble-boxes==1.0.9 \
    scipy==1.12.0
RUN mkdir -p /data/images /output
COPY submission_pretrained/ /app/
CMD ["python", "run.py", "--images", "/data/images", "--output", "/tmp/predictions.json"]
