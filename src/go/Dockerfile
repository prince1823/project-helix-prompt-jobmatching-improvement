# Use an official Go image as the base
FROM golang:1.24.3-bookworm AS base

# Set up Go dependencies
WORKDIR /app/src/go
COPY go.mod go.sum ./
RUN go mod download

# Copy Go source code
COPY . ./
RUN go build -o whatsapp-bot
