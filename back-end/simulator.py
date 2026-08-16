"""
simulator.py — Gia lap phat du lieu CHUAN CHINH XAC THEO FORMAT BTC.

Format BTC JSON:
{
  "timestamp": "2026-07-18T07:30:01.000Z",
  "epoch": 1784369401,
  "environment": "HOME",
  "teamCode": "HOME_T1",
  "devices": [
    {
      "deviceCode": "AC_01",
      "status": "ok",
      "metrics": { "power": 1160.4, "temperature": 24.7 }
    }
  ]
}

Chay:
  1. Direct buffer: python simulator.py --mode buffer
  2. MQTT publish:  python simulator.py --mode mqtt
"""
import time
import math
import random
import logging
import argparse
import datetime
import json

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
logger = logging.getLogger("Simulator")


class BTCFarmSimulator:
    def __init__(self, scenario: str = "normal"):
        self.scenario = scenario
        self.start_time = time.time()
        self.tick = 0

    def generate_btc_payload(self) -> dict:
        """Tao 1 goi tin payload tong hop mang 'devices' theo dung chuan BTC."""
        self.tick += 1
        now = time.time()
        now_dt = datetime.datetime.fromtimestamp(now, datetime.timezone.utc)
        elapsed = now - self.start_time

        devices = []

        # 1. SOIL_01
        soil_m = max(15, 50 - elapsed * 0.1) if self.scenario == "dry_soil" else 45 + 5 * math.sin(elapsed / 100)
        devices.append({
            "deviceCode": "SOIL_01",
            "status": "ok",
            "metrics": {
                "soil_moisture": round(soil_m + random.gauss(0, 1), 1),
                "temperature": round(27.5 + random.gauss(0, 0.5), 1)
            }
        })

        # 2. WEATHER_01
        devices.append({
            "deviceCode": "WEATHER_01",
            "status": "ok",
            "metrics": {
                "temperature": round(31.0 + random.gauss(0, 1), 1),
                "humidity": round(68.0 + random.gauss(0, 2), 1)
            }
        })

        # 3. PUMP_01
        pump_flow = 0.0 if (self.scenario == "pump_failure" and elapsed > 60) else 16.5
        pump_power = 0.0 if pump_flow == 0 else 240.0
        devices.append({
            "deviceCode": "PUMP_01",
            "status": "ok" if pump_flow > 0 or self.scenario != "pump_failure" else "error",
            "metrics": {
                "flow_rate": round(pump_flow + random.gauss(0, 0.5), 1),
                "power": round(pump_power + random.gauss(0, 5), 1)
            }
        })

        # 4. PH_01
        devices.append({
            "deviceCode": "PH_01",
            "status": "ok",
            "metrics": { "ph": round(6.5 + random.gauss(0, 0.1), 2) }
        })

        # 5. TANK_01
        tank_lvl = max(10, 85.0 - elapsed * 0.05)
        devices.append({
            "deviceCode": "TANK_01",
            "status": "ok",
            "metrics": { "level": round(tank_lvl, 1) }
        })

        # 6. SUN_01
        devices.append({
            "deviceCode": "SUN_01",
            "status": "ok",
            "metrics": { "lux": round(42000 + random.gauss(0, 2000), 0) }
        })

        return {
            "timestamp": now_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "epoch": int(now),
            "environment": "SMART_FARM_ZONE_A",
            "teamCode": "AE_MIEN_TRUNG",
            "devices": devices
        }


def run_buffer_mode(duration: int = 300, interval: float = 2.0):
    """Bom thang vao pipeline (state -> ML -> Agent), khong qua broker."""
    from app.pipeline import on_reading

    sim = BTCFarmSimulator(scenario="normal")
    print("=" * 60)
    print("BTC Payload Simulator Running (Direct Buffer Stream)")
    print("=" * 60)

    start = time.time()
    msg_count = 0
    try:
        while time.time() - start < duration:
            payload = sim.generate_btc_payload()
            msg_count += 1

            epoch = float(payload["epoch"])
            for dev in payload["devices"]:
                on_reading(
                    dev["deviceCode"].upper(),
                    dev.get("metrics", {}),
                    event_time=epoch,
                    meta={"source": "simulator.py", "scenario": payload.get("scenario", "NORMAL")},
                )

            print(f"  [{int(time.time() - start):>3d}s] Emitted BTC Payload #{msg_count} with {len(payload['devices'])} devices")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nSimulator stopped.")


def run_mqtt_mode(duration: int = 300, interval: float = 2.0):
    """Publish goi tin BTC qua MQTT Broker thuc te."""
    import paho.mqtt.client as mqtt

    # Doc cung mot nguon cau hinh voi backend — khong tu dat default broker rieng,
    # neu khong se publish len mot broker khac voi cai backend dang subscribe.
    from app.config import (
        MQTT_BROKER_HOST as broker,
        MQTT_BROKER_PORT as port,
        MQTT_PASSWORD,
        MQTT_TOPIC_TEST as topic,
        MQTT_TRANSPORT,
        MQTT_USE_TLS,
        MQTT_USERNAME,
        MQTT_WS_PATH,
    )

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"Publisher_{int(time.time())}",
        transport=MQTT_TRANSPORT,
    )
    if MQTT_TRANSPORT == "websockets" and MQTT_WS_PATH:
        client.ws_set_options(path=MQTT_WS_PATH)
    if MQTT_USE_TLS:
        client.tls_set()
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.connect(broker, port, keepalive=60)
    client.loop_start()

    sim = BTCFarmSimulator(scenario="normal")
    print("=" * 60)
    print(f"Publishing BTC Payload over MQTT to [{broker}:{port}]")
    print(f"Topic: {topic}")
    print("=" * 60)

    start = time.time()
    msg_count = 0
    try:
        while time.time() - start < duration:
            payload = sim.generate_btc_payload()
            msg_count += 1
            client.publish(topic, json.dumps(payload), qos=1)
            print(f"  [{int(time.time() - start):>3d}s] Published MQTT Payload #{msg_count} to [{topic}]")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nPublisher stopped.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BTC Payload Format Simulator")
    parser.add_argument("--mode", choices=["buffer", "mqtt"], default="buffer", help="buffer=direct stream, mqtt=publish over MQTT")
    parser.add_argument("--duration", type=int, default=300, help="Duration in seconds")
    parser.add_argument("--interval", type=float, default=2.0, help="Interval in seconds")
    args = parser.parse_args()

    if args.mode == "mqtt":
        run_mqtt_mode(duration=args.duration, interval=args.interval)
    else:
        run_buffer_mode(duration=args.duration, interval=args.interval)
