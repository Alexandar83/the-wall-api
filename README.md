# The Wall API


The Wall API is a Django REST Framework (DRF) project that simulates the construction of a colossal wall in a fictional world. The API tracks material quantities, costs, and construction progress across multiple sections of the wall, managed by the Sworn Brothers of the Night's Watch.


# Story


> "The White Walkers sleep beneath the ice for thousands of years. And when they wake up..."  
> "And when they wake up... what?"  
> "I hope the Wall is high enough."

The Wall is a massive fortification being built along the northern border of the Seven Kingdoms. It stretches for 100 leagues (300 miles) and is 30 feet tall, made of solid ice. The Sworn Brothers of the Night's Watch manage the construction, ensuring that each section has its own dedicated crew.


# Features

  **Track daily ice usage and construction costs**
  **Multi-threaded construction simulation**
  **API endpoints for querying construction progress and cost overview**


## Installation Instructions


### Prerequisites

- Python 3.11
- Key Libraries:
  - Django 5.1
  - Django REST Framework 3.15.2
  - Python-dotenv 1.0.1
  - drf-spectacular 0.27.2
  - openapi-spec-validator 0.7.1
  - redis
  - django-redis


### Installation Steps


1. **Clone the repository:**
  git clone https://github.com/yourusername/the-wall-api.git


2. **Install dependencies:**
 ```bash
   # pip
   pip install -r requirements.txt
   
   # Poetry to consume pyproject.toml and poetry.lock.
   pip install poetry
   poetry install   
```

3. **Set up the `.env` file:**

   Create a `.env` file in the root of the project and configure it as follows:
   # For switching between the env. vars below: 'env'|'prod'
   PROJECT_MODE='dev'

   # Prod settings
   PROD_SECRET_KEY='PROD_SECRET_KEY'
   
   PROD_DEBUG=False
   
   PROD_ALLOWED_HOSTS=localhost,127.0.0.1
   
   PROD_DB_ENGINE='django.db.backends.sqlite3'
   
   PROD_DB_NAME='db.sqlite3'
   
   PROD_TEST_LOGGING_LEVEL='FAILED'
   
   # Dev. Settings
   DEV_SECRET_KEY='DEV_SECRET_KEY'
   
   DEV_DEBUG=True
   
   DEV_ALLOWED_HOSTS=localhost,127.0.0.1
   
   DEV_DB_ENGINE='django.db.backends.sqlite3'
   
   DEV_DB_NAME='db.sqlite3'

   DEV_TEST_LOGGING_LEVEL='FAILED'
   
   # Wall configuration
   WALL_CONFIG_PATH=config/wall_config.json
   
   MAX_HEIGHT=30
   
   ICE_PER_FOOT=195
   
   ICE_COST_PER_CUBIC_YARD=1900
   
   MAX_LENGTH=2000

   # Common
   API_VERSION='v1'

## Usage Instructions

### Start a Virtual Environment

# On Linux/Mac
```bash
# venv
python3 -m venv venv
source venv/bin/activate
# Poetry
poetry shell
```

# On Windows
```bash
python -m venv venv
.\venv\Scripts\activate

### Apply Migrations
python manage.py migrate

### Run the Server
python manage.py runserver

### Create an Admin User
python manage.py createsuperuser
```


### Accessing the API
- **Admin Interface:** `http://localhost:8000/admin/`
- **Daily Ice Usage Endpoint:** `http://localhost:8000/api/v1/daily-ice-usage/<profile_id>/<day>/`
- **Cost Overview Endpoints:**
  - `http://localhost:8000/api/v1/cost-overview/` -  pass the `num_crews` query parameter for multi-threaded construction simulation
  - `http://localhost:8000/api/v1/cost-overview/<profile_id>/`


## API Documentation

- **Schema:** `http://localhost:8000/api/v1/schema/`
- **Swagger UI:** `http://localhost:8000/api/v1/swagger-ui/`
- **ReDoc:** `http://localhost:8000/api/v1/redoc/`


## Testing
Run the full test suite:
```bash
python manage.py test

Run specific test modules:
python manage.py test <the_wall_api>.tests.<test_module>
# Example:
python manage.py test the_wall_api.tests.test_models
```


## Author

- **Aleksandar Dimitrov**
- [LinkedIn](https://www.linkedin.com/public-profile/settings?trk=d_flagship3_profile_self_view_public_profile)
- [Yahoo Email](mailto:sasho_1983@yahoo.com)
