# ClickHouse Authentication Issue - Diagnostic Report

**Date**: 2025-10-30
**Status**: ⚠️ **BLOCKED** - Cannot authenticate to ClickHouse server

---

## Problem Summary

The Data API service cannot connect to the ClickHouse server at `111.220.88.138:19999` (or `localhost:19999`). All authentication attempts have failed with error:

```
Code: 516. DB::Exception: webss: Authentication failed:
password is incorrect, or there is no user with such name
```

---

## What We've Tested

### Configurations Tested ❌

All of the following configurations **FAILED**:

1. **Host: `111.220.88.138`, User: `webss`, Password: ``** (empty)
2. **Host: `111.220.88.138`, User: `webss`, Password: `3zSg!Lqnmm6780Q78/!F`** (from env)
3. **Host: `111.220.88.138`, User: `default`, Password: `3zSg!Lqnmm6780Q78/!F`**
4. **Host: `192.168.1.110`, User: `webss`, Password: `3zSg!Lqnmm6780Q78/!F`**
5. **Host: `localhost`, User: `webss`, Password: ``** (empty)
6. **Host: `localhost`, User: `webss`, Password: `webss`**
7. **Host: `localhost`, User: `default`, Password: ``** (empty)

### What We Know ✅

1. **ClickHouse server is running**:
   ```bash
   ps aux | grep clickhouse
   # Process found: /usr/bin/clickhouse-server --config=/etc/clickhouse-server/config.xml
   ```

2. **Port 19999 is listening**:
   ```bash
   netstat -tuln | grep 19999
   # tcp  0  0 0.0.0.0:19999  0.0.0.0:*  LISTEN
   ```

3. **Network connectivity works** (telnet connects successfully)

4. **nona_server_06 config shows**:
   ```python
   CLICKHOUSE_HOST = "111.220.88.138"
   CLICKHOUSE_PORT = 19999
   CLICKHOUSE_USER = "webss"
   CLICKHOUSE_PASSWORD = "webss"  # But this doesn't work!
   ```

---

## Possible Root Causes

### 1. User Doesn't Exist
The user `webss` may not exist in the ClickHouse server's user database.

**To check** (requires ClickHouse admin access):
```bash
clickhouse-client --query "SELECT name FROM system.users"
```

### 2. Password is Different
The actual password might be different from what's in the config or environment variables.

### 3. IP-Based Access Control
ClickHouse might have IP-based access restrictions that block connections from this host.

**To check** (requires ClickHouse admin access):
```bash
# Check users.xml or users.d/*.xml for <networks> configuration
cat /etc/clickhouse-server/users.xml | grep -A10 "networks"
```

### 4. Configuration Mismatch
The nona_server_06 might be using a different connection method (SSH tunnel, proxy, etc.) that we're not aware of.

---

## How to Resolve

### Option 1: Get Correct Credentials from System Admin

Contact the ClickHouse system administrator to verify:
- What users exist in the database
- What the correct password is for the `webss` user
- Whether IP-based access control is configured
- Whether there are any special authentication requirements

### Option 2: Check ClickHouse Configuration Files

If you have root/sudo access:

```bash
# Check default password
sudo cat /etc/clickhouse-server/users.d/default-password.xml

# Check user configuration
sudo cat /etc/clickhouse-server/users.xml

# Check for custom user definitions
sudo ls -la /etc/clickhouse-server/users.d/
sudo cat /etc/clickhouse-server/users.d/*.xml
```

### Option 3: Reset ClickHouse Password

If you have root access and can restart ClickHouse:

```bash
# Delete the password file to reset to no password
sudo rm /etc/clickhouse-server/users.d/default-password.xml

# Restart ClickHouse
sudo systemctl restart clickhouse-server

# Try connecting with default user and no password
```

### Option 4: Investigate nona_server_06 Connection Method

Check if nona_server_06 uses a different connection approach:

```bash
# Check if it uses SSH tunneling
docker exec nona_server_06 ps aux | grep ssh

# Check if it uses a proxy
docker exec nona_server_06 env | grep -i proxy

# Check network connections from the container
docker exec nona_server_06 netstat -tnp
```

### Option 5: Create New User

If you have ClickHouse admin access:

```sql
-- Connect as admin
clickhouse-client

-- Create new user
CREATE USER webss IDENTIFIED WITH plaintext_password BY 'your_password';

-- Grant permissions
GRANT ALL ON *.* TO webss;
```

---

## Immediate Workaround

While authentication is being resolved, you can test the API with **mock data mode** (once implemented):

```bash
# This would allow testing the API endpoints without database access
export DATA_API_MOCK_MODE=true
docker-compose restart
```

Or use the client with `skip_db_check`:

```python
from examples.ds_request_clickhouse import predict_with_real_data

# This will skip database check and use mock data
prediction = predict_with_real_data(
    symbol="EURUSD",
    skip_db_check=True,
    verbose=True
)
```

---

## Service Status

The Data API service is **fully implemented and running**, but cannot serve real data until ClickHouse authentication is resolved:

- ✅ Service running on port 8001
- ✅ API documentation available at http://localhost:8001/docs
- ✅ Health check endpoint responds: `{"status": "degraded", "database_connected": false}`
- ❌ Cannot query K-line data (authentication failure)
- ❌ Complete prediction workflow blocked

---

## Diagnostic Tool

A comprehensive diagnostic tool has been created to test various configurations:

```bash
cd /data/ws/kronos/services/data_api
source ~/.bashrc  # Load CLICKHOUSE_PASSWORD
python3 diagnose.py
```

This tool will:
- Test 5 different connection configurations
- Print detailed error messages
- Suggest next troubleshooting steps

---

## Next Steps

1. **Immediate**: Contact system admin to verify correct ClickHouse credentials
2. **Alternative**: Check if you have sudo access to inspect ClickHouse config files
3. **Last Resort**: Consider setting up a new ClickHouse instance with known credentials

Once correct credentials are obtained:
1. Update `/data/ws/kronos/services/data_api/.env`
2. Restart service: `docker-compose down && docker-compose up -d`
3. Verify health check: `curl http://localhost:8001/v1/healthz`
4. Test complete workflow: `python ds_request_clickhouse.py`

---

**Updated**: 2025-10-30
**Diagnostic Tool**: `/data/ws/kronos/services/data_api/diagnose.py`
**Service Status**: Waiting for authentication resolution
