#!/usr/bin/env python3
"""
ClickHouse Connection Diagnostic Tool

Tests various connection configurations to identify the correct credentials.
"""

import sys
import os

# Try to import clickhouse-driver
try:
    from clickhouse_driver import Client
    print("✓ clickhouse-driver installed")
except ImportError:
    print("✗ clickhouse-driver not installed")
    print("  Install: pip install clickhouse-driver")
    sys.exit(1)


def test_connection(host, port, user, password, database='default'):
    """Test a ClickHouse connection configuration."""
    try:
        client = Client(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            connect_timeout=5,
            send_receive_timeout=10
        )

        # Try simple query
        result = client.execute("SELECT 1")

        # Try to list tables
        tables = client.execute("SHOW TABLES")

        # Try to check forex table
        try:
            count = client.execute("SELECT COUNT(*) FROM forex LIMIT 1")
            forex_exists = True
            forex_count = count[0][0]
        except:
            forex_exists = False
            forex_count = 0

        return {
            'success': True,
            'result': result,
            'tables_count': len(tables),
            'forex_exists': forex_exists,
            'forex_count': forex_count,
            'error': None
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)[:200]
        }


def main():
    """Run diagnostic tests."""
    print("="*60)
    print("ClickHouse Connection Diagnostic Tool")
    print("="*60)
    print()

    # Test configurations to try
    configs = [
        {
            'name': 'Config 1: nona_server_06 default',
            'host': '111.220.88.138',
            'port': 19999,
            'user': 'webss',
            'password': '',
            'database': 'default'
        },
        {
            'name': 'Config 2: With CLICKHOUSE_PASSWORD env var',
            'host': '111.220.88.138',
            'port': 19999,
            'user': 'webss',
            'password': os.environ.get('CLICKHOUSE_PASSWORD', ''),
            'database': 'default'
        },
        {
            'name': 'Config 3: default user with env password',
            'host': '111.220.88.138',
            'port': 19999,
            'user': 'default',
            'password': os.environ.get('CLICKHOUSE_PASSWORD', ''),
            'database': 'default'
        },
        {
            'name': 'Config 4: Local host (192.168.1.110)',
            'host': '192.168.1.110',
            'port': 19999,
            'user': 'webss',
            'password': os.environ.get('CLICKHOUSE_PASSWORD', ''),
            'database': 'default'
        },
        {
            'name': 'Config 5: localhost',
            'host': 'localhost',
            'port': 19999,
            'user': 'webss',
            'password': '',
            'database': 'default'
        },
    ]

    # Test each configuration
    for i, config in enumerate(configs, 1):
        config_name = config.pop('name')  # Remove 'name' before passing to test_connection
        print(f"\nTest {i}: {config_name}")
        print("-" * 60)
        print(f"Host:     {config['host']}")
        print(f"Port:     {config['port']}")
        print(f"User:     {config['user']}")
        print(f"Password: {'<empty>' if not config['password'] else '<set> (' + config['password'][:5] + '...)'}")
        print(f"Database: {config['database']}")
        print()

        result = test_connection(**config)

        if result['success']:
            print("✓ CONNECTION SUCCESSFUL!")
            print(f"  - Query result: {result['result']}")
            print(f"  - Tables found: {result['tables_count']}")
            print(f"  - Forex table: {'✓ Exists' if result['forex_exists'] else '✗ Not found'}")
            if result['forex_exists']:
                print(f"  - Forex records: {result['forex_count']:,}")
            print()
            print("=" * 60)
            print("SUCCESS! Use this configuration:")
            print("=" * 60)
            print(f"DATA_API_CLICKHOUSE_HOST={config['host']}")
            print(f"DATA_API_CLICKHOUSE_PORT={config['port']}")
            print(f"DATA_API_CLICKHOUSE_USER={config['user']}")
            print(f"DATA_API_CLICKHOUSE_PASSWORD={config['password']}")
            print(f"DATA_API_CLICKHOUSE_DATABASE={config['database']}")
            print("=" * 60)
            return 0
        else:
            print(f"✗ FAILED: {result['error']}")

    print()
    print("=" * 60)
    print("All connection attempts failed")
    print("=" * 60)
    print()
    print("Possible issues:")
    print("1. ClickHouse server is not accessible from this host")
    print("2. Incorrect credentials")
    print("3. Network/firewall blocking connection")
    print("4. ClickHouse server is down")
    print()
    print("Next steps:")
    print("1. Verify ClickHouse server is running:")
    print("   netstat -tuln | grep 19999")
    print()
    print("2. Test network connectivity:")
    print("   telnet 111.220.88.138 19999")
    print()
    print("3. Check if nona_server_06 can connect:")
    print("   docker exec nona_server_06 python3 -c \"")
    print("   from src.db.clickhouse_connection_unified import ClickHouseConnectionManager;")
    print("   print(ClickHouseConnectionManager().execute_query('SELECT 1'))\"")
    print()

    return 1


if __name__ == "__main__":
    sys.exit(main())
