"""
mqtt_client.py — Module ket noi MQTT Broker va boc tach du lieu theo dung Schema BTC.

Topics BTC:
  - hackathon/ae_mien_trung/test/telemetry
  - hackathon/ae_mien_trung/judge/telemetry

Payload Format BTC:
{
  "timestamp": "2026-07-18T07:30:01.000Z",
  "epoch": 1784369401,
  "environment": "HOME",
  "teamCode": "HOME_T1",
  "devices": [
    {
      "deviceCode": "AC_01",
      "status": "ok",
      "metrics": {
        "power": 1160.4,
        "temperature": 24.7
      }
    }
  ]
}
"""
import json
import os
import ssl
import time
import logging
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("MQTTClient")

load_dotenv()

BROKER = os.getenv("MQTT_BROKER", "mqtt-hackathon.lexatek.vn")
PORT = int(os.getenv("MQTT_PORT", 443))
TRANSPORT = os.getenv("MQTT_TRANSPORT", "websockets" if PORT == 443 else "tcp")
USE_TLS = os.getenv("MQTT_USE_TLS", "true").lower() in ("true", "1", "yes") or PORT == 443
WS_PATH = os.getenv("MQTT_WS_PATH", "/mqtt")

USERNAME = os.getenv("MQTT_USERNAME", "AE_MIEN_TRUNG")
PASSWORD = os.getenv("MQTT_PASSWORD", "mq_2fXRJxD_lAVgHEXTMF33JQ")
TEST_KEY = os.getenv("MQTT_TEST_KEY", "tk_CgukidjWBbI2A-ev1MZpCE2yLOBhwiR7")

# Standard Topics BTC
TOPIC_TEST = os.getenv("MQTT_TOPIC_TEST", "hackathon/ae_mien_trung/test/telemetry")
TOPIC_JUDGE = os.getenv("MQTT_TOPIC_JUDGE", "hackathon/ae_mien_trung/judge/telemetry")
TOPIC_WILDCARD = os.getenv("MQTT_TOPIC_WILDCARD", "hackathon/ae_mien_trung/#")

# ── Registry 6 thiet bi nông nghiệp Track B + thiet bi thu nghiem cua BTC ──
DEVICE_REGISTRY = {
    "SOIL_01": {"name": "Cảm biến đất khu A", "metrics": ["soil_moisture", "temperature"]},
    "WEATHER_01": {"name": "Trạm thời tiết", "metrics": ["temperature", "humidity"]},
    "PUMP_01": {"name": "Bơm tưới khu A", "metrics": ["flow_rate", "power"]},
    "PH_01": {"name": "Cảm biến pH bồn", "metrics": ["ph"]},
    "TANK_01": {"name": "Bồn nước chính", "metrics": ["level"]},
    "SUN_01": {"name": "Cảm biến nắng khu A", "metrics": ["lux"]},
    "AC_01": {"name": "Thiết bị điều hòa (Demo)", "metrics": ["power", "temperature"]},
}


import random

class MQTTHandler:
    def __init__(self, data_callback=None):
        self.data_callback = data_callback
        self.connected = False
        self.message_count = 0
        self.last_scenario = "NORMAL"

        client_id = f"AE_MIEN_TRUNG_{int(time.time())}_{random.randint(1000, 9999)}"

        if TRANSPORT == "websockets":
            self.client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2,
                client_id=client_id,
                transport="websockets"
            )
            self.client.ws_set_options(path=WS_PATH)
            logger.info(f"Using WebSockets transport (path={WS_PATH}, client_id={client_id})")
        else:
            self.client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2,
                client_id=client_id
            )

        if USE_TLS:
            try:
                self.client.tls_set()  # Standard CA TLS validation
                logger.info("TLS/SSL Enabled with standard CA certificate validation")
            except Exception as e:
                logger.warning(f"Standard TLS set failed, using fallback: {e}")
                self.client.tls_set(cert_reqs=ssl.CERT_NONE)
                self.client.tls_insecure_set(True)


        # Config Auth mode tu BTC Credentials
        if USERNAME:
            self.client.username_pw_set(USERNAME, PASSWORD)
            logger.info(f"Auth mode: Username/Password (user={USERNAME})")
        else:
            logger.info("Auth mode: Anonymous / Open Broker")

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        rc_value = rc.value if hasattr(rc, "value") else int(rc)
        if rc_value == 0:
            self.connected = True
            logger.info(f"✅ Connected to BTC MQTT Broker [{BROKER}:{PORT}] via {TRANSPORT.upper()}")
            # Subscribe 2 topics BTC va wildcard topic
            client.subscribe(TOPIC_TEST, qos=1)
            client.subscribe(TOPIC_JUDGE, qos=1)
            client.subscribe(TOPIC_WILDCARD, qos=1)
            logger.info(f"📡 Subscribed to topics: [{TOPIC_TEST}], [{TOPIC_JUDGE}]")
        else:
            self.connected = False
            logger.error(f"❌ Connection failed code={rc_value}")

    def _on_message(self, client, userdata, msg):
        """Boc tach JSON Payload tu BTC."""
        try:
            payload_str = msg.payload.decode("utf-8")
            data = json.loads(payload_str)
            self.message_count += 1

            if self.message_count <= 5 or self.message_count % 50 == 0:
                logger.info(f"📦 Payload #{self.message_count} [{msg.topic}]: {json.dumps(data, ensure_ascii=False)}")

            # 1. lay timestamp epoch
            sensor_time = data.get("epoch") or time.time()
            iso_time = data.get("timestamp")
            env = data.get("environment", "FARM")
            team_code = data.get("teamCode", "AE_MIEN_TRUNG")
            scenario = data.get("scenario", "NORMAL")
            self.last_scenario = scenario

            # 2. Xuly mang 'devices' tu payload BTC
            devices_list = data.get("devices", [])

            if isinstance(devices_list, list) and len(devices_list) > 0:
                for dev in devices_list:
                    device_code = (dev.get("deviceCode") or dev.get("device_code") or "UNKNOWN").upper()
                    metrics = dev.get("metrics", {})
                    status = dev.get("status", "ok")

                    telemetry = {
                        "device_code": device_code,
                        "timestamp": float(sensor_time),
                        "iso_timestamp": iso_time,
                        "status": status,
                        "metrics": metrics,
                        "environment": env,
                        "team_code": team_code,
                        "scenario": scenario,
                        "raw_topic": msg.topic,
                    }

                    if self.data_callback:
                        self.data_callback(telemetry)
            else:
                # Fallback cho payload 1 thiet bi don le
                device_code = (data.get("deviceCode") or data.get("device_code") or "UNKNOWN").upper()
                telemetry = {
                    "device_code": device_code,
                    "timestamp": float(sensor_time),
                    "iso_timestamp": iso_time,
                    "status": data.get("status", "ok"),
                    "metrics": data.get("metrics", {}),
                    "environment": env,
                    "team_code": team_code,
                    "scenario": scenario,
                    "raw_topic": msg.topic,
                }
                if self.data_callback:
                    self.data_callback(telemetry)

        except json.JSONDecodeError:
            logger.warning(f"Non-JSON payload on {msg.topic}: {msg.payload[:100]}")
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        self.connected = False
        rc_value = rc.value if hasattr(rc, "value") else int(rc)
        logger.warning(f"Unexpected disconnect (code={rc_value}). Reconnecting...")

    def start(self):
        logger.info(f"Connecting to MQTT Broker at {BROKER}:{PORT}...")
        try:
            self.client.connect(BROKER, PORT, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"Cannot connect to broker: {e}")
            self.client.connect_async(BROKER, PORT, keepalive=60)
            self.client.loop_start()

    def stop(self):
        logger.info("Stopping MQTT client...")
        self.client.loop_stop()
        self.client.disconnect()


if __name__ == "__main__":
    print("=" * 60)
    print("MQTT Client Listener — SEAL Hackathon (BTC Format Ready)")
    print(f"   Broker      : {BROKER}:{PORT}")
    print(f"   Topic Test  : {TOPIC_TEST}")
    print(f"   Topic Judge : {TOPIC_JUDGE}")
    print("=" * 60)

    received = []
    def print_telemetry(data):
        received.append(data)
        print(f"  [{len(received):>4}] Device={data['device_code']:<10s} Status={data['status']:<4s} Metrics={data['metrics']}")

    handler = MQTTHandler(data_callback=print_telemetry)
    handler.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        handler.stop()
