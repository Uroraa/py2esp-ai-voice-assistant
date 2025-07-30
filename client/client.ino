#include <WiFi.h>
#include <WiFiUdp.h>
#include "driver/i2s.h"
#include <string.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

QueueHandle_t audioQueue;
WiFiUDP UDP;

const char* ssid = "Etek Office";
const char* password = "Taphaco@189";
// const char* ssid = "Sxmh2";
// const char* password = "123456789@";

#define I2S_BCLK_PIN 18
#define I2S_LRC_PIN 17
#define I2S_DOUT_PIN 16
#define LED_PIN 48
#define RELAY_PIN 5
#define MAX_PACKET_SIZE 1100
#define QUEUE_LENGTH 10
#define SERVER_IP "192.168.25.98"
#define LOCAL_PORT 5005

bool udpStarted;

enum PacketType : uint8_t {
  PACKET_TEXT = 0x02,
  PACKET_AUDIO = 0x03
};

struct UDP_Packet {
  uint16_t len;
  uint8_t buf[1100];
};

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

void packet_recv(void* pv) {
  UDP_Packet pkt;
  while (true) {
    int packet_size = UDP.parsePacket();
    if (packet_size > 0 && packet_size <= MAX_PACKET_SIZE) {
      int length = UDP.read(pkt.buf, packet_size);
      pkt.len = (uint16_t)length;
      xQueueSend(audioQueue, &pkt, portMAX_DELAY);
    }
    vTaskDelay(pdMS_TO_TICKS(1));
  }
}

void packet_handle(void* pv) {
  static bool headerStripped = false;
  UDP_Packet pkt;
  while (true) {
    if (xQueueReceive(audioQueue, &pkt, portMAX_DELAY) == pdTRUE) {
      uint8_t type = pkt.buf[0];
      if (type == PACKET_TEXT) {
        int lenText = pkt.len - 1;
        pkt.buf[lenText + 1] = '\0';
        Serial.println((char*)pkt.buf + 1);  // text hiển thị

        if (lenText == 1 && (pkt.buf[1] == '0' || pkt.buf[1] == '1')) {
          digitalWrite(RELAY_PIN, pkt.buf[1] ? HIGH : LOW);
          Serial.println(pkt.buf[1] ? "-> đã bật" : "-> đã tắt");
        }

      } else if (type == PACKET_AUDIO) {
        // Audio packet: buf layout = [type(1)] [seq(2 bytes)] [payload...]
        size_t offset = 1;
        size_t dataLen = pkt.len - offset;
        uint8_t* dataPtr = pkt.buf + offset;

        if (!headerStripped) {
          dataPtr += 44;
          dataLen -= 44;
          headerStripped = true;
        }
        size_t bytesWritten;
        i2s_write(I2S_NUM_0, dataPtr, dataLen, &bytesWritten, portMAX_DELAY);
      } else {
        Serial.println("Không nhận dc gói tin");
      }
    }
  }
}

void ready_status(){
  char is_ready[] = "READY";
  struct sockaddr_in dest_addr;
  dest_addr.sin_addr.s_addr = inet_addr(SERVER_IP);
  dest_addr.sin_family = AF_INET;
  dest_addr.sin_port = htons(LOCAL_PORT);

  int sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
  sendto(sock, is_ready, strlen(is_ready), 0, (struct sockaddr *)&dest_addr, sizeof(dest_addr));
  close(sock);
}

void setup() {
  Serial.begin(115200);

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    Serial.println("Connecting...");
    delay(1000);
  }

  Serial.println("WiFi connected");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());

  udpStarted = UDP.begin(LOCAL_PORT);
  if (udpStarted) {
    Serial.println("UDP channel");
  }

  audioQueue = xQueueCreate(
    QUEUE_LENGTH,
    sizeof(UDP_Packet));

  while (!setupI2S()) {
    Serial.println("i2s setting up...");
    delay(500);
  }
  Serial.println("i2s ok");

  xTaskCreatePinnedToCore(packet_recv, "Packet Receiver", 4096, nullptr, 2, nullptr, 1);
  xTaskCreatePinnedToCore(packet_handle, "Packet Handle", 8192, nullptr, 1, nullptr, 0);
}

void loop() {
  vTaskDelay(pdMS_TO_TICKS(1000));
}
