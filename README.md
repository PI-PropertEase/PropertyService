# PropertyService
Microservice responsible for storing and providing all information relative to a property.

#### Build Image
```bash
sudo docker build -t my-mongo-db ./ ;
```

#### Run Image
```bash
sudo docker run -d --name my-mongo-container -p 27017:27017 my-mongo-db ;
```

#### PSQL (Postgres Command Line Interface)
```bash
sudo docker exec -it container_number /bin/bash ;
mongosh;
```

#### Pre-requirements
```bash
sudo apt-get install libpq-dev python-dev
```


#### Setup venv
```bash
python -m venv venv;
source venv/bin/activate;
pip install -r requirements;
```

#### Run FastAPI
```bash
source venv/bin/activate;
uvicorn PropertyService.main:app --reload;
```


