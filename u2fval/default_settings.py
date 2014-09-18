# Database configuration string
DATABASE_CONFIGURATION = 'sqlite:///:memory:'

# If True, use memcached for storing registration and authentication requests
# in progress, instead of persisting them to the database.
USE_MEMCACHED = False

# If memcached is enabled, use thes servers.
MEMCACHED_SERVERS = ['127.0.0.1:11211']
