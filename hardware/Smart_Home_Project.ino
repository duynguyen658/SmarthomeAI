#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <DHT.h>

// WIFI + MQTT
const char * ssid="xxxx";
const char * password="xxxx";
const char * mqtt_server="xxx";
const char* mqtt_id = "esp32_client_001";
const long port=1883;

const char* topic_publish = "smartHome/sensor/data"; 
const char* topic_state="smartHome/status/device";   
const char* topic_subscribe = "smartHome/command"; 

WiFiClient espClient;
PubSubClient client(espClient);

// PIN
#define DHTPIN 4
#define GAS_PIN 34      
#define Relay_fan 26
#define Relay_led 25

#define Relay_ON LOW
#define Relay_OFF HIGH
#define DHTTYPE DHT22

DHT dht(DHTPIN, DHTTYPE);

// STATE
bool stateFan=false;
bool stateLight=false;

// TIME
unsigned long previousMillis = 0;
const long interval = 10000;  // Gửi cảm biến mỗi 10 giây
unsigned long lastStatePublish = 0;
const long stateReplyInterval = 100;  // Reply state nhanh (100ms)

// DATA
int gas_level=0;
float temperature=0;
float huminity=0;

// WIFI
void connectWifi(){
  Serial.println("🔌 Connecting WiFi...");
  WiFi.begin(ssid, password);

  while(WiFi.status() != WL_CONNECTED){
    delay(500);
    Serial.print(".");
  }

  Serial.println("\n✅ WiFi connected!");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());
}

// MQTT
bool connectMQTT(){
  if(client.connected()) return true;

  Serial.print("🔗 Connecting MQTT...");

  if(client.connect(mqtt_id)){
    Serial.println("✅ Connected!");
    client.subscribe(topic_subscribe);
    Serial.print("📡 Subscribed: ");
    Serial.println(topic_subscribe);
    return true;
  } else {
    Serial.print("❌ Failed, rc=");
    Serial.println(client.state());
    return false;
  }
}

// CALLBACK
void callback(char* topic, byte* payload, unsigned int length){
  Serial.print("\n📩 Message arrived [");
  Serial.print(topic);
  Serial.print("]: ");

  for (int i = 0; i < length; i++) {
    Serial.print((char)payload[i]);
  }
  Serial.println();

  StaticJsonDocument<256> doc;
  if (deserializeJson(doc, payload, length)) {
    Serial.println("❌ JSON parse error");
    return;
  }

  const char* device=doc["device"];
  const char* status=doc["status"];

  Serial.print("👉 Device: "); Serial.println(device);
  Serial.print("👉 Status: "); Serial.println(status);

  if(!device || !status){
    Serial.println("❌ Missing device/status");
    return;
  }

  if(strcmp(device,"fan")==0){
    digitalWrite(Relay_fan, strcmp(status,"ON")==0 ? Relay_ON : Relay_OFF);
    stateFan = strcmp(status,"ON")==0;
    Serial.println("💨 Fan updated");
  }
  else if(strcmp(device,"light")==0){
    digitalWrite(Relay_led, strcmp(status,"ON")==0 ? Relay_ON : Relay_OFF);
    stateLight = strcmp(status,"ON")==0;
    Serial.println("💡 Light updated");
  }

  // Reply state với debounce - tránh spam MQTT
  if (millis() - lastStatePublish >= stateReplyInterval) {
    lastStatePublish = millis();
    
    StaticJsonDocument<128> res;
    res["fan_status"]= stateFan?"ON":"OFF";
    res["light_status"]= stateLight?"ON":"OFF";
    res["temp"]= temperature;
    res["humi"]= huminity;

    char buffer[128];
    serializeJson(res,buffer);

    if(client.publish(topic_state,buffer)){
      Serial.println("✅ State published");
    } else {
      Serial.println("❌ Publish state failed");
    }

    Serial.print("📤 State payload: ");
    Serial.println(buffer);
  } else {
    Serial.println("⏳ State reply debounced");
  }
}

// SETUP
void setup() {
  Serial.begin(115200);

  pinMode(Relay_fan, OUTPUT);
  pinMode(Relay_led, OUTPUT);

  digitalWrite(Relay_fan, Relay_OFF);
  digitalWrite(Relay_led, Relay_OFF);

  pinMode(GAS_PIN, INPUT);

  dht.begin();

  connectWifi();

  client.setServer(mqtt_server, port);
  client.setCallback(callback);
}

// LOOP
void loop() {

  static unsigned long lastMqttAttempt = 0;
  if (!client.connected()) {
    if (millis() - lastMqttAttempt > 5000) {
      lastMqttAttempt = millis();
      connectMQTT();
    }
  }

  client.loop();

  unsigned long currentMillis = millis();

  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis;

    Serial.println("\n======================");
    Serial.println("📊 Reading sensors...");

    long sumGas = 0;
    for(int i = 0; i < 10; i++){
        sumGas += analogRead(GAS_PIN);   
    }

    int gas = sumGas / 10;

    float h = dht.readHumidity();
    float t = dht.readTemperature();

    if (isnan(h) || isnan(t)) {
      Serial.println("❌ DHT read error");
      h = 0; t = 0;
    }

    gas_level = gas;
    temperature = t;
    huminity = h;

    Serial.print("🌡 Temp: "); Serial.println(t);
    Serial.print("💧 Humidity: "); Serial.println(h);
    Serial.print("🔥 Gas: "); Serial.println(gas);

    StaticJsonDocument<128> doc;
    doc["temperature"] = t;
    doc["humidity"] = h;
    doc["gas"] = gas;

    char buffer[128];
    serializeJson(doc, buffer);

    if(client.publish(topic_publish, buffer)){
      Serial.println("✅ Publish sensor OK");
    } else {
      Serial.println("❌ Publish sensor FAIL");
    }

    Serial.print("📤 Payload: ");
    Serial.println(buffer);
  }
}
