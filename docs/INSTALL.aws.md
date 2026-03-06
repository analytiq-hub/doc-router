# AWS Setup

Here are instructions on how to set up an AWS Lightsail instance and deploy the application.

* Create a new Lightsail instance with Ubuntu 24.04 LTS.
  * Recommended platform: `Linux/Unix`, `Ubuntu 24.04 LTS`, `2 vCPUs`, `4 GB Memory`, `60 GB SSDStorage`
    * A smaller instance would work, but be certain that the `docker compose` build will not run out of RAM memory.
    * I was able to use a `2GB RAM, 1GB Swap` instance, and the `docker compose` build step maxed out at about `2.5GB` of RAM max utilization
* Assign Lightsail instance a static IP
* Point `<mydomain>` to it (in my case, I point `doc-router.analytiq-hub.com` to it)
* Copy the SSH key to the instance.
* Connect to the instance using SSH.
* Clone the repository.
* Install `Docker`, `docker-compose` and `nginx`.
* Set up `nginx` to route `http://<mydomain>:80` requests to `http://localhost:3000` for the doc-router GUI, and to route `http://<mydomain>:8000` requests to `http://localhost:8000` for the FastAPI backend.
  * In my case, I create a file `/etc/nginx/sites-available/doc-router.conf` as follows:
  ```
  server {
  server_name app.docrouter.ai;
  client_max_body_size 100M;

  # API requests                                                                
  location /fastapi/ { # Note the trailing slash                                
      proxy_pass http://localhost:8000/; # The port of the FastAPI backend      
      proxy_http_version 1.1;
      proxy_set_header Upgrade $http_upgrade;
      proxy_set_header Connection 'upgrade';
      proxy_set_header Host $host;
      proxy_cache_bypass $http_upgrade;
  }

  location / {
      proxy_pass http://localhost:3000; # The port of the doc-router site       
      proxy_http_version 1.1;
      proxy_set_header Upgrade $http_upgrade;
      proxy_set_header Connection 'upgrade';
      proxy_set_header Host $host;
      proxy_cache_bypass $http_upgrade;
  }

    listen 443 ssl; # managed by Certbot                                        
    ssl_certificate /etc/letsencrypt/live/doc-router.analytiq-hub.com/fullchain.\
pem; # managed by Certbot                                                       
    ssl_certificate_key /etc/letsencrypt/live/doc-router.analytiq-hub.com/privke\
y.pem; # managed by Certbot                                                     
    include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot       
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; # managed by Certbot         



}

server {                                                   
    if ($host = app.docrouter.ai) {
        return 301 https://$host$request_uri;
    } # managed by Certbot                                                      


  listen 80;
  server_name doc-router.analytiq-hub.com app.docrouter.ai;
  return 404; # managed by Certbot                                            
}

  ```
  * I linked the file to the `sites-enabled` directory, and enabled the service:
    ```bash
    sudo ln -s /etc/nginx/sites-available/doc-router.conf /etc/nginx/sites-enabled/
    ```
  * Obtain SSL certificates for the doc-router and the API, in my case:
    ```bash
    sudo certbot --nginx -d doc-router.analytiq-hub.com
    ```
  * Enable and start the `nginx` service:
    ```bash
    sudo systemctl enable nginx
    sudo systemctl start nginx
    ```

* Create a `.env` file at the root based on `.env.example.aws_lightsail`
* Set up an external MongoDB database and update the `MONGODB_URI` environment variable in the `.env` file.
* Run the application with Docker Compose.
  ```bash
  DOCKER_BUILDKIT=1 docker compose up --build --detach
  ```
