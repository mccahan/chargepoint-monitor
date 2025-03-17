FROM mccahan/v0-export-builder:latest AS build-static

COPY static-app.zip /app/app.zip
RUN build-static

# Use the official Python image from the Docker Hub
FROM python:3.9-alpine

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

COPY --from=build-static /app/output-dir /app/static
RUN find /app/static -type f -exec sed -i 's/http:\/\/localhost:8085\/ws/\/ws/g' {} +

# Command to run the application
CMD ["python", "-u", "main.py"]