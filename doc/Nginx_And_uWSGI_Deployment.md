# Deploying u2fval with Nginx and uWSGI

To deploy u2fval in a microservices environment, you can use uWSGI as a robust application server and use nginx, which has uWSGI support built-in, as a proxy server.

Install uWSGI on the same server where you had `u2fval` installed beforehand, preferably with `pip install uwsgi`, and create the `/etc/uwsgi.ini` file:
```
[uwsgi]
master = true
processes = 4
socket = :8000
uid = nobody
buffer-size = 65535
module = u2fval
callable = app
```

uWSGI can be started in daemon mode:
```
uwsgi -d /etc/uwsgi.ini
```


In nginx, add the following server definition, replacing `server_name` by your own domain name and `u2fval_user` by the user that you had setup with `u2fval` previously.
```
server {
	listen 443;
	# ssl certificate configuration would go here
        server_name  yourauthserver.com;
        location /u2f {
                uwsgi_pass 127.0.0.1:8000;
                include uwsgi_params;
                uwsgi_param REMOTE_USER u2fval_user;
        }
}
```

You now can access your u2fval server at https://yourauthserver.com/u2f
