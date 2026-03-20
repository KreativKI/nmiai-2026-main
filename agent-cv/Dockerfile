# NorgesGruppen sandbox mirror for local validation
# Matches competition environment: Python 3.11, exact package versions, blocked imports
FROM python:3.11-slim

WORKDIR /app

# Install exact sandbox package versions (CPU variants for local testing)
RUN pip install --no-cache-dir \
    torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir \
    onnxruntime==1.20.0 \
    opencv-python-headless==4.9.0.80 \
    numpy==1.26.4 \
    Pillow==10.2.0 \
    pycocotools==2.0.7 \
    timm==0.9.12 \
    safetensors==0.4.2 \
    scipy==1.12.0 \
    scikit-learn==1.4.0

# Create standard directories
RUN mkdir -p /data/images /output

# Copy submission files
COPY submission/ /app/

# Default command
CMD ["python", "run.py", "--images", "/data/images", "--output", "/tmp/predictions.json"]
