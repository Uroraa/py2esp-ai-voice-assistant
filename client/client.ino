#include <WiFi.h>
#include <WiFiUdp.h>
#include "driver/i2s.h"

#define I2S_BCLK_PIN    18
#define I2S_LRC_PIN     17
#define I2S_DOUT_PIN    16
#define LED_PIN         48
#define RELAY_PIN       5

const char *ssid = "Etek Office";
const char *password = "Taphaco@189";
// const char *ssid = "Sxmh2";
// const char *password = "123456789@";

const int local_port = 5005;
bool udpStarted;
char incomingTextPacket[512];
uint8_t incomingAudioPacket[2048];

WiFiUDP UDP; 

bool setupI2S() {
  const i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = 16000,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_I2S_MSB,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 1024,
    .use_apll = false,
    .tx_desc_auto_clear = true,
    .fixed_mclk = 0
  };

  const i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_BCLK_PIN,   
    .ws_io_num = I2S_LRC_PIN,     
    .data_out_num = I2S_DOUT_PIN,  
    .data_in_num = I2S_PIN_NO_CHANGE
  };

  i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pin_config);
  i2s_zero_dma_buffer(I2S_NUM_0);
  return true;
}

void play_audio(const uint16_t *audio_data, size_t len) {
  size_t bytes_written;
  i2s_write(I2S_NUM_0, audio_data, len, &bytes_written, portMAX_DELAY);
  // Serial.println(bytes_written);
  // Serial.println(len);
}

void setup() {
  Serial.begin(115200);

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);
  delay(10);

  WiFi.begin(ssid, password);
  udpStarted = UDP.begin(local_port);

  while(WiFi.status() != WL_CONNECTED){
    Serial.println("Connecting...");
    delay(1000);
  }
  
  Serial.println("WiFi connected");
  Serial.print("IP address: "); 
  Serial.println(WiFi.localIP());

  if (udpStarted) {
    Serial.println("UDP channel");
  }

  while (!setupI2S()) {
    Serial.println("i2s setting up...");
    delay(500);
  }
  Serial.println("i2s ok");
}

void loop() {
  int packet_size = UDP.parsePacket();
  if (packet_size <= 0) return;

  uint8_t header;
  UDP.read(&header, 1);
  
  if (header == 0x02) {
    int lenText = UDP.read(incomingTextPacket, sizeof(incomingTextPacket) - 1);
    if (lenText > 0) {
    incomingTextPacket[lenText] = 0;
    Serial.println(incomingTextPacket);  // text hiển thị
    
      if (lenText == 1 && (incomingTextPacket[0] == '0' || incomingTextPacket[0] == '1')) {
          uint8_t flag = incomingTextPacket[0] - '0';
          digitalWrite(RELAY_PIN, flag ? HIGH : LOW);
          Serial.println(flag ? "-> bật đèn" : "-> tắt đèn");
      }
    } 
  } else if (header == 0x03) {
    int lenAudio = UDP.read(incomingAudioPacket, sizeof(incomingAudioPacket));

    if (lenAudio > 0) {
      if (lenAudio % 2 != 0) lenAudio--;
      play_audio((uint16_t*)(incomingAudioPacket + 44), lenAudio - 44);
      // for (int i = 45; i < 50; i++) {
      //   Serial.print("Byte ");
      //   Serial.print(i);
      //   Serial.print(": 0x");
      //   if (incomingAudioPacket[i] < 0x10) Serial.print("0");
      //   Serial.println(incomingAudioPacket[i], HEX);
      // }   
    }

    // packet_size = UDP.parsepacket();
    // continue;

  } else {
    Serial.println("không nhận dc gói tin");
  }
}
