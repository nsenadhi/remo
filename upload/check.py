#!/usr/bin/env python3
"""Test AWS IoT MQTT Connection"""

import os
from dotenv import load_dotenv
from mqtt_client import MQTTClient
from mqtt_config import MQTTConfig
import time

load_dotenv()


def test_connection():
    print("🧪 Testing AWS IoT MQTT Connection...")
    print(f"📡 Broker: {MQTTConfig.MQTT_BROKER_HOST}")
    print(f"🔐 TLS Enabled: {MQTTConfig.MQTT_USE_TLS}")
    print(f"📁 Certificate: {MQTTConfig.MQTT_CERT_PATH}")

    # Create client
    client = MQTTClient(
        client_id="test_web_app",
        patient_id="00001"
    )

    # Try to connect
    if client.connect():
        print("✅ Successfully connected to AWS IoT Core!")
        print("⏳ Waiting 5 seconds...")
        time.sleep(5)

        # Disconnect
        client.disconnect()
        print("✅ Disconnected successfully")
        return True
    else:
        print("❌ Failed to connect to AWS IoT Core")
        print("\n🔍 Troubleshooting:")
        print("1. Check your AWS IoT endpoint in .env")
        print("2. Verify certificates are in ./certs/ directory")
        print("3. Ensure certificate has correct permissions (chmod 600)")
        print("4. Check if IoT policy is attached to certificate")
        return False


if __name__ == "__main__":
    test_connection()