#include <Arduino.h>
#include <SPI.h>
#include <Adafruit_ST7789.h>
#include <ArduinoJson.h>
#include <time.h>
#include <sys/time.h>
#include <SD_MMC.h>
#include <esp_ota_ops.h>
#include "lunar_calendar.h"

// Waveshare ESP32-S3-LCD-1.47 official pin map, ST7789 172 x 320.
Adafruit_ST7789 lcd(&SPI, 42, 41, 39);
GFXcanvas16 frame(172, 320);
constexpr uint16_t BG=0x0842, CARD=0x10C4, WHITE=0xEF7D, MUTED=0x7C52, GREEN=0x4ED8, AMBER=0xFDC8;
struct Window { float used; int mins; time_t reset; } windows[2];
int count=0;
int page=0;
constexpr int PAGE_COUNT=5;
uint32_t appBytes=0, appSlotBytes=0;
struct StorageSnapshot { int state=0; uint64_t total=0,used=0; uint32_t started=0; };
StorageSnapshot storage;
portMUX_TYPE storageMux=portMUX_INITIALIZER_UNLOCKED;
StorageSnapshot readStorage(){
 portENTER_CRITICAL(&storageMux);auto value=storage;portEXIT_CRITICAL(&storageMux);return value;
}
void storageTask(void*){
 // FAT free-cluster scanning can be slow. Never run it on the UI/USB task.
 SD_MMC.setPins(14,15,16); // Official CLK/CMD/D0; 1-bit mode.
 bool mounted=SD_MMC.begin("/sdcard",true,false,10000,1); // Never format.
 uint64_t total=0,used=0;
 if(mounted){total=SD_MMC.totalBytes();used=SD_MMC.usedBytes();SD_MMC.end();}
 portENTER_CRITICAL(&storageMux);
 storage.total=total;storage.used=used;storage.state=mounted&&total>0?2:3;
 portEXIT_CRITICAL(&storageMux);
 vTaskDelete(nullptr);
}
void sampleStorage(){
 portENTER_CRITICAL(&storageMux);
 bool busy=storage.state==1;
 if(!busy){storage.state=1;storage.started=millis();}
 portEXIT_CRITICAL(&storageMux);
 if(!busy && xTaskCreatePinnedToCore(storageTask,"storage",6144,nullptr,1,nullptr,0)!=pdPASS){
  portENTER_CRITICAL(&storageMux);storage.state=3;portEXIT_CRITICAL(&storageMux);
 }
}
constexpr int BOOT_PIN=0;
bool bootRaw=HIGH, bootStable=HIGH;
uint32_t bootChanged=0;
float wbTotal=0, wbLeft=0, wbUsed=0;
struct Balance { String currency; double total,gift,paid; } dsBalances[2];
int dsCount=0;
bool dsOK=false, dsAvailable=false;
time_t dsUpdated=0;
String dsStatus="setup";
bool wbOK=false;
time_t wbUpdated=0;
bool clockReady=false, quotaOK=false, received=false;
uint32_t lastPacket=0, lastDraw=0;
time_t updated=0;
String input;
bool overflow=false;
void label(int x,int y,const String &s,int size=1,uint16_t color=WHITE){
 frame.setCursor(x,y); frame.setTextSize(size); frame.setTextColor(color); frame.print(s);
}
String storageSize(uint64_t bytes){
 if(bytes<1024) return String((unsigned long)bytes)+" B";
 if(bytes<1048576) return String((double)bytes/1024.0,1)+" KiB";
 if(bytes<1073741824ULL) return String((double)bytes/1048576.0,1)+" MiB";
 return String((double)bytes/1073741824.0,2)+" GiB";
}
void storageRow(int y,const String &name,const String &value,uint16_t color=WHITE){
 label(15,y,name,1,MUTED);
 label(157-value.length()*6,y,value,1,color);
}
String resetDate(time_t epoch){
 if(epoch<=0) return "Reset unknown";
 struct tm t; localtime_r(&epoch,&t);
 char text[24];
 strftime(text,sizeof(text),"Reset %Y-%m-%d %H:%M",&t);
 return String(text);
}
String money(double value){
 String text=String(value,2);
 if(text.length()>10){char compact[16];snprintf(compact,sizeof(compact),"%.3g",value);text=compact;}
 return text;
}
void chinese(int y,const String &text,uint16_t color=WHITE){
 int n=text.length()/3;int x=(172-n*20)/2;
 for(unsigned int i=0;i+2<text.length();i+=3){
  uint16_t code=((text[i]&15)<<12)|((text[i+1]&63)<<6)|(text[i+2]&63);
  for(const auto &g:lunarGlyphs)if(g.code==code){frame.drawBitmap(x,y,g.bits,20,20,color);break;}
  x+=20;
 }
}
void drawCalendar(time_t now,bool connected){
 frame.fillScreen(BG);
 chinese(7,"农历时辰",GREEN);
 if(!clockReady){label(15,90,"Waiting for USB time");}
 else{
  struct tm t;localtime_r(&now,&t);LunarDate lunar;
  char b[32];strftime(b,sizeof(b),"%H:%M",&t);label(11,36,b,5);
  strftime(b,sizeof(b),"%Y-%m-%d",&t);label(26,82,b,2,MUTED);
  chinese(108,week[(t.tm_wday+6)%7],GREEN);
  if(toLunar(t.tm_year+1900,t.tm_mon+1,t.tm_mday,lunar)){
   chinese(135,String(stems[(lunar.year-4)%10])+branches[(lunar.year-4)%12]+animals[(lunar.year-4)%12]+"年",AMBER);
   chinese(162,String(lunar.leap?"闰":"")+months[lunar.month]+days[lunar.day]);
  }else label(18,162,"Lunar out of range",1,AMBER);
  int si=shichenIndex(t.tm_hour,t.tm_min),ke=quarterIndex(t.tm_hour,t.tm_min);
  chinese(191,String(branches[si])+"时"+kes[ke]+"刻",GREEN);
  snprintf(b,sizeof(b),"%02d:00 - %02d:00",(si*2+23)%24,(si*2+1)%24);label(47,216,b,1,MUTED);
  chinese(234,organs[si],AMBER);
  chinese(263,advice[si],WHITE);
 }
 label(12,291,connected?"BEIJING / USB SYNC":"BEIJING / USB OFFLINE",1,connected?GREEN:AMBER);
 label(12,305,"5/5 BOOT > Codex",1,MUTED);
 lcd.drawRGBBitmap(0,0,frame.getBuffer(),172,320);
}
void draw(){
 time_t now=time(nullptr);
 bool connected=received && millis()-lastPacket<10000;
 if(page==4){drawCalendar(now,connected);return;}
 bool fresh=connected && quotaOK && updated>0 && now>=updated && now-updated<180;
 if(page==1) fresh=connected && wbOK && wbUpdated>0 && now>=wbUpdated && now-wbUpdated<180;
 if(page==2) fresh=connected && dsOK && dsUpdated>0 && now>=dsUpdated && now-dsUpdated<180;
 frame.fillScreen(BG);
 label(12,12,page==0?"OPENAI / CODEX":(page==1?"WORKBUDDY":(page==3?"DEVICE / STORAGE":"DEEPSEEK / API")),1,GREEN);
 frame.fillCircle(156,16,3,connected?GREEN:AMBER);
 char buf[32];
 if(clockReady){
  struct tm t; localtime_r(&now,&t);
  strftime(buf,sizeof(buf),"%H:%M",&t); label(11,38,buf,5);
  strftime(buf,sizeof(buf),"%Y-%m-%d  %a",&t); label(12,86,buf,1,MUTED);
 }else{label(11,38,"--:--",5);label(12,86,"Waiting for USB time",1,MUTED);}
 label(12,108,"BEIJING  UTC+8",1,MUTED);
 if(page==0) {
 for(int i=0;i<2;i++){
  int y=132+i*76;
  frame.fillRoundRect(8,y,156,68,8,CARD);
  if(i>=count){label(18,y+10,"QUOTA",1,MUTED);label(18,y+29,"Unavailable",1);continue;}
  Window w=windows[i];
  String title=w.mins==10080?"WEEK":(w.mins%60==0?String(w.mins/60)+" HOURS":String(w.mins)+" MINS");
  label(18,y+9,title,1,MUTED);
  label(126,y+9,"used",1,MUTED);
  label(18,y+21,String(w.used,0)+"%",3,fresh?GREEN:AMBER);
  label(100,y+32,String(100-(int)roundf(w.used))+"% left",1,fresh?MUTED:AMBER);
  frame.fillRoundRect(18,y+48,136,4,3,BG);
  int fill=roundf(136*w.used/100);
  if(fill>0) frame.fillRoundRect(18,y+48,fill,4,3,w.used>=80?AMBER:GREEN);
  label(18,y+56,resetDate(w.reset),1,w.reset>0 && w.reset<=now?AMBER:MUTED);
 }
 } else if(page==1) {
  frame.fillRoundRect(8,132,156,144,8,CARD);
  label(18,143,"CREDITS REMAINING",1,MUTED);
  if(wbUpdated==0) {
   label(18,169,"Unavailable",1,AMBER);
   label(18,207,"Usage unavailable",1,MUTED);
   label(18,226,"Check Mac sync log",1,MUTED);
  } else {
   String left=String(wbLeft,1);
   if(left.length()>11){char compact[16];snprintf(compact,sizeof(compact),"%.3g",(double)wbLeft);left=compact;}
   label(18,165,left,left.length()<=7?3:2,fresh?GREEN:AMBER);
   label(18,197,"Used  "+String(wbUsed,1),1,WHITE);
   label(18,215,"Total "+String(wbTotal,1),1,MUTED);
   frame.fillRoundRect(18,236,136,7,3,BG);
   int fill=wbTotal>0?roundf(136*min(1.0f,wbUsed/wbTotal)):0;
   if(fill>0)frame.fillRoundRect(18,236,fill,7,3,GREEN);
   struct tm wt; localtime_r(&wbUpdated,&wt);
   char stamp[24];strftime(stamp,sizeof(stamp),"Updated %m-%d %H:%M",&wt);
   label(18,256,stamp,1,MUTED);
  }
 }
 if(page==3){
  auto sd=readStorage();
  frame.fillRoundRect(8,128,156,153,8,CARD);
  label(15,136,String(ESP.getChipModel())+" / "+String(ESP.getChipCores())+" cores",1,GREEN);
  label(15,152,"CPU "+String(ESP.getCpuFreqMHz())+"MHz  LCD172x320",1,MUTED);
  storageRow(168,"Flash",storageSize(ESP.getFlashChipSize()));
  label(15,184,"APP "+String((appBytes+1023)/1024)+"/"+String(appSlotBytes/1024)+" KiB",1,WHITE);
  uint32_t heapTotal=ESP.getHeapSize(),heapFree=ESP.getFreeHeap();
  label(15,200,"Heap "+String((heapTotal-heapFree)/1024)+"/"+String(heapTotal/1024)+" KiB",1,WHITE);
  label(15,216,ESP.getPsramSize()?"PSRAM "+String((ESP.getPsramSize()-ESP.getFreePsram())/1024)+"/"+String(ESP.getPsramSize()/1024)+"K":"PSRAM not enabled",1,MUTED);
  label(15,232,"SD CARD",1,GREEN);
  if(sd.state==2){
   storageRow(248,"Used",storageSize(sd.used));
   storageRow(266,"Total",storageSize(sd.total));
  }else{
   label(15,248,sd.state==1?"Reading SD...":"Absent / unreadable",1,AMBER);
   label(15,266,sd.state==1?String((millis()-sd.started)/1000)+"s / BOOT still works":"Reopen page to retry",1,MUTED);
  }
 }
 if(page==2){
  frame.fillRoundRect(8,132,156,144,8,CARD);
  if(dsOK && dsCount){
   int index=(millis()/5000)%dsCount;
   const Balance &b=dsBalances[index];
   label(18,143,"BALANCE "+b.currency+(dsCount>1?" "+String(index+1)+"/"+String(dsCount):""),1,MUTED);
   String total=money(b.total);
   label(18,162,total,total.length()<=7?3:2,fresh?GREEN:AMBER);
   label(18,195,"Paid " + money(b.paid),1,WHITE);
   label(18,210,"Gift " + money(b.gift),1,MUTED);
   label(18,225,dsAvailable?"API: AVAILABLE":"API: NO BALANCE",1,dsAvailable?GREEN:AMBER);
   label(18,240,"Usage/tokens: N/A",1,MUTED);
   struct tm dt;localtime_r(&dsUpdated,&dt);
   char stamp[24];strftime(stamp,sizeof(stamp),"Updated %m-%d %H:%M",&dt);
   label(18,258,stamp,1,MUTED);
  }else{
   label(18,143,"BALANCE",1,MUTED);
   label(18,168,"Unavailable",1,AMBER);
   label(18,198,(dsStatus=="key_missing" || dsStatus=="setup")?"Set API key on Mac":(dsStatus=="keychain"?"Unlock Mac keychain":(dsStatus=="auth"?"Check API key on Mac":"Check Mac / network")),1,WHITE);
   label(18,224,"Official balance API",1,MUTED);
   label(18,244,"Usage/tokens: N/A",1,MUTED);
  }
 }
 if(page==3) label(12,289,connected?"LOCAL / TIME SYNC":"LOCAL / USB OFFLINE",1,connected?GREEN:AMBER);
 else label(12,289,fresh?"LIVE / USB":(connected?"QUOTA STALE":"USB DISCONNECTED"),1,fresh?GREEN:AMBER);
 label(12,305,page==0?"1/5 BOOT > WorkBuddy":(page==1?"2/5 BOOT > DeepSeek":(page==2?"3/5 BOOT > Device":"4/5 BOOT > Calendar")),1,MUTED);
 lcd.drawRGBBitmap(0,0,frame.getBuffer(),172,320);
}
void packet(){
 JsonDocument doc;
 if(deserializeJson(doc,input) || doc["v"].as<int>()!=1 || !doc["epoch"].is<long long>()) return;
 long long epoch=doc["epoch"].as<long long>();
 if(epoch<1700000000LL || epoch>4102444800LL) return;
 timeval tv={(time_t)epoch,0}; settimeofday(&tv,nullptr); clockReady=true;
 count=0;
 for(JsonObject w:doc["windows"].as<JsonArray>()){
  if(count==2) break;
  float used=w["used"].as<float>(); int mins=w["mins"].as<int>();
  if(!w["used"].is<float>() || !isfinite(used) || used<0 || used>100 || mins<=0) continue;
  windows[count++]={used,mins,w["reset"].as<time_t>()};
 }
 updated=doc["updated"].as<time_t>();quotaOK=doc["ok"].as<bool>();received=true;lastPacket=millis();
 JsonObject wb=doc["workbuddy"].as<JsonObject>();
 wbOK=wb["ok"].as<bool>();
 if(wb["updated"].as<time_t>()>0 && wb["total"].is<float>() && wb["left"].is<float>() && wb["used"].is<float>()){
  float t=wb["total"],l=wb["left"],u=wb["used"];
  if(isfinite(t)&&isfinite(l)&&isfinite(u)&&t>=0&&l>=0&&u>=0){wbTotal=t;wbLeft=l;wbUsed=u;wbUpdated=wb["updated"].as<time_t>();}
  else wbOK=false;
 }else wbOK=false;
 JsonObject ds=doc["deepseek"].as<JsonObject>();
 dsOK=ds["ok"].as<bool>();dsCount=0;
 dsAvailable=ds["available"].as<bool>();dsUpdated=ds["updated"].as<time_t>();
 dsStatus=ds["status"].as<String>();
 if(dsOK){
  for(JsonObject b:ds["balances"].as<JsonArray>()){
   String currency=b["currency"].as<String>();
   if(dsCount>=2 || (currency!="CNY" && currency!="USD")) {dsOK=false;break;}
   if(!b["total"].is<double>() || !b["gift"].is<double>() || !b["paid"].is<double>()){dsOK=false;break;}
   double t=b["total"],g=b["gift"],p=b["paid"];
   if(!isfinite(t)||!isfinite(g)||!isfinite(p)){dsOK=false;break;}
   dsBalances[dsCount++]={currency,t,g,p};
  }
  if(!dsCount || dsUpdated<=0) dsOK=false;
 }
 auto sd=readStorage();
 Serial.printf("{\"ack\":1,\"screen\":\"clock-quota-v5.3\",\"windows\":%d,\"epoch\":%lld,\"heap\":%u,\"page\":%d,\"wb_ok\":%d,\"ds_ok\":%d,\"flash\":%u,\"app\":%u,\"slot\":%u,\"heap_total\":%u,\"psram\":%u,\"sd_mounted\":%d,\"sd_state\":%d,\"sd_total\":%llu,\"sd_used\":%llu}\n",count,epoch,ESP.getFreeHeap(),page,wbOK,dsOK,ESP.getFlashChipSize(),appBytes,appSlotBytes,ESP.getHeapSize(),ESP.getPsramSize(),sd.state==2,sd.state,(unsigned long long)sd.total,(unsigned long long)sd.used);
}
void setup(){
 appBytes=ESP.getSketchSize();
 const esp_partition_t *app=esp_ota_get_running_partition();
 if(app) appSlotBytes=app->size;
 pinMode(BOOT_PIN,INPUT_PULLUP);
 Serial.setRxBufferSize(2048);
 Serial.begin(115200);
 SPI.begin(40,-1,45,42);
 lcd.init(172,320);lcd.setRotation(2);lcd.invertDisplay(true);
 // Panel power/gamma values from Waveshare Display_ST7789.cpp.
 const uint8_t porch[]={0x0C,0x0C,0x00,0x33,0x33};
 lcd.sendCommand(0xB2,porch,sizeof(porch));
 const uint8_t commands[]={0xB7,0xBB,0xC0,0xC2,0xC3,0xC4,0xC6,0xD6};
 const uint8_t values[]={0x35,0x35,0x2C,0x01,0x13,0x20,0x0F,0xA1};
 for(int i=0;i<8;i++)lcd.sendCommand(commands[i],values+i,1);
 const uint8_t power[]={0xA4,0xA1};lcd.sendCommand(0xD0,power,2);
 const uint8_t positive[]={0xF0,0x00,0x04,0x04,0x04,0x05,0x29,0x33,0x3E,0x38,0x12,0x12,0x28,0x30};
 const uint8_t negative[]={0xF0,0x07,0x0A,0x0D,0x0B,0x07,0x28,0x33,0x3E,0x36,0x14,0x14,0x29,0x32};
 lcd.sendCommand(0xE0,positive,sizeof(positive));lcd.sendCommand(0xE1,negative,sizeof(negative));
 pinMode(48,OUTPUT);digitalWrite(48,HIGH);
 setenv("TZ","CST-8",1);tzset();
 input.reserve(1024); draw();
}
void loop(){
 bool raw=digitalRead(BOOT_PIN);
 if(raw!=bootRaw){bootRaw=raw;bootChanged=millis();}
 if(millis()-bootChanged>=40 && bootStable!=bootRaw){
  bootStable=bootRaw;
  if(bootStable==LOW){page=(page+1)%PAGE_COUNT;if(page==3)sampleStorage();draw();lastDraw=millis();}
 }
 while(Serial.available()){
  char c=Serial.read();
  if(c=='\n'){if(!overflow)packet();input="";overflow=false;}
  else if(c!='\r') {if(input.length()<1024 && !overflow)input+=c;else overflow=true;}
 }
 if(millis()-lastDraw>=1000){lastDraw=millis();draw();}
 delay(2);
}
