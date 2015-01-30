# Database configuration string
DATABASE_CONFIGURATION = 'sqlite:///:memory:'

# If True, use memcached for storing registration and authentication requests
# in progress, instead of persisting them to the database.
USE_MEMCACHED = False

# If memcached is enabled, use thes servers.
MEMCACHED_SERVERS = ['127.0.0.1:11211']

# Add files containing trusted metadata JSON to the directory below.
METADATA = '/etc/yubico/u2fval/metadata/'

# Setting this to True will skip any attepts to verify the attestation
# certificates provided by device registrations. This will allow any type of
# U2F device to be registered against the server (including software based
# tokens).
DISABLE_ATTESTATION_VERIFICATION = False
