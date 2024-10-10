# The Wall API


The Wall API is a Django REST Framework (DRF) project that simulates the construction of a colossal wall in a fictional world. The API tracks material quantities, costs, and construction progress across multiple sections of the wall, managed by the Sworn Brothers of the Night's Watch.


# Story


> "The White Walkers sleep beneath the ice for thousands of years. And when they wake up..."  
> "And when they wake up... what?"  
> "I hope the Wall is high enough."

The Wall is a massive fortification being built along the northern border of the Seven Kingdoms. It stretches for 100 leagues (300 miles) and is 30 feet tall, made of solid ice. The Sworn Brothers of the Night's Watch manage the construction, ensuring that each section has its own dedicated crew.


# Features
- Track daily ice usage and construction costs
- Sequential and concurrent construction simulation
- API endpoints for querying construction progress and cost overview

# Dependencies
- Django Rest Framework - implementation framework
- Redis
  - In-memory cache management
  - Message broker for Celery
- PostgreSQL - DB engine for persistent data storage
- Celery - for scheduling of periodic tasks
- Docker - for containerization and deployment
  - Docker compose
  - Docker swarm
- Poetry - manage dependencies and ensure a reproducible environment


# Installation Instructions

### 1. Clone the repository
```bash
git clone https://github.com/Alexandar83/the-wall-api.git
```

### 2. Local development setup >All scripts must be executed in the project's root folder<
<details>
<summary>DEV</summary>
<br>

<details>
<summary>2.1 Install dependencies</summary>
<br>

- pip installation
```bash
  pip install -r requirements.txt
```
- Poetry installation
```bash
  pip install poetry
  poetry install   
```
</details>

<details>
<summary>2.2 Set up the DEV configuration</summary>
<br>

- Required .config and .env files:
  - *config/envs/common/redis.conf*
  - *config/envs/dev/postgres_dev.env*
  - *config/envs/dev/the_wall_api_dev.env*
- Check the *.example files in the relevant folders for example configuration values
</details>

<details>
<summary>2.3 Workflow</summary>
<br>
- 2.3.1 Start a virtual environment
  
- 2.3.2 Start all dockerized services:

  - *This script ensures that:*
    - *The Django migrations will be run after the PostgreSQL server is completely started*
    - *The Celery services are started after the image they're using is built*
  
```bash
config/docker/scripts/docker-compose-dev+migrations.sh
```

- 2.3.3 Start a local Django development server:
```bash
python manage.py runserver
```

- 2.3.4 Send requests to the API endpoint: *http://localhost:8000/api/v1/*

- 2.3.5 Create a super user:
```bash
python manage.py createsuperuser
```

- 2.3.6 Access the built-in Django admin panel: *http://localhost:8000/admin*
</details>

<details>
<summary>2.4 Push any changes to a container registry - GHCR usage example below</summary>
<br>

- Build the latest version
```bash
docker build --no-cache -t the-wall-api:latest -f ./config/docker/Dockerfile.prod .
```

- Push it to GHCR
```bash
docker push ghcr.io/<github-repo-name>/the-wall-api --all-tags
```
</details>

</details>

### 3. Production setup (v1)

<details>
<summary>PROD(v1)</summary>
<br>

3.1 **Set up the PROD configuration:**
- Required .config and .env files:
  - *config/envs/common/redis.conf*
  - *config/envs/prod/postgres_prod.env*
  - *config/envs/prod/redis_prod.env*
  - *config/envs/prod/the_wall_api_prod.env*
- Check the *.example files in the relevant folders for example configuration values

3.2 **Docker compose:**
- Ensure the v1 compose file from the repo is placed in ***config/docker/docker-compose-prod-v1.yml***

3.3 **Workflow:**
- Start the app, Redis and PostgreSQL containers:
```bash
docker-compose -p the-wall-api-prod -f config/docker/docker-compose-prod-v1.yml up -d
```
- Send requests to the API endpoint: *http://localhost:8000/api/v1/*
- To stop the containers:
```bash
docker-compose -p the-wall-api-prod -f config/docker/docker-compose-prod-v1.yml down
```

</details>

### 4. Production setup (v2)

<details>
<summary>PROD(v2)</summary>
<br>

4.1 **Set up the PROD configuration:**
- Required .config and .env files:
  - *config/envs/common/redis.conf*
  - *config/envs/prod/the_wall_api_prod.env*
- Required docker secrets files:

  *The following files should contain the values of the according passwords*
  - *config/secrets/postgres_db.txt*
  - *config/secrets/postgres_password.txt*
  - *config/secrets/postgres_user.txt*
  - *config/secrets/redis_password.txt*
- Check the *.example files in the relevant folders for example configuration values

4.2 **Init docker swarm mode**
```bash
docker swarm init
```

4.3 **Manage the docker secrets**
- For each password file in the /secrets folder execute:
```bash
docker secret create <password_name> config/secrets/<password_file_name>.txt
```
- Remove the password files from the /secrets folder

4.4 **Docker stack deploy:**
- Ensure the v2 compose file from the repo is placed in  ***config/docker/docker-compose-prod-v2.yml***
- Ensure the wait_for_postgres.py script from the repo is placed in ***config/docker/scripts/wait_for_postgres.py***

4.5 **Workflow:**
- Start the app, Redis and PostgreSQL by deploying the prod_stack:
```bash
docker stack deploy -c config/docker/docker-compose-prod-v2.yml prod_stack
```
- Send requests to the API endpoint: *http://localhost:8000/api/v1/*
- To stop the stack:
```bash
docker stack rm prod_stack
```

</details>


# Accessing the API
- **Admin Interface:** `http://localhost:8000/admin/`
- **Daily Ice Usage Endpoint:** `http://localhost:8000/api/v1/daily-ice-usage/<profile_id>/<day>/`
- **Cost Overview Endpoints:**
  - `http://localhost:8000/api/v1/cost-overview/` -  pass the `num_crews` query parameter for multi-threaded construction simulation
  - `http://localhost:8000/api/v1/cost-overview/<profile_id>/`


# API Documentation

- **Schema:** `http://localhost:8000/api/v1/schema/`
- **Swagger UI:** `http://localhost:8000/api/v1/swagger-ui/`
- **ReDoc:** `http://localhost:8000/api/v1/redoc/`


# Testing
- Run the full test suite:
```bash
python manage.py test
```

- Run specific test modules:
```bash
python manage.py test the_wall_api.tests.<test_module>
```


# Author

#### Aleksandar Dimitrov
- [LinkedIn](https://www.linkedin.com/in/aleksandar-dimitrov-412833316)
- [Yahoo Email](mailto:sasho_1983@yahoo.com)


# Status

#### Work in progress