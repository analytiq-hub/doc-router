# Local Development Setup

## Linux
* MongoDB setup
  * [Install MongoDB](https://medium.com/@nkav2447/how-to-download-and-install-mongodb-on-fedora-40-2db148a7c2f0)
  * [Install MongoDB Compass](https://www.mongodb.com/try/download/compass)
  * Create a `dev` database
* Create a `packages/analytiq-data/.env` file, taking [.env.example](../packages/analytiq_data/.env.example) as a template
  * For production, point MONGODB_URI to your production MongoDB server, and set ENV to `prod`.
* Create `venv` for doc-router, install `packages/requirements.txt`
  * During setup
  ```bash
  mkdir ~/.venv
  python -m venv ~/.venv/doc-router
  . ~/.venv/doc-router/bin/activate
  pip install -r packages/requirements.txt
  ```
* Install `NodeJS` and `npm`
* Install the frontend
  ```bash
  cd frontend
  npm install
  ```
* Set up the `frontend/.env.local` file, taking [.env.example](../frontend/.env.example) as a template

### Using `start-all.sh`
* Cd to the top of the project directory, and run `./start-all.sh`

### Manually starting each process
* Open three terminals
* In the two terminals you will run the fastapi and worker, activate the virtual environment: `. ~/.venv/doc-router/bin/activate`
* Start the back end
  ```bash
  cd packages
  uvicorn docrouter_app.main:app --host 0.0.0.0 --port 8000
  ```
* In a separate shell, start the workers
  ```bash
  cd packages/workers
  python worker.py
  ```
* Open [http://localhost:8000/docs](http://localhost:8000/docs) to experiment with the FastAPI

* Start the front end
  ```bash
  npm run dev
  ```

## Macbook
Under construction.
* MongoDB setup
  * [Install MongoDB](https://www.mongodb.com/docs/manual/tutorial/install-mongodb-on-os-x/)
  * [Install MongoDB Compass](https://www.mongodb.com/try/download/compass)
  * Create a `dev` database
* Backend and venv
  * Install python 3.11 - 3.12 and use it to create the venv
    * `brew install python@3.11`
    * `mkdir ~/.venv`
    * `python3.11 -m venv ~/.venv/doc-router`
    * `. ~/.venv/doc-router/bin/activate`
    * `pip install -r packages/requirements.txt`
  * The rest is the same as for Linux
* Frontend
  * Same as for Linux

## Changing log levels
* The default log level is `INFO`.
* To change the log level, set the `LOG_LEVEL` environment variable to the desired level.
  * `export LOG_LEVEL=DEBUG`
* The log level can only be set in the environment, not in the `.env` file.
