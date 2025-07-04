# ---- Builder Stage ----
# This stage installs dependencies using pipenv for reproducible builds
FROM python:3.13.5-alpine AS builder

# Install pipenv
RUN pip install pipenv

# Set the working directory in the container
WORKDIR /app

# Copy dependency definition files
COPY Pipfile Pipfile.lock ./

# Install dependencies into the system python, not a virtualenv.
# --deploy checks that Pipfile.lock is up-to-date and fails if not.
# --system installs to the system site-packages.
RUN pipenv install --system --deploy --ignore-pipfile


# ---- Final Stage ----
# This stage creates the final, lean image
FROM python:3.13.5-alpine

# Set working directory
WORKDIR /app

# Copy the installed dependencies from the builder stage
COPY --from=builder /usr/local/lib/python*/site-packages /usr/local/lib/python*/site-packages

# Copy only the necessary application code from the build context
# This avoids copying dev files, git history, etc. into the final image
COPY shokobridge/ ./shokobridge/
COPY ShokoBridge.py .

# Set the entrypoint to run the script
ENTRYPOINT ["python", "ShokoBridge.py"]