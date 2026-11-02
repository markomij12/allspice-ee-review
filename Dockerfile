FROM python:3.12-slim
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
COPY entrypoint.py /entrypoint.py
COPY ee_review /ee_review
ENV PYTHONPATH=/
ENTRYPOINT ["python3", "/entrypoint.py"]
