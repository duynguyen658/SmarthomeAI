#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <DHT.h>

// --- CẤU HÌNH MẠNG ---
// const char* ssid = "OngNgoai";
// const char* password = "0913858753";
// const char * ssid="Van Ut_Lau 4-5";
// const char * password="vanut1978@";
const char * ssid="GDU-Core";
const char * password="GDU2024@371NK@";
const char * mqtt_server="10.0.18.255";
const char* mqtt_id = "esp32_client_001";
const long port=1881;
// Topic gửi dữ liệu lên (Node-RED sẽ nghe topic này)
const char* topic_publish = "home/sensor/data"; 
const char* topic_state="home/status/device";   
// Topic nhận lệnh (Dùng cho bước sau)
const char* topic_subscribe = "home/command"; 

WiFiClient espClient;
PubSubClient client(espClient);

// --- KHAI BÁO PIN (Theo cấu hình của bạn) ---
#define DHTPIN 4
#define GAS_PIN 34      
#define LRDPIN 35      
#define Relay_fan 26
#define Relay_led 25
#define Buzzer 27
#define Relay_ON LOW
#define Relay_OFF HIGH
#define DHTTYPE DHT11

DHT dht(DHTPIN, DHTTYPE);
//----- Trạng thái thiết bị ----------
bool stateFan=false;
bool stateLight=false;
// ----------Buzzer-------
bool buzzerState = false;
unsigned long buzzerMillis = 0;
const long buzzerInterval = 800;
// --- BIẾN QUẢN LÝ THỜI GIAN (NON-BLOCKING) ---
unsigned long previousMillis = 0;
const long interval = 5000; // Gửi dữ liệu mỗi 5000ms (5 giây)

int gas_level=0;
float temperature=0;
float huminity=0;
// ============================ Hàm kết nối Wifi ==========================
void connectWifi(){
  delay(10);
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  while(WiFi.status() != WL_CONNECTED){
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected to Wifi");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

//============================ Hàm kết nối MQTT ==========================
bool connectMQTT(){
  // while(!client.connected()){
  //   Serial.print("Attempting MQTT connection...");
  //   if(client.connect(mqtt_id)){
  //     Serial.println("connected");
  //     client.subscribe(topic_subscribe);
  //   }
  //   else{
  //     Serial.print("failed, rc=");
  //     Serial.print(client.state());
  //     Serial.println(" try again in 5 seconds");
  //     delay(5000);
  //   }
  // }
  if(client.connected()) return true;

  if(client.connect(mqtt_id)){
    client.subscribe(topic_subscribe);
    Serial.println("MQTT connected");
    return true;
  }
  else{
    Serial.print("MQTT failed, rc=");
    Serial.println(client.state());
    return false;
  }
}

//============================ Hàm callback (Nhận lệnh) =================
void callback(char* topic, byte* payload, unsigned int length){
  // Tạm thời để trống, sẽ code ở bước sau
  Serial.print("Message arrived [");
  Serial.print(topic);
  Serial.print("]: ");

  StaticJsonDocument<256> doc;
  DeserializationError error= deserializeJson(doc, payload, length);
  if(error){
    Serial.print("Lỗi giải mã json: ");
    Serial.println(error.c_str());
    return;
  }
  const char* device=doc["device"];
  const char* status=doc["status"];
  Serial.print("Device: "); Serial.print(device);
  Serial.print(" - Status: "); Serial.print(status);

  //kiểm tra lệnh tránh null
  if(!device || !status){
    Serial.println("Mising device or status key! ");
    return;
  }
//-----------Xử lí lệnh -------------
  if(strcmp(device,"fan")==0){
    if (strcmp(status, "ON") == 0) {
      digitalWrite(Relay_fan, Relay_ON); // Bật
      stateFan=true;
      Serial.println("=> Đã BẬT Quạt");

  }
  else {
      digitalWrite(Relay_fan, Relay_OFF); // Tắt
      stateFan=false;
      Serial.println("=> Đã TẮT Quạt");
    }
}
// --- ĐIỀU KHIỂN ĐÈN (LED) ---
  else if (strcmp(device, "light") == 0) {
    if (strcmp(status, "ON") == 0) {
      digitalWrite(Relay_led, Relay_ON); // Bật
      stateLight=true;
      Serial.println("=> Đã BẬT Đèn");
    } else {
      digitalWrite(Relay_led, Relay_OFF); // Tắt
      stateLight=false;
      Serial.println("=> Đã TẮT Đèn");
    }
  }


  StaticJsonDocument<128>  docResponse;
  docResponse["fan_status"]= stateFan?"ON":"OFF";
  docResponse["light_status"]= stateLight?"ON":"OFF";
  docResponse["temp"]= temperature;
  docResponse["humi"]=huminity;
  char buffer[256];
  serializeJson(docResponse,buffer);
  client.publish(topic_state,buffer);
  Serial.print("=> Đã gửi cập nhật trạng thái: ");
  Serial.println(buffer);

}
// =========================== Hàm setup ===============================  
void setup() {
  Serial.begin(115200);
  
  // Setup Pin Output
  pinMode(Relay_fan, OUTPUT);
  pinMode(Relay_led, OUTPUT);
  digitalWrite(Relay_fan, Relay_OFF);
  digitalWrite(Relay_led, Relay_OFF);
  
  // Setup Pin Input
  pinMode(LRDPIN, INPUT);
  pinMode(GAS_PIN, INPUT);
  pinMode(Buzzer, OUTPUT);
  digitalWrite(Buzzer, LOW);
  dht.begin();
  
  connectWifi();
  client.setServer(mqtt_server, port);
  client.setCallback(callback);
}

//========================== Hàm loop (Xử lý chính) ============================
void loop() {
  // 1. Kiểm tra kết nối MQTT
  // if (!client.connected()) {
  //   connectMQTT();
  // }
  // client.loop(); // Duy trì kết nối để nhận lệnh bất cứ lúc nào
  static unsigned long lastMqttAttempt = 0;
if (!client.connected()) {
  if (millis() - lastMqttAttempt > 5000) {
    lastMqttAttempt = millis();
    connectMQTT();
  }
}
client.loop();

  // 2. Gửi dữ liệu định kỳ (Không dùng delay để tránh treo hệ thống)
  unsigned long currentMillis = millis();
  unsigned long now=millis();
  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis; // Lưu lại mốc thời gian
    long sumGas = 0;
    long sumLight = 0;
    
    // Đọc 20 lần liên tiếp
    for(int i = 0; i < 10; i++){
        sumGas += analogRead(GAS_PIN);   
        sumLight += analogRead(LRDPIN);  
        
    }
    
    int gas = sumGas / 10;
    int light = sumLight / 10;

    // --- 2. ĐỌC DHT ---
    float h = dht.readHumidity();
    float t = dht.readTemperature();
    
    if (isnan(h) || isnan(t)) {
      Serial.println("DHT Error!");
      h = 0; t = 0; 
    }
    // --- ĐÓNG GÓI JSON ---
    StaticJsonDocument<256> doc;
    doc["temperature"] = t;
    doc["humidity"] = h;
    doc["light"] = light;
    doc["gas"] = gas;
    gas_level=gas;
    temperature=t;
    huminity=h;
    // doc["stateFan"]=stateFan?"ON":"OFF";
    // doc["stateLight"]=stateLight?"ON":"OFF";

    // Chuyển JSON thành chuỗi ký tự
    char buffer[256];
    serializeJson(doc, buffer);

    // --- GỬI LÊN NODE-RED ---
    client.publish(topic_publish, buffer);
    
    // In ra Serial để kiểm tra
    Serial.print("Sent JSON: ");
    Serial.println(buffer);
  }

  // --- MỨC NGUY HIỂM ---
if (gas_level >= 2500) {
  digitalWrite(Buzzer, HIGH); // Kêu liên tục
  buzzerState = true;
}
// --- MỨC CẢNH BÁO ---
else if (gas_level >= 2000) {
  if (now - buzzerMillis >= buzzerInterval) {
    buzzerMillis = now;
    buzzerState = !buzzerState;
    digitalWrite(Buzzer, buzzerState ? HIGH : LOW);
  }
}
// --- BÌNH THƯỜNG ---
else {
  digitalWrite(Buzzer, LOW);
  buzzerState = false;
}

}