# Use an official Python image as the base
FROM python:3.13-slim AS base

# Set up Python dependencies
WORKDIR /app/src/ui
COPY pyproject.toml uv.lock ./
RUN pip install --upgrade pip && \
    pip install uv && \
    uv sync

# Copy Python source code
COPY . ./
EXPOSE 8501
