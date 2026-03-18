import os
from typing import Dict
from datetime import datetime


class MQTTConfig:
    """MQTT Configuration for AWS IoT Core"""

    # ✅ AWS IoT Core Settings
    MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "your-endpoint.iot.us-east-1.amazonaws.com")
    MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "8883"))  # ✅ TLS port
    MQTT_USERNAME = None  # ✅ Not used with AWS IoT (certificate-based auth)
    MQTT_PASSWORD = None  # ✅ Not used with AWS IoT
    MQTT_KEEP_ALIVE = 60

    # ✅ TLS/SSL Configuration for AWS IoT Core
    MQTT_USE_TLS = os.getenv("MQTT_USE_TLS", "true").lower() == "true"
    MQTT_CERT_PATH = os.getenv("MQTT_CERT_PATH", "/home/ec2-user/remoninew/certs/certificate.pem.crt")
    MQTT_KEY_PATH = os.getenv("MQTT_KEY_PATH", "/home/ec2-user/remoninew/certs/private.pem.key")
    MQTT_CA_PATH = os.getenv("MQTT_CA_PATH", "/home/ec2-user/remoninew/certs/AmazonRootCA1.pem")

    QOS_VITALS = 1
    QOS_ALERTS = 2
    QOS_STATUS = 0

    @staticmethod
    def get_broker_url() -> str:
        """Get broker URL with SSL prefix for AWS IoT"""
        return f"ssl://{MQTTConfig.MQTT_BROKER_HOST}:{MQTTConfig.MQTT_BROKER_PORT}"

    @staticmethod
    def get_vitals_topic(patient_id: str) -> str:
        return f"remoni/{patient_id}/vitals"

    @staticmethod
    def get_vitals_request_topic(patient_id: str) -> str:
        return f"remoni/{patient_id}/vitals/request"

    @staticmethod
    def get_vitals_response_topic(patient_id: str) -> str:
        return f"remoni/{patient_id}/vitals/response"

    @staticmethod
    def get_glucose_request_topic(patient_id: str) -> str:
        """Topic for web app to request immediate glucose fetch"""
        return f"remoni/{patient_id}/glucose/request"

    @staticmethod
    def get_glucose_response_topic(patient_id: str) -> str:
        """Topic for edge device to respond with fresh glucose"""
        return f"remoni/{patient_id}/glucose/response"

    @staticmethod
    def get_account_status_topic(patient_id: str) -> str:
        """Topic for notifying edge device about account changes"""
        return f"remoni/{patient_id}/account/status"

    @staticmethod
    def get_librelink_credentials_topic(patient_id: str) -> str:
        """Topic for sending LibreLink credentials from web app to edge device"""
        return f"remoni/{patient_id}/librelink/credentials"

    @staticmethod
    def get_fall_alert_topic(patient_id: str) -> str:
        """Get fall alert topic for immediate fall detection alerts"""
        return f"remoni/{patient_id}/alerts/fall"

    @staticmethod
    def get_emergency_alert_topic(patient_id: str) -> str:
        """Get emergency alert topic for immediate critical alerts"""
        return f"remoni/{patient_id}/alerts/emergency"

    @staticmethod
    def get_status_topic(patient_id: str) -> str:
        return f"remoni/{patient_id}/status"

    @staticmethod
    def create_status_message(patient_id: str, status: str, details: str = "") -> Dict:
        timestamp = int(datetime.now().timestamp() * 1000)
        return {
            "patient_id": patient_id,
            "device": "web_app",
            "status": status,
            "details": details,
            "timestamp": timestamp,
            "datetime": datetime.fromtimestamp(timestamp / 1000).strftime("%Y-%m-%d %H:%M:%S"),
            "type": "status"
        }

    @staticmethod
    def validate_patient_id(patient_id: str) -> bool:
        if not patient_id:
            return False
        return bool(patient_id.isdigit() and len(patient_id) == 5)
