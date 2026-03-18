import requests
import json
import hashlib
import time
import threading
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class LibreLinkUpAPI:
    """
    LibreLinkUp API Client with S3 integration for glucose monitoring
    Fetches glucose data every 1 minute and uploads to S3
    """

    def __init__(self, s3_client, s3_bucket, patient_id):
        """
        Initialize LibreLink API client

        Args:
            s3_client: Boto3 S3 client
            s3_bucket: S3 bucket name
            patient_id: Patient identifier
        """
        self.s3_client = s3_client
        self.s3_bucket = s3_bucket
        self.patient_id = patient_id

        self.base_url = "https://api.libreview.io"
        self.token = None
        self.account_id = None
        self.user_id = None
        self.is_authenticated = False
        self.monitoring_active = False
        self.monitoring_thread = None

        self.headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'product': 'llu.android',
            'version': '4.16.0'
        }

        self.latest_glucose = None
        self.all_readings = []
        self.seen_timestamps = set()

    def _get_auth_headers(self):
        """Get headers with authentication token"""
        headers = self.headers.copy()
        if self.token:
            headers['Authorization'] = f"Bearer {self.token}"
        if self.account_id:
            headers['Account-Id'] = self.account_id
        return headers

    def login(self, email, password):
        """
        Login to LibreLinkUp

        Returns:
            tuple: (success: bool, message: str)
        """
        login_url = f"{self.base_url}/llu/auth/login"
        login_data = {"email": email, "password": password}

        logger.info(f"🔐 Attempting LibreLink login for {email}...")

        try:
            response = requests.post(login_url, headers=self.headers, json=login_data, timeout=10)
            data = response.json()

            # Handle regional redirect
            if data.get("status") == 0 and data.get("data", {}).get("redirect"):
                region = data["data"].get("region")
                logger.info(f"🌍 Redirecting to region: {region}")
                self.base_url = f"https://api-{region}.libreview.io"
                login_url = f"{self.base_url}/llu/auth/login"
                response = requests.post(login_url, headers=self.headers, json=login_data, timeout=10)
                data = response.json()

            if data.get("status") == 0:
                self.token = data.get('data', {}).get('authTicket', {}).get('token')
                self.user_id = data.get('data', {}).get('user', {}).get('id')

                if self.user_id:
                    self.account_id = hashlib.sha256(self.user_id.encode('utf-8')).hexdigest().lower()

                if self.token and self.account_id:
                    self.is_authenticated = True
                    user = data.get('data', {}).get('user', {})
                    logger.info(f"✅ LibreLink login successful for {user.get('firstName')} {user.get('lastName')}")
                    return True, "LibreLink connected successfully!"
                else:
                    return False, "Login failed: Missing authentication data"
            else:
                error_msg = data.get('error', {}).get('message', 'Unknown error')
                logger.error(f"❌ LibreLink login failed: {error_msg}")
                return False, f"Login failed: {error_msg}"

        except requests.exceptions.Timeout:
            return False, "Login timeout - please check your internet connection"
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Network error during login: {e}")
            return False, f"Network error: {str(e)}"
        except Exception as e:
            logger.error(f"❌ Unexpected error during login: {e}")
            return False, f"Unexpected error: {str(e)}"

    def get_connections(self):
        """Get list of connected patients"""
        if not self.is_authenticated:
            return None

        url = f"{self.base_url}/llu/connections"
        headers = self._get_auth_headers()

        try:
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 429:
                logger.warning("⚠️ Rate limit hit")
                return None

            if response.status_code != 200:
                logger.error(f"❌ Failed to get connections: {response.status_code}")
                return None

            data = response.json()

            if data.get("status") == 0 and data.get("data"):
                connections = data["data"]
                logger.info(f"✅ Found {len(connections)} connection(s)")
                return connections
            return None

        except Exception as e:
            logger.error(f"❌ Error getting connections: {e}")
            return None

    def get_glucose_data(self, patient_id=None):
        """
        Get latest glucose data from LibreLink

        Returns:
            dict: Latest glucose reading or None
        """
        if not self.is_authenticated:
            logger.warning("⚠️ Not authenticated to LibreLink")
            return None

        connections = self.get_connections()
        if not connections:
            logger.warning("⚠️ No connections found")
            return None

        # Use first connection
        connection = connections[0]
        connection_patient_id = connection.get('patientId')

        url = f"{self.base_url}/llu/connections/{connection_patient_id}/graph"
        headers = self._get_auth_headers()

        try:
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 429:
                logger.warning("⚠️ Rate limit hit - waiting 60 seconds")
                time.sleep(60)
                return None

            if response.status_code != 200:
                logger.error(f"❌ Failed to get glucose: {response.status_code}")
                return None

            data = response.json()

            if data.get("status") == 0:
                conn = data["data"].get("connection", {})
                measurement = conn.get("glucoseMeasurement", {})

                if measurement:
                    timestamp = measurement.get("Timestamp")

                    # Check if this is a new reading (avoid duplicates)
                    if timestamp in self.seen_timestamps:
                        logger.info(f"⏭️  Skipping duplicate reading from {timestamp}")
                        return self.latest_glucose

                    # Mark as seen
                    self.seen_timestamps.add(timestamp)

                    glucose_reading = {
                        'patient_id': self.patient_id,
                        'value_mgdl': measurement.get("ValueInMgPerDl"),
                        'trend_arrow': measurement.get("TrendArrow"),
                        'is_high': measurement.get("isHigh", False),
                        'is_low': measurement.get("isLow", False),
                        'datetime': timestamp,
                        'timestamp': int(datetime.now().timestamp() * 1000)
                    }

                    self.latest_glucose = glucose_reading
                    self.all_readings.append(glucose_reading)

                    logger.info(f"📊 NEW Glucose: {glucose_reading['value_mgdl']} mg/dL | "
                                f"Trend: {self.get_trend_arrow_text(glucose_reading['trend_arrow'])} | "
                                f"Status: {'HIGH ⚠️' if glucose_reading['is_high'] else 'LOW ⚠️' if glucose_reading['is_low'] else 'NORMAL ✓'}")

                    # Upload to S3
                    self._upload_to_s3(glucose_reading)

                    return glucose_reading
                else:
                    logger.warning("⚠️ No glucose measurement in response")

        except Exception as e:
            logger.error(f"❌ Error fetching glucose: {e}")

        return None

    def _upload_to_s3(self, glucose_reading):
        """Upload glucose reading to S3"""
        if not self.s3_client:
            logger.warning("⚠️ S3 client not available")
            return

        try:
            year_month = datetime.now().strftime("%Y-%m")
            s3_key = f"{self.patient_id}/glucose/{year_month}.json"

            # Try to get existing data
            try:
                obj = self.s3_client.get_object(Bucket=self.s3_bucket, Key=s3_key)
                existing_data = json.loads(obj['Body'].read().decode('utf-8'))
            except self.s3_client.exceptions.NoSuchKey:
                existing_data = []
                logger.info(f"📝 Creating new glucose file: {s3_key}")

            # Check for duplicates before appending
            existing_timestamps = {reading.get('datetime') for reading in existing_data}
            if glucose_reading['datetime'] not in existing_timestamps:
                # Append new reading
                existing_data.append(glucose_reading)

                # Upload back to S3
                self.s3_client.put_object(
                    Bucket=self.s3_bucket,
                    Key=s3_key,
                    Body=json.dumps(existing_data, indent=2),
                    ContentType='application/json'
                )

                logger.info(f"✅ Uploaded glucose to S3: {s3_key} (Total: {len(existing_data)} readings)")
            else:
                logger.info(f"⏭️  Skipped duplicate S3 upload for {glucose_reading['datetime']}")

            # Update signal file to notify other components
            signal_data = {
                'timestamp': int(time.time() * 1000),
                'type': 'glucose_update',
                'patient_id': self.patient_id,
                'value': glucose_reading['value_mgdl'],
                'is_high': glucose_reading['is_high'],
                'is_low': glucose_reading['is_low']
            }

            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key='signal_file.txt',
                Body=json.dumps(signal_data),
                ContentType='application/json'
            )

        except Exception as e:
            logger.error(f"❌ Failed to upload to S3: {e}")

    def get_trend_arrow_text(self, arrow_code):
        """Convert trend arrow code to text"""
        arrows = {
            1: "↑↑ Rising Fast",
            2: "↑ Rising",
            3: "→ Stable",
            4: "↓ Falling",
            5: "↓↓ Falling Fast"
        }
        return arrows.get(arrow_code, "Unknown")

    def start_monitoring(self, poll_interval=60):
        """
        Start continuous glucose monitoring

        Args:
            poll_interval: Seconds between polls (default 60 = 1 minute)
        """
        if self.monitoring_active:
            logger.warning("⚠️ Monitoring already active")
            return

        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(poll_interval,),
            daemon=True
        )
        self.monitoring_thread.start()
        logger.info(f"🔄 Started glucose monitoring (every {poll_interval} seconds)")

    def stop_monitoring(self):
        """Stop glucose monitoring"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        logger.info("🛑 Stopped glucose monitoring")

    def _monitoring_loop(self, poll_interval):
        """
        Background monitoring loop - fetches glucose every poll_interval seconds
        """
        logger.info(f"🔁 Monitoring loop started (interval: {poll_interval}s)")
        iteration = 0

        while self.monitoring_active:
            try:
                iteration += 1

                if self.is_authenticated:
                    logger.info(f"🔄 [Poll #{iteration}] Fetching glucose from LibreLink...")
                    result = self.get_glucose_data()

                    if result is None:
                        logger.warning(f"⚠️ [Poll #{iteration}] No glucose data received")
                    elif result == self.latest_glucose:
                        logger.info(f"ℹ️  [Poll #{iteration}] No new data (same as last reading)")
                else:
                    logger.warning("⚠️ Not authenticated - skipping poll")

                # Wait for next poll
                time.sleep(poll_interval)

            except Exception as e:
                logger.error(f"❌ Monitoring error in poll #{iteration}: {e}")
                time.sleep(poll_interval)

        logger.info("🛑 Monitoring loop ended")

    def get_statistics(self):
        """Get statistics about glucose readings"""
        if not self.all_readings:
            return {
                'total_readings': 0,
                'average': 0,
                'min': 0,
                'max': 0,
                'high_count': 0,
                'low_count': 0
            }

        values = [r['value_mgdl'] for r in self.all_readings]
        return {
            'total_readings': len(self.all_readings),
            'average': sum(values) / len(values),
            'min': min(values),
            'max': max(values),
            'high_count': sum(1 for r in self.all_readings if r['is_high']),
            'low_count': sum(1 for r in self.all_readings if r['is_low']),
            'latest': self.latest_glucose
        }