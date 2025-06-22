import time
import json
import paho.mqtt.client as paho
from paho import mqtt
import random
import string

# --- Callbacks ---
# These functions will be called by the MQTT client when specific events happen.

def on_connect(client, userdata, flags, rc, properties=None):
    """Prints the result of the connection attempt."""
    print(f"CONNACK received with code {rc}.")
    if rc == 0:
        print("Connected successfully to HiveMQ Cloud!")
    else:
        print(f"Failed to connect, return code {rc}\n")

def on_publish(client, userdata, mid, properties=None):
    """Prints the MID (Message ID) of the successfully published message."""
    print("mid: " + str(mid))

def on_subscribe(client, userdata, mid, granted_qos, properties=None):
    """Prints the MID of the subscription request."""
    print("Subscribed: " + str(mid) + " " + str(granted_qos))

# --- Client Setup ---

# Use the credentials from your HiveMQ Cloud cluster
broker = "6f052708e84c40d1bf4093fc430373a0.s1.eu.hivemq.cloud"
port = 8883
username = "Ahmed"
password = "01211005393aA"
topic = "alerts"

# Create a client instance using MQTTv5
client = paho.Client(client_id="", userdata=None, protocol=paho.MQTTv5)

# Assign the callback functions
client.on_connect = on_connect
client.on_publish = on_publish
client.on_subscribe = on_subscribe

# Enable TLS for a secure connection
client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)

# Set username and password
client.username_pw_set(username, password)

# Connect to the broker
client.connect(broker, port)

# --- The Action ---

# Subscribe to the 'alerts' topic to be thorough
client.subscribe(topic, qos=1)

# The JSON payload for the alert
alert_payload = {
    "id": 100,
    "type": "warning",
    "icon": "🤖",
    "title": "Python Script Test",
    "time": "Right now",
    "description": "This message was sent from the official HiveMQ test script.",
    "priority": "HIGH"
}

# Start a non-blocking network loop
client.loop_start()

# Publish the message
print(f"Publishing message to topic '{topic}'...")
client.publish(topic, payload=json.dumps(alert_payload), qos=1)

# Wait for a moment to allow for the publish acknowledgment
time.sleep(2)

# Stop the loop and disconnect
client.loop_stop()
client.disconnect()

print("Script finished.") 