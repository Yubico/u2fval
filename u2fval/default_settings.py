# Database configuration string
DATABASE_CONFIGURATION = 'sqlite:///:memory:'

# If True, use memcached for storing registration and authentication requests
# in progress, instead of persisting them to the database.
USE_MEMCACHED = False

# If memcached is enabled, use these servers.
MEMCACHED_SERVERS = ['127.0.0.1:11211']

# Add files containing trusted metadata JSON to the directory below.
METADATA = '/etc/yubico/u2fval/metadata/'

# Allow the use of untrusted (for which attestation cannot be verified using
# the available trusted metadata) U2F devices.
ALLOW_UNTRUSTED = False
