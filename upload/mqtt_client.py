# mqtt_client.py for Web App

import paho.mqtt.client as mqtt
import json
import logging
from typing import Callable, Dict, Optional
from mqtt_config import MQTTConfig

logger = logging.getLogger(__name__)


class MQTTClient:
    """MQTT Client for Web App to communicate with Edge Device via AWS IoT Core"""

    def __init__(self, client_id: str, patient_id: str, broker_url: Optional[str] = None):
        self.client_id = client_id
        self.patient_id = patient_id
        self.broker_url = broker_url or MQTTConfig.get_broker_url()

        # ✅ Support both paho-mqtt 1.x and 2.x
        if hasattr(mqtt, "CallbackAPIVersion"):
            self.client = mqtt.Client(
                client_id=self.client_id,
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2
            )
        else:
            self.client = mqtt.Client(client_id=self.client_id)

        self.is_connected = False
        self.message_handlers = {}

        # Set callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        # ✅ Configure TLS for AWS IoT Core
        if MQTTConfig.MQTT_USE_TLS:
            import ssl
            try:
                self.client.tls_set(
                    ca_certs=MQTTConfig.MQTT_CA_PATH,
                    certfile=MQTTConfig.MQTT_CERT_PATH,
                    keyfile=MQTTConfig.MQTT_KEY_PATH,
                    cert_reqs=ssl.CERT_REQUIRED,
                    tls_version=ssl.PROTOCOL_TLSv1_2
                )
                logger.info("✅ TLS configured for AWS IoT Core")
            except Exception as e:
                logger.error(f"❌ TLS configuration failed: {e}")
                raise

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """✅ Callback when connected to broker (VERSION2 signature)"""
        if rc == 0:
            self.is_connected = True
            logger.info(f"✅ MQTT Connected to {self.broker_url}")
        else:
            self.is_connected = False
            logger.error(f"❌ MQTT Connection failed with code: {rc}")

    def _on_disconnect(self, client, userdata, rc, properties=None):
        """✅ Callback when disconnected from broker (VERSION2 signature)"""
        self.is_connected = False
        if rc != 0:
            logger.warning(f"⚠️ MQTT Unexpected disconnect. Code: {rc}")
        else:
            logger.info("MQTT Disconnected")

    def _on_message(self, client, userdata, msg):
        """Callback when message received"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode('utf-8'))

            logger.info(f"📨 MQTT Message received on topic: {topic}")

            # Call registered handler for this topic
            if topic in self.message_handlers:
                self.message_handlers[topic](topic, payload)
                return

            # Support wildcard handlers (#, +)
            for pattern, handler in self.message_handlers.items():
                if '#' in pattern or '+' in pattern:
                    try:
                        if mqtt.topic_matches_sub(pattern, topic):
                            handler(topic, payload)
                            return
                    except Exception:
                        continue

        except Exception as e:
            logger.error(f"❌ Error handling MQTT message: {e}")

    def connect(self) -> bool:
        """Connect to MQTT broker (AWS IoT Core)"""
        try:
            # ✅ Parse broker URL (supports both tcp:// and ssl://)
            if self.broker_url.startswith("ssl://"):
                broker_host = self.broker_url.replace("ssl://", "").split(":")[0]
                broker_port = int(
                    self.broker_url.replace("ssl://", "").split(":")[1]) if ":" in self.broker_url.replace("ssl://",
                                                                                                           "") else MQTTConfig.MQTT_BROKER_PORT
            elif self.broker_url.startswith("tcp://"):
                broker_host = self.broker_url.replace("tcp://", "").split(":")[0]
                broker_port = int(
                    self.broker_url.replace("tcp://", "").split(":")[1]) if ":" in self.broker_url.replace("tcp://",
                                                                                                           "") else MQTTConfig.MQTT_BROKER_PORT
            else:
                broker_host = self.broker_url
                broker_port = MQTTConfig.MQTT_BROKER_PORT

            logger.info(f"🔌 Connecting to MQTT broker: {broker_host}:{broker_port}")

            # ✅ AWS IoT Core uses certificate-based auth (no username/password)
            # Connect
            self.client.connect(broker_host, broker_port, MQTTConfig.MQTT_KEEP_ALIVE)

            # Start network loop in background
            self.client.loop_start()

            # Wait a moment for connection
            import time
            time.sleep(3)  # ✅ Slightly longer wait for TLS handshake

            return self.is_connected

        except Exception as e:
            logger.error(f"❌ MQTT Connection error: {e}")
            return False

    def disconnect(self):
        """Disconnect from MQTT broker"""
        try:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("MQTT Disconnected")
        except Exception as e:
            logger.error(f"❌ Error disconnecting MQTT: {e}")

    def subscribe(self, topic: str, handler: Callable[[str, Dict], None]):
        """Subscribe to a topic with a handler function"""
        try:
            self.message_handlers[topic] = handler
            self.client.subscribe(topic, qos=MQTTConfig.QOS_VITALS)
            logger.info(f"✅ Subscribed to MQTT topic: {topic}")
            return True
        except Exception as e:
            logger.error(f"❌ Error subscribing to {topic}: {e}")
            return False

    def publish(self, topic: str, payload: Dict, qos: int = None) -> bool:
        """Publish a message to a topic"""
        try:
            if not self.is_connected:
                logger.warning("⚠️ Cannot publish - MQTT not connected")
                return False

            if qos is None:
                qos = MQTTConfig.QOS_VITALS

            message = json.dumps(payload)
            result = self.client.publish(topic, message, qos=qos)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"✅ Published to MQTT topic: {topic}")
                return True
            else:
                logger.error(f"❌ Failed to publish to {topic}")
                return False

        except Exception as e:
            logger.error(f"❌ Error publishing to {topic}: {e}")
            return False

    def publish_vitals_request(self, request_payload: Dict) -> bool:
        """Publish vitals request to edge device"""
        topic = MQTTConfig.get_vitals_request_topic(self.patient_id)
        return self.publish(topic, request_payload)

    def publish_glucose_request(self, request_payload: Dict) -> bool:
        """Publish glucose request to edge device"""
        topic = MQTTConfig.get_glucose_request_topic(self.patient_id)
        return self.publish(topic, request_payload)

    def publish_librelink_credentials(self, credentials: Dict) -> bool:
        """Publish LibreLink credentials to edge device"""
        topic = MQTTConfig.get_librelink_credentials_topic(self.patient_id)
        return self.publish(topic, credentials)

    def publish_account_status(self, status_payload: Dict) -> bool:
        """Publish account status notification to edge device"""
        topic = MQTTConfig.get_account_status_topic(self.patient_id)
        return self.publish(topic, status_payload)

    def publish_status(self, status: str, details: str = "") -> bool:
        """Publish status update"""
        topic = MQTTConfig.get_status_topic(self.patient_id)
        payload = MQTTConfig.create_status_message(
            patient_id=self.patient_id,
            status=status,
            details=details
        )
        return self.publish(topic, payload)
