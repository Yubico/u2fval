# Database configuration string
DATABASE_CONFIGURATION = 'sqlite:///:memory:'

# If True, use memcached for storing registration and authentication requests
# in progress, instead of persisting them to the database.
USE_MEMCACHED = False

# If memcached is enabled, use thes servers.
MEMCACHED_SERVERS = ['127.0.0.1:11211']

# Add trusted CA certificates to the directory below, or add additional
# locations to the search path.
CA_CERTS = ['/etc/yubico/u2fval/cacerts/']

# Setting this to true will skip any attepts to verify the attestation
# certificates provided by device registrations. This will allow any type of
# U2F device to be registered against the server (including software based
# tokens).
DISABLE_ATTESTATION_VERIFICATION = False
