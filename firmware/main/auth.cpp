#include "auth.hpp"
#include "dashboard.hpp"
#include "products.hpp"
#include "contacts.hpp"
#include "module_policy.hpp"
#include "sales.hpp"
#include "inventory.hpp"
#include <sys/stat.h>
#include "sdkconfig.h"

#if !CONFIG_SLAVE_IDF_TARGET_ESP32C6
#error "Tab5 requires ESP32-C6 as the ESP-Hosted slave target"
#endif
#include "bsp/esp-bsp.h"
#include "erp_fonts.h"
#include "esp_wifi.h"
#include "esp_heap_caps.h"
#include <cstdlib>
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_netif_sntp.h"
#include "esp_http_client.h"
#include "esp_crt_bundle.h"
#include "esp_random.h"
#include "bootloader_random.h"
#include "esp_mac.h"
#include "esp_timer.h"
#include "esp_system.h"
#include "settings_file.hpp"
#include "mbedtls/pkcs5.h"
#include "mbedtls/gcm.h"
#include "mbedtls/platform_util.h"
#include "cJSON.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/event_groups.h"
#include <cstring>
#include <cstdio>
#include <ctime>
#include <string>
#include <algorithm>

namespace tab5 {
namespace {
template<class T> struct InternalAllocator {
    using value_type=T;
    InternalAllocator()=default;
    template<class U> InternalAllocator(const InternalAllocator<U>&) {}
    T* allocate(size_t count){auto* p=static_cast<T*>(heap_caps_malloc(count*sizeof(T),MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT));if(!p)abort();return p;}
    void deallocate(T* p,size_t count){mbedtls_platform_zeroize(p,count*sizeof(T));heap_caps_free(p);}
    template<class U> bool operator==(const InternalAllocator<U>&)const{return true;}
    template<class U> bool operator!=(const InternalAllocator<U>&)const{return false;}
};
using String=std::basic_string<char,std::char_traits<char>,InternalAllocator<char>>;
enum class Page { Provision, Unlock, Configure, Login, Password, Session, LocalPassword, ConfirmForget, ConfirmReset };
enum class Action { Provision, Unlock, Save, Scan, Login, Password, Logout, LocalPassword, Forget, Lock, Reset, Home, Theme };
struct Command { Action action; char fields[4][192]; };
struct Settings { char ssid[33]; char password[65]; char api[160]; bool setup_complete; };
struct Envelope { uint32_t format; uint8_t salt[16]; uint8_t iv[12]; uint8_t tag[16]; uint8_t data[sizeof(Settings)]; };
struct View { Page page; bool busy; unsigned serial; char message[1536]; char generated[25]; char networks[320]; bool light; bool authenticated; bool api_ready; bool checking; char identity[1536]; char permissions[2048]; char ssid[33]; char api[160]; };
View view{};
QueueHandle_t commands;
SemaphoreHandle_t view_lock;
EventGroupHandle_t wifi_events;
constexpr char settings_path[]="/sdcard/ERP/config/settings.enc";
bool card_ready=false;
Settings settings{};
Envelope envelope{};
uint8_t key[32]{};
bool unlocked=false, wifi_started=false;
bool browsing_products=false;
bool browsing_contacts=false;
bool browsing_sales=false;
bool browsing_inventory=false;
esp_netif_t* netif=nullptr;
String access, refresh_token;
char device_id[32]{};
int64_t refresh_at=0, retry_at=0, lock_until=0;
unsigned failures=0, reconnects=0;
lv_obj_t *panel, *heading, *message, *fields[4], *field_labels[4], *buttons[4], *keyboard, *networks, *return_button, *home_button;
lv_group_t *input_group,*diagnostic_group;
bool secret_fields[4]{},revealed=false;
Page rendered=Page::Provision;
unsigned rendered_serial=0;

void wipe(void* data, size_t size) { mbedtls_platform_zeroize(data,size); }
void* json_allocate(size_t size){auto* raw=static_cast<uint8_t*>(heap_caps_malloc(size+16,MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT));if(!raw)return nullptr;memcpy(raw,&size,sizeof(size));return raw+16;}
void json_release(void* ptr){if(!ptr)return;auto* raw=static_cast<uint8_t*>(ptr)-16;size_t size;memcpy(&size,raw,sizeof(size));wipe(raw,size+16);heap_caps_free(raw);}
void random_bytes(void* data,size_t size){esp_fill_random(data,size);}
void publish(Page page,const char* text,bool busy=false) {
    xSemaphoreTake(view_lock,portMAX_DELAY);
    view.page=page; view.busy=busy; ++view.serial;
    snprintf(view.message,sizeof(view.message),"%s",text);
    xSemaphoreGive(view_lock);
}
constexpr char journal_path[]="/sdcard/ERP/pdv/pending.enc";
struct PendingSale { uint32_t format; int user; char api[160]; char device[32]; char request[4097]; };
struct SaleEnvelope { uint32_t format; uint8_t iv[12],tag[16],data[sizeof(PendingSale)]; };
bool pending_record_exists(const char* path){char backup[96];snprintf(backup,sizeof(backup),"%s.bak",path);FILE* f=fopen(path,"rb");if(!f)f=fopen(backup,"rb");if(!f)return false;fclose(f);return true;}
constexpr char inventory_journal_path[]="/sdcard/ERP/inventory/pending.enc";
bool pending_operation_exists(){return pending_record_exists(journal_path)||pending_record_exists(inventory_journal_path);}

int protected_journal(const char* operation,int user,char* request,size_t capacity,const char* path,const char* aad){
    if(!unlocked||!card_ready)return -1;
    if(strcmp(operation,"clear")==0)return erase_settings_files(path)?1:-1;
    auto* plain=static_cast<PendingSale*>(heap_caps_calloc(1,sizeof(PendingSale),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
    auto* sealed=static_cast<SaleEnvelope*>(heap_caps_calloc(1,sizeof(SaleEnvelope),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
    if(!plain||!sealed){heap_caps_free(plain);heap_caps_free(sealed);return -1;}
    bool saving=strcmp(operation,"save")==0;int result=-1;
    if(saving){if(strlen(request)>=sizeof(plain->request)){heap_caps_free(plain);heap_caps_free(sealed);return -1;}plain->format=1;plain->user=user;snprintf(plain->device,sizeof(plain->device),"%s",device_id);snprintf(plain->api,sizeof(plain->api),"%s",settings.api);snprintf(plain->request,sizeof(plain->request),"%s",request);sealed->format=1;random_bytes(sealed->iv,sizeof(sealed->iv));}
    else{auto rc=load_settings_file(path,sealed,sizeof(*sealed));if(rc==FileRead::Missing)result=0;else if(rc!=FileRead::Found||sealed->format!=1)result=-1;if(rc!=FileRead::Found||sealed->format!=1){wipe(plain,sizeof(*plain));wipe(sealed,sizeof(*sealed));heap_caps_free(plain);heap_caps_free(sealed);return result;}}
    mbedtls_gcm_context ctx;mbedtls_gcm_init(&ctx);int rc=mbedtls_gcm_setkey(&ctx,MBEDTLS_CIPHER_ID_AES,key,256);
    if(rc==0&&saving)rc=mbedtls_gcm_crypt_and_tag(&ctx,MBEDTLS_GCM_ENCRYPT,sizeof(*plain),sealed->iv,sizeof(sealed->iv),reinterpret_cast<const uint8_t*>(aad),strlen(aad)+1,reinterpret_cast<const uint8_t*>(plain),sealed->data,16,sealed->tag);
    if(rc==0&&!saving)rc=mbedtls_gcm_auth_decrypt(&ctx,sizeof(*plain),sealed->iv,sizeof(sealed->iv),reinterpret_cast<const uint8_t*>(aad),strlen(aad)+1,sealed->tag,16,sealed->data,reinterpret_cast<uint8_t*>(plain));
    mbedtls_gcm_free(&ctx);
    if(rc==0&&saving){char folder[96];snprintf(folder,sizeof(folder),"%s",path);char* slash=strrchr(folder,'/');if(slash)*slash=0;mkdir(folder,0755);result=save_settings_file(path,sealed,sizeof(*sealed))?1:-1;}
    if(rc==0&&!saving){if(plain->format!=1||!memchr(plain->api,0,sizeof(plain->api))||!memchr(plain->device,0,sizeof(plain->device))||!memchr(plain->request,0,sizeof(plain->request)))result=-1;else if(plain->user!=user||strcmp(plain->device,device_id)||strcmp(plain->api,settings.api))result=-2;else if(strlen(plain->request)<capacity){snprintf(request,capacity,"%s",plain->request);result=1;}}
    wipe(plain,sizeof(*plain));wipe(sealed,sizeof(*sealed));heap_caps_free(plain);heap_caps_free(sealed);return result;
}

int sale_journal(const char* operation,int user,char* request,size_t capacity){return protected_journal(operation,user,request,capacity,journal_path,"TAB5 ERP pending sale v1");}
int inventory_journal(const char* operation,int user,char* request,size_t capacity){return protected_journal(operation,user,request,capacity,inventory_journal_path,"TAB5 ERP pending inventory v1");}

void clear_session() { xSemaphoreTake(view_lock,portMAX_DELAY);view.authenticated=false;xSemaphoreGive(view_lock); if(!access.empty())wipe(access.data(),access.size()); if(!refresh_token.empty())wipe(refresh_token.data(),refresh_token.size()); access.clear();refresh_token.clear();refresh_at=0; }
bool derive(const char* password,const uint8_t* salt,uint8_t* result,unsigned iterations=200000) {
    mbedtls_md_context_t ctx;mbedtls_md_init(&ctx);
    uint8_t u[32]{};constexpr uint8_t block[]={0,0,0,1};
    int rc=mbedtls_md_setup(&ctx,mbedtls_md_info_from_type(MBEDTLS_MD_SHA256),1);
    if(rc==0)rc=mbedtls_md_hmac_starts(&ctx,reinterpret_cast<const uint8_t*>(password),strlen(password));
    if(rc==0)rc=mbedtls_md_hmac_update(&ctx,salt,16);
    if(rc==0)rc=mbedtls_md_hmac_update(&ctx,block,sizeof(block));
    if(rc==0)rc=mbedtls_md_hmac_finish(&ctx,u);
    memcpy(result,u,32);
    for(unsigned i=1;i<iterations && rc==0;++i){
        rc=mbedtls_md_hmac_reset(&ctx);
        if(rc==0)rc=mbedtls_md_hmac_update(&ctx,u,32);
        if(rc==0)rc=mbedtls_md_hmac_finish(&ctx,u);
        for(unsigned j=0;j<32;++j)result[j]^=u[j];
        if((i&511)==0)vTaskDelay(1);
    }
    wipe(u,sizeof(u));mbedtls_md_free(&ctx);if(rc!=0)wipe(result,32);return rc==0;
}
bool crypt(bool encrypt,const uint8_t* cipher_key,Envelope& e,Settings& s) {
    mbedtls_gcm_context ctx;mbedtls_gcm_init(&ctx);
    int rc=mbedtls_gcm_setkey(&ctx,MBEDTLS_CIPHER_ID_AES,cipher_key,256);
    constexpr char aad[]="TAB5 ERP settings v1";
    if(rc==0 && encrypt) rc=mbedtls_gcm_crypt_and_tag(&ctx,MBEDTLS_GCM_ENCRYPT,sizeof(s),e.iv,sizeof(e.iv),
        reinterpret_cast<const uint8_t*>(aad),sizeof(aad),reinterpret_cast<const uint8_t*>(&s),e.data,16,e.tag);
    if(rc==0 && !encrypt) rc=mbedtls_gcm_auth_decrypt(&ctx,sizeof(s),e.iv,sizeof(e.iv),
        reinterpret_cast<const uint8_t*>(aad),sizeof(aad),e.tag,16,e.data,reinterpret_cast<uint8_t*>(&s));
    mbedtls_gcm_free(&ctx); return rc==0;
}
bool save() {
    Envelope next=envelope;
    random_bytes(next.iv,sizeof(next.iv));
    if(!crypt(true,key,next,settings))return false;
    if(!card_ready || !save_settings_file(settings_path,&next,sizeof(next)))return false;
    envelope=next;return true;
}
void config_view(){
    xSemaphoreTake(view_lock,portMAX_DELAY);snprintf(view.ssid,sizeof(view.ssid),"%s",settings.ssid);snprintf(view.api,sizeof(view.api),"%s",settings.api);xSemaphoreGive(view_lock);
}
void wifi_event(void*,esp_event_base_t base,int32_t id,void*) {
    if(base==IP_EVENT && id==IP_EVENT_STA_GOT_IP)xEventGroupSetBits(wifi_events,1);
    if(base==WIFI_EVENT && id==WIFI_EVENT_STA_DISCONNECTED)xEventGroupClearBits(wifi_events,1);
}
bool init_wifi() {
    if(wifi_started)return true;
    if(bsp_feature_enable(BSP_FEATURE_WIFI,true)!=ESP_OK)return false;
    // E1.P0 is RF path selection; low selects the built-in antenna.
    auto antenna=bsp_io_expander_init();if(!antenna)return false;
    if(esp_io_expander_set_dir(antenna,IO_EXPANDER_PIN_NUM_0,IO_EXPANDER_OUTPUT)!=ESP_OK ||
       esp_io_expander_set_level(antenna,IO_EXPANDER_PIN_NUM_0,0)!=ESP_OK ||
       esp_io_expander_set_output_mode(antenna,IO_EXPANDER_PIN_NUM_0,IO_EXPANDER_OUTPUT_MODE_PUSH_PULL)!=ESP_OK)return false;
    if(esp_netif_init()!=ESP_OK)return false;
    auto rc=esp_event_loop_create_default();if(rc!=ESP_OK && rc!=ESP_ERR_INVALID_STATE)return false;
    netif=esp_netif_create_default_wifi_sta();if(!netif)return false;
    esp_event_handler_register(WIFI_EVENT,ESP_EVENT_ANY_ID,wifi_event,nullptr);
    esp_event_handler_register(IP_EVENT,IP_EVENT_STA_GOT_IP,wifi_event,nullptr);
    wifi_init_config_t cfg=WIFI_INIT_CONFIG_DEFAULT();
    cfg.nvs_enable=0;
    if(esp_wifi_init(&cfg)!=ESP_OK)return false;
    if(esp_wifi_set_storage(WIFI_STORAGE_RAM)!=ESP_OK || esp_wifi_set_mode(WIFI_MODE_STA)!=ESP_OK || esp_wifi_start()!=ESP_OK)return false;
    wifi_started=true;return true;
}
bool connect_wifi() {
    if(!init_wifi() || !settings.ssid[0])return false;
    esp_wifi_disconnect();xEventGroupClearBits(wifi_events,1);
    wifi_config_t cfg{};
    memcpy(cfg.sta.ssid,settings.ssid,strlen(settings.ssid));
    memcpy(cfg.sta.password,settings.password,strlen(settings.password));
    cfg.sta.pmf_cfg.capable=true;
    if(esp_wifi_set_config(WIFI_IF_STA,&cfg)!=ESP_OK || esp_wifi_connect()!=ESP_OK)return false;
    bool ok=(xEventGroupWaitBits(wifi_events,1,pdFALSE,pdTRUE,pdMS_TO_TICKS(30000))&1)!=0;
    if(ok){ reconnects=0;retry_at=esp_timer_get_time()+5000000; }
    return ok;
}
bool sync_time() {
    static bool initialized=false;
    if(!initialized){esp_sntp_config_t cfg=ESP_NETIF_SNTP_DEFAULT_CONFIG("pool.ntp.org");if(esp_netif_sntp_init(&cfg)!=ESP_OK)return false;initialized=true;}
    if(time(nullptr)>1735689600)return true;
    return esp_netif_sntp_sync_wait(pdMS_TO_TICKS(20000))==ESP_OK && time(nullptr)>1735689600;
}
struct Response { String data; bool overflow=false; };
esp_err_t http_event(esp_http_client_event_t* event) {
    auto* response=static_cast<Response*>(event->user_data);
    if(event->event_id==HTTP_EVENT_ON_DATA){
        if(response->data.size()+event->data_len>16384){response->overflow=true;return ESP_FAIL;}
        response->data.append(static_cast<const char*>(event->data),event->data_len);
    }
    return ESP_OK;
}
int request(const char* path,const char* body,Response& response,bool authenticated=false,esp_http_client_method_t method=HTTP_METHOD_GET) {
    if(!(xEventGroupGetBits(wifi_events)&1) || !sync_time())return -1;
    String url=String(settings.api)+path;
    esp_http_client_config_t cfg{};cfg.url=url.c_str();cfg.crt_bundle_attach=esp_crt_bundle_attach;
    cfg.timeout_ms=15000;cfg.disable_auto_redirect=true;cfg.event_handler=http_event;cfg.user_data=&response;
    auto client=esp_http_client_init(&cfg);if(!client)return -1;
    if(method!=HTTP_METHOD_GET)esp_http_client_set_method(client,method);
    if(body){esp_http_client_set_method(client,method==HTTP_METHOD_GET?HTTP_METHOD_POST:method);esp_http_client_set_header(client,"Content-Type","application/json");esp_http_client_set_post_field(client,body,strlen(body));}
    if(authenticated){String auth="Bearer "+access;esp_http_client_set_header(client,"Authorization",auth.c_str());wipe(auth.data(),auth.size());}
    int result=esp_http_client_perform(client)==ESP_OK && !response.overflow?esp_http_client_get_status_code(client):-1;
    esp_http_client_cleanup(client);return result;
}
String json_string(cJSON* object,const char* name) { auto* v=cJSON_GetObjectItemCaseSensitive(object,name);return cJSON_IsString(v)?v->valuestring:""; }
bool health() {
    Response response; if(request("/health/ready",nullptr,response)!=200)return false;
    auto* data=cJSON_Parse(response.data.c_str());bool ok=json_string(data,"status")=="ready";cJSON_Delete(data);
    if(!ok)return false;
    response={};if(request("/api/v1/system/status",nullptr,response)!=200)return false;
    data=cJSON_Parse(response.data.c_str());ok=json_string(data,"api_version")=="v1";
    auto* caps=cJSON_GetObjectItemCaseSensitive(data,"capabilities");bool auth=false;cJSON* item;
    cJSON_ArrayForEach(item,caps)if(cJSON_IsString(item) && strcmp(item->valuestring,"auth")==0)auth=true;
    cJSON_Delete(data);return ok&&auth;
}
String body_for(const char* a,const char* av,const char* b=nullptr,const char* bv=nullptr,bool device=false) {
    auto* object=cJSON_CreateObject();cJSON_AddStringToObject(object,a,av);
    if(b)cJSON_AddStringToObject(object,b,bv);
    if(device)cJSON_AddStringToObject(object,"device_id",device_id);
    char* raw=cJSON_PrintUnformatted(object);String out=raw?raw:"";
    if(raw){wipe(raw,strlen(raw));cJSON_free(raw);}cJSON_Delete(object);return out;
}
bool tokens(Response& response,bool& change) {
    auto* data=cJSON_Parse(response.data.c_str());auto a=json_string(data,"access_token"),r=json_string(data,"refresh_token");
    change=cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(data,"must_change_password"));cJSON_Delete(data);
    if(a.size()<40 || a.size()>256 || r.size()<40 || r.size()>256)return false;
    clear_session();access=a;refresh_token=r;wipe(a.data(),a.size());wipe(r.data(),r.size());
    xSemaphoreTake(view_lock,portMAX_DELAY);view.authenticated=true;xSemaphoreGive(view_lock);refresh_at=esp_timer_get_time()+600000000;return true;
}
void show_session() {
    Response response;if(request("/api/v1/auth/me",nullptr,response,true)!=200){clear_session();publish(Page::Login,"Sessão expirada. Entre novamente.");return;}
    auto* data=cJSON_Parse(response.data.c_str());String msg="Usuário: "+json_string(data,"username")+"\nDispositivo: "+device_id+"\nPerfis: ";cJSON* item;
    bool admin=false;
    cJSON_ArrayForEach(item,cJSON_GetObjectItemCaseSensitive(data,"permissions"))if(cJSON_IsString(item)&&strcmp(item->valuestring,"users.create")==0)admin=true;
    if(!settings.setup_complete && (!admin || cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(data,"must_change_password")))){
        cJSON_Delete(data);clear_session();publish(Page::Login,"Primeira instalação: entre com o administrador ERP após trocar a senha inicial.");return;
    }
    if(!settings.setup_complete){settings.setup_complete=true;if(!save()){settings.setup_complete=false;cJSON_Delete(data);clear_session();publish(Page::Login,"Não foi possível concluir a instalação em memória persistente.");return;}}
    cJSON_ArrayForEach(item,cJSON_GetObjectItemCaseSensitive(data,"roles"))if(cJSON_IsString(item))msg+=String(item->valuestring)+" ";
    String permissions;
    cJSON_ArrayForEach(item,cJSON_GetObjectItemCaseSensitive(data,"permissions"))if(cJSON_IsString(item))permissions+=String(item->valuestring)+" ";
    msg+="\nPermissões: "+permissions;
    xSemaphoreTake(view_lock,portMAX_DELAY);snprintf(view.permissions,sizeof(view.permissions),"%s",permissions.c_str());xSemaphoreGive(view_lock);
    cJSON_Delete(data);xSemaphoreTake(view_lock,portMAX_DELAY);snprintf(view.identity,sizeof(view.identity),"%s",msg.c_str());xSemaphoreGive(view_lock);publish(Page::Session,msg.c_str());
}
int product_transport(const char* method,const char* path,const char* body,char* output,size_t capacity){
    output[0]=0;Response response;
    if(access.empty())return 401;
    if(esp_timer_get_time()>=refresh_at){
        auto body=body_for("refresh_token",refresh_token.c_str(),nullptr,nullptr,true);Response refreshed;bool change=false;
        int status=request("/api/v1/auth/refresh",body.c_str(),refreshed);wipe(body.data(),body.size());
        if(status!=200 || !tokens(refreshed,change)){clear_session();publish(Page::Login,"Sessão expirada. Entre novamente.");return 401;}
    }
    auto verb=strcmp(method,"PUT")==0?HTTP_METHOD_PUT:strcmp(method,"DELETE")==0?HTTP_METHOD_DELETE:strcmp(method,"POST")==0?HTTP_METHOD_POST:HTTP_METHOD_GET;
    int code=request(path,body,response,true,verb);
    if(response.data.size()>=capacity)return -1;
    snprintf(output,capacity,"%s",response.data.c_str());
    if(code==401){clear_session();publish(Page::Login,"Sessão expirada. Entre novamente.");}
    return code;
}
void worker(void*) {
    // P4 has no local RF entropy source. ADC is reserved for RNG in this profile.
    bootloader_random_enable();
    uint8_t test_salt[16],test_key[32]{};for(unsigned i=0;i<16;++i)test_salt[i]=i;
    constexpr uint8_t expected[]={0xac,0xc5,0xf4,0x7b,0x58,0xd5,0x90,0x16,0xf8,0x8b,0xed,0xc0,0xce,0x41,0x87,0xb6,0x55,0x18,0xf2,0xad,0x96,0x2b,0xe5,0xf1,0xe0,0x5d,0x20,0x62,0xe1,0xb9,0x47,0x2e};
    bool crypto_ok=derive("TAB5-crypto-selftest",test_salt,test_key,2048)&&memcmp(test_key,expected,32)==0;
    Envelope test{};Settings plain{},opened{};snprintf(plain.ssid,sizeof(plain.ssid),"crypto-test");
    crypto_ok=crypto_ok&&crypt(true,test_key,test,plain)&&crypt(false,test_key,test,opened)&&memcmp(&plain,&opened,sizeof(plain))==0;
    test.tag[0]^=1;crypto_ok=crypto_ok&&!crypt(false,test_key,test,opened);wipe(test_key,32);
    if(!crypto_ok){publish(Page::Unlock,"Autoteste criptográfico falhou. Provisionamento bloqueado.");vTaskDelete(nullptr);return;}
    if(!card_ready){publish(Page::Unlock,"microSD necessário. Insira um cartão gravável e reinicie. Nenhuma configuração será salva na memória interna.",true);vTaskDelete(nullptr);return;}
    uint8_t theme=0;
    auto theme_rc=load_settings_file("/sdcard/ERP/config/theme.bin",&theme,sizeof(theme));
    if(theme_rc==FileRead::Found && theme<=1){xSemaphoreTake(view_lock,portMAX_DELAY);view.light=theme==1;xSemaphoreGive(view_lock);}
    auto rc=load_settings_file(settings_path,&envelope,sizeof(envelope));
    if(rc==FileRead::Missing){
        uint8_t random[24];random_bytes(random,sizeof(random));
        constexpr char alphabet[]="0123456789";
        xSemaphoreTake(view_lock,portMAX_DELAY);for(unsigned i=0;i<4;++i)view.generated[i]=alphabet[random[i]% (sizeof(alphabet)-1)];view.generated[4]=0;xSemaphoreGive(view_lock);wipe(random,sizeof(random));
        publish(Page::Provision,"Primeiro boot. Guarde a senha local sugerida em local seguro.");
    }else if(rc!=FileRead::Found || envelope.format!=1){publish(Page::Unlock,"Configuração inválida. Recuperação física necessária; nenhum dado apagado.");vTaskDelete(nullptr);return;}
    else publish(Page::Unlock,"Desbloqueie a rede com a senha do admin-local.");
    int64_t probe_at=0;
    for(;;){
        if(!access.empty()){
            char permissions[2048];xSemaphoreTake(view_lock,portMAX_DELAY);snprintf(permissions,sizeof(permissions),"%s",view.permissions);xSemaphoreGive(view_lock);
            if(products_handle_next(permissions,settings.api,(xEventGroupGetBits(wifi_events)&1)!=0,product_transport))continue;
            if(contacts_handle_next(permissions,(xEventGroupGetBits(wifi_events)&1)!=0,product_transport))continue;
            if(inventory_handle_next(permissions,(xEventGroupGetBits(wifi_events)&1)!=0,product_transport,inventory_journal))continue;
            if(sales_handle_next(permissions,(xEventGroupGetBits(wifi_events)&1)!=0,product_transport,sale_journal))continue;
        }
        Command cmd{};
        if(xQueueReceive(commands,&cmd,pdMS_TO_TICKS(1000))!=pdTRUE){
            if(unlocked && wifi_started && settings.ssid[0] && !(xEventGroupGetBits(wifi_events)&1) && esp_timer_get_time()>=retry_at){
                esp_wifi_connect();reconnects=std::min(reconnects+1,6u);retry_at=esp_timer_get_time()+(int64_t(1u<<reconnects)*1000000);
            }
            if(!access.empty() && esp_timer_get_time()>=probe_at){
                xSemaphoreTake(view_lock,portMAX_DELAY);view.checking=true;xSemaphoreGive(view_lock);
                bool ready=health();xSemaphoreTake(view_lock,portMAX_DELAY);view.api_ready=ready;view.checking=false;xSemaphoreGive(view_lock);
                probe_at=esp_timer_get_time()+30000000;
            }
            if(!refresh_token.empty() && esp_timer_get_time()>=refresh_at){
                auto body=body_for("refresh_token",refresh_token.c_str(),nullptr,nullptr,true);Response response;bool change=false;
                int code=request("/api/v1/auth/refresh",body.c_str(),response);wipe(body.data(),body.size());
                if(code!=200 || !tokens(response,change)){clear_session();publish(Page::Login,"Sessão encerrada. Entre novamente.");}
                else {show_session();}
                wipe(response.data.data(),response.data.size());
            }continue;
        }
        Page current; xSemaphoreTake(view_lock,portMAX_DELAY);current=view.page;xSemaphoreGive(view_lock);
        publish(current,"Aguarde...",true);
        if(cmd.action==Action::Provision || cmd.action==Action::Unlock){
            if(esp_timer_get_time()<lock_until){publish(current,"Muitas tentativas. Aguarde antes de tentar novamente.");wipe(&cmd,sizeof(cmd));continue;}
            bool initial=cmd.action==Action::Provision;
            if(initial && envelope.format==1){publish(current,"Administrador local já configurado.");wipe(&cmd,sizeof(cmd));continue;}
            if(pending_operation_exists()){publish(Page::Configure,"Resolva a operação pendente em Vendas/Estoque antes de alterar a senha local.");wipe(&cmd,sizeof(cmd));continue;}
            uint8_t candidate[32]{};Settings opened{};
            bool ok=strlen(cmd.fields[0])>= (initial?4u:1u);
            if(initial && ok){random_bytes(envelope.salt,16);}
            ok=ok && derive(cmd.fields[0],envelope.salt,candidate);
            if(!initial)ok=ok&&crypt(false,candidate,envelope,opened);
            if(ok){memcpy(key,candidate,32);unlocked=true;failures=0;settings=opened;
                xSemaphoreTake(view_lock,portMAX_DELAY);wipe(view.generated,sizeof(view.generated));xSemaphoreGive(view_lock);
                if(initial){envelope.format=1;snprintf(settings.api,sizeof(settings.api),"https://tab5api.ampere.diadiatech.com.br");ok=save();}
                if(!ok){unlocked=false;wipe(key,sizeof(key));if(initial)wipe(&envelope,sizeof(envelope));publish(current,"Não foi possível salvar as configurações. Confira o microSD.");}
                else if((config_view(),settings.ssid[0]) && connect_wifi() && health())publish(Page::Login,"Rede e API disponíveis. Entre com seu usuário ERP.");
                else publish(Page::Configure,"Configure a rede e teste a conexão com a API.");
            }else{++failures;lock_until=esp_timer_get_time()+int64_t(std::min(1u<<std::min(failures,6u),60u))*1000000;publish(current,"Senha inválida ou configuração não autenticada. Aguarde e tente novamente.");}
            wipe(candidate,sizeof(candidate));wipe(&opened,sizeof(opened));
        }else if(!unlocked){publish(Page::Unlock,"Desbloqueio local necessário.");}
        else if(cmd.action==Action::Save){
            String url=cmd.fields[2];while(!url.empty()&&url.back()=='/')url.pop_back();
            bool valid=strlen(cmd.fields[0])>0 && strlen(cmd.fields[0])<=32 && strlen(cmd.fields[1])<=64 && url.size()<sizeof(settings.api) && url.rfind("https://",0)==0 && url.size()>8 && url.find_first_of(" @?#\r\n") == String::npos;
            if(!valid)publish(Page::Configure,"Confira SSID, senha e URL HTTPS da API.");
            else if(pending_operation_exists() && url != settings.api)publish(Page::Configure,"Resolva a operação pendente em Vendas/Estoque antes de alterar a API.");
            else{clear_session();memcpy(settings.ssid,cmd.fields[0],strlen(cmd.fields[0])+1);memcpy(settings.password,cmd.fields[1],strlen(cmd.fields[1])+1);snprintf(settings.api,sizeof(settings.api),"%s",url.c_str());
                config_view();if(!save())publish(Page::Configure,"Falha ao salvar configuração.");
                else if(!connect_wifi())publish(Page::Configure,"Configuração salva. Wi-Fi indisponível; confira rede/senha e C6.");
                else if(!health())publish(Page::Configure,"Wi-Fi conectado. Falha de hora, DNS, TLS ou compatibilidade da API.");
                else{esp_netif_ip_info_t ip{};esp_netif_get_ip_info(netif,&ip);char msg[192];snprintf(msg,sizeof(msg),"Configuração salva. IP: " IPSTR " | gateway: " IPSTR "\nAPI e banco disponíveis.",IP2STR(&ip.ip),IP2STR(&ip.gw));publish(Page::Login,msg);}
            }
        }else if(cmd.action==Action::Scan){
            if(!init_wifi())publish(Page::Configure,"Não foi possível iniciar o rádio C6.");
            else{wifi_scan_config_t cfg{};cfg.show_hidden=false;cfg.scan_type=WIFI_SCAN_TYPE_ACTIVE;
                if(esp_wifi_scan_start(&cfg,true)!=ESP_OK)publish(Page::Configure,"Pesquisa de redes indisponível.");
                else{wifi_ap_record_t records[8]{};uint16_t count=8;esp_wifi_scan_get_ap_records(&count,records);String msg="Redes: ",options="Selecione a rede";for(unsigned i=0;i<count;++i){char row[64];snprintf(row,sizeof(row),"\n%.32s (%d dBm)",records[i].ssid,records[i].rssi);msg+=row;options+="\n";options+=reinterpret_cast<const char*>(records[i].ssid);}
                    xSemaphoreTake(view_lock,portMAX_DELAY);snprintf(view.networks,sizeof(view.networks),"%s",options.c_str());xSemaphoreGive(view_lock);publish(Page::Configure,msg.c_str());}
            }
        }else if(cmd.action==Action::Login){
            auto body=body_for("username",cmd.fields[0],"password",cmd.fields[1],true);Response response;
            int code=request("/api/v1/auth/login",body.c_str(),response);wipe(body.data(),body.size());bool change=false;
            if(code==200 && tokens(response,change)){if(change)publish(Page::Password,"Altere a senha inicial do ERP para continuar.");else show_session();}
            else{clear_session();publish(Page::Login,code==429?"Muitas tentativas. Aguarde 15 minutos.":"Login indisponível ou credenciais inválidas.");}
            wipe(response.data.data(),response.data.size());
        }else if(cmd.action==Action::Password){
            auto body=body_for("current_password",cmd.fields[0],"new_password",cmd.fields[1]);Response response;
            int code=request("/api/v1/auth/change-password",body.c_str(),response,true);wipe(body.data(),body.size());
            if(code==204){clear_session();publish(Page::Login,"Senha alterada e sessões revogadas. Entre novamente.");}else if(code==401)publish(Page::Password,"Senha atual incorreta ou sessão expirada. Confira a senha ou entre novamente.");
            else if(code==422)publish(Page::Password,"Nova senha inválida. Use pelo menos 8 caracteres e uma senha diferente da atual. Confira se a API foi atualizada.");
            else if(code<=0)publish(Page::Password,"Sem resposta da API. Confira a rede e tente novamente.");
            else publish(Page::Password,"API recusou a alteração. Tente entrar novamente.");
        }else if(cmd.action==Action::Logout){Response response;int code=request("/api/v1/auth/logout","",response,true);clear_session();publish(Page::Login,code==204?"Sessão encerrada.":"Sessão removida deste dispositivo; revogação remota não confirmada.");}
        else if(cmd.action==Action::LocalPassword){
            if(pending_operation_exists()){publish(Page::Configure,"Resolva a operação pendente em Vendas/Estoque antes de alterar a senha local.");wipe(&cmd,sizeof(cmd));continue;}
            uint8_t candidate[32]{};Settings opened{};
            bool ok=derive(cmd.fields[0],envelope.salt,candidate)&&crypt(false,candidate,envelope,opened)&&strlen(cmd.fields[1])>=4;
            Envelope old=envelope;uint8_t old_key[32];memcpy(old_key,key,32);
            if(ok){random_bytes(envelope.salt,16);ok=derive(cmd.fields[1],envelope.salt,key)&&save();}
            if(!ok){envelope=old;memcpy(key,old_key,32);}
            wipe(candidate,32);wipe(old_key,32);wipe(&opened,sizeof(opened));publish(Page::Configure,ok?"Senha local alterada; guarde-a em local seguro.":"Confira a senha local atual e a nova senha (4 caracteres).");
        }else if(cmd.action==Action::Forget){clear_session();if(wifi_started)esp_wifi_disconnect();wipe(settings.ssid,sizeof(settings.ssid));wipe(settings.password,sizeof(settings.password));publish(Page::Configure,save()?"Rede esquecida.":"Falha ao salvar alteração.");}
        else if(cmd.action==Action::Home){if(!access.empty())show_session();else publish(Page::Login,"Entre novamente para abrir o menu.");}
        else if(cmd.action==Action::Theme){
            uint8_t theme; xSemaphoreTake(view_lock,portMAX_DELAY);theme=view.light?0:1;xSemaphoreGive(view_lock);
            bool ok=save_settings_file("/sdcard/ERP/config/theme.bin",&theme,sizeof(theme));
            if(ok){xSemaphoreTake(view_lock,portMAX_DELAY);view.light=theme==1;xSemaphoreGive(view_lock);}
            publish(Page::Session,ok?"Tema salvo no microSD.":"Falha ao salvar tema. Confira o microSD.");
        }
        else if(cmd.action==Action::Lock){clear_session();if(wifi_started)esp_wifi_disconnect();unlocked=false;wipe(key,32);wipe(&settings,sizeof(settings));publish(Page::Unlock,"Configuração bloqueada. Entre como admin-local.");}
        else if(cmd.action==Action::Reset){
            if(pending_operation_exists())publish(Page::Configure,"Resolva a operação pendente em Vendas/Estoque antes de restaurar o Tab5.");
            else if(!erase_settings_files("/sdcard/ERP/config/theme.bin") || !erase_settings_files(settings_path))publish(Page::Configure,"Falha ao remover configuração. Nenhum reinício executado.");
            else{clear_session();wipe(key,32);wipe(&settings,sizeof(settings));wipe(&envelope,sizeof(envelope));wipe(&cmd,sizeof(cmd));esp_restart();}
        }
        wipe(&cmd,sizeof(cmd));
    }
}
void focus_field(lv_event_t* e){lv_keyboard_set_textarea(keyboard,lv_event_get_target_obj(e));}
void reveal_passwords(lv_event_t*){revealed=!revealed;for(unsigned i=0;i<4;++i)if(secret_fields[i])lv_textarea_set_password_mode(fields[i],!revealed);}
void diagnostics(lv_event_t*){
    bool showing=!lv_obj_has_flag(panel,LV_OBJ_FLAG_HIDDEN);
    if(showing){lv_obj_add_flag(panel,LV_OBJ_FLAG_HIDDEN);lv_obj_remove_flag(return_button,LV_OBJ_FLAG_HIDDEN);}
    else{lv_obj_remove_flag(panel,LV_OBJ_FLAG_HIDDEN);lv_obj_add_flag(return_button,LV_OBJ_FLAG_HIDDEN);}
    auto* selected=showing?diagnostic_group:input_group;lv_group_set_default(selected);
    for(auto* input=lv_indev_get_next(nullptr);input;input=lv_indev_get_next(input))if(lv_indev_get_type(input)==LV_INDEV_TYPE_KEYPAD)lv_indev_set_group(input,selected);
}
void selected_network(lv_event_t*){char ssid[64];if(lv_dropdown_get_selected(networks)>0){lv_dropdown_get_selected_str(networks,ssid,sizeof(ssid));lv_textarea_set_text(fields[0],ssid);}}
void pressed(lv_event_t* e){
    auto action=static_cast<Action>(reinterpret_cast<uintptr_t>(lv_event_get_user_data(e)));
    Command cmd{};cmd.action=action;
    for(unsigned i=0;i<4;++i){const char* text=lv_textarea_get_text(fields[i]);if(strlen(text)>=sizeof(cmd.fields[i])){lv_label_set_text(message,"Campo muito longo em bytes. Reduza o texto.");wipe(&cmd,sizeof(cmd));return;}snprintf(cmd.fields[i],sizeof(cmd.fields[i]),"%s",text);if(secret_fields[i])lv_textarea_set_text(fields[i],"");}
    if(xQueueSend(commands,&cmd,0)!=pdTRUE)lv_label_set_text(message,"Operação em andamento.");
    wipe(&cmd,sizeof(cmd));
}
void navigate_to(lv_event_t* e){auto target=static_cast<Page>(reinterpret_cast<uintptr_t>(lv_event_get_user_data(e)));publish(target,"Preencha os campos para continuar.");}
void products_home(){browsing_inventory=false;browsing_sales=false;browsing_contacts=false;browsing_products=false;publish(Page::Session,"Menu principal.");}
void dashboard_action(DashboardAction action){
    if(action==DashboardAction::Inventory){
        xSemaphoreTake(view_lock,portMAX_DELAY);View snapshot=view;xSemaphoreGive(view_lock);
        browsing_inventory=true;dashboard_hide();inventory_open(snapshot.permissions,snapshot.light);return;
    }
    if(action==DashboardAction::Sales){
        static View snapshot;xSemaphoreTake(view_lock,portMAX_DELAY);snapshot=view;xSemaphoreGive(view_lock);
        browsing_sales=true;dashboard_hide();sales_open(snapshot.permissions,snapshot.light);return;
    }
    if(action==DashboardAction::Customers){
        static View snapshot;xSemaphoreTake(view_lock,portMAX_DELAY);snapshot=view;xSemaphoreGive(view_lock);
        browsing_contacts=true;dashboard_hide();contacts_open(snapshot.permissions,snapshot.light,!has_module_permission(snapshot.permissions,"customers.read"));return;
    }
    if(action==DashboardAction::Products){
        static View snapshot;xSemaphoreTake(view_lock,portMAX_DELAY);snapshot=view;xSemaphoreGive(view_lock);
        browsing_products=true;dashboard_hide();products_open(snapshot.permissions,snapshot.light);return;
    }
    if(action==DashboardAction::Network){publish(Page::Configure,"Configure a rede e o servidor.");return;}
    if(action==DashboardAction::Password){publish(Page::Password,"Informe a senha atual e a nova senha ERP.");return;}
    Command cmd{};cmd.action=action==DashboardAction::Logout?Action::Logout:action==DashboardAction::Lock?Action::Lock:Action::Theme;
    if(xQueueSend(commands,&cmd,0)!=pdTRUE)publish(Page::Session,"Operação em andamento.");
}
void render(lv_timer_t*) {
    static View next; xSemaphoreTake(view_lock,portMAX_DELAY);next=view;xSemaphoreGive(view_lock);
    dashboard_status((xEventGroupGetBits(wifi_events)&1)!=0,next.api_ready,next.busy||next.checking,next.light);
    if(next.serial==rendered_serial)return;
    if(next.page==Page::Session && next.authenticated){
        lv_obj_add_flag(panel,LV_OBJ_FLAG_HIDDEN);lv_obj_add_flag(home_button,LV_OBJ_FLAG_HIDDEN);
        if(!browsing_products&&!browsing_contacts&&!browsing_sales&&!browsing_inventory)dashboard_show(next.identity,next.permissions,next.light,next.busy || strcmp(next.message,next.identity)==0?"":next.message);
        rendered=next.page;rendered_serial=next.serial;return;
    }
    browsing_products=false;browsing_contacts=false;browsing_sales=false;browsing_inventory=false;inventory_hide();sales_hide(true);products_hide();contacts_hide();dashboard_hide();lv_obj_remove_flag(panel,LV_OBJ_FLAG_HIDDEN);
    if(next.authenticated){lv_obj_remove_flag(home_button,LV_OBJ_FLAG_HIDDEN);}
    else lv_obj_add_flag(home_button,LV_OBJ_FLAG_HIDDEN);
    lv_group_set_default(input_group);
    for(auto* input=lv_indev_get_next(nullptr);input;input=lv_indev_get_next(input))if(lv_indev_get_type(input)==LV_INDEV_TYPE_KEYPAD)lv_indev_set_group(input,input_group);
    bool page_changed=next.page!=rendered || rendered_serial==0;rendered=next.page;rendered_serial=next.serial;
    lv_label_set_text(message,next.message);
    if(next.page==Page::Configure){lv_obj_remove_flag(networks,LV_OBJ_FLAG_HIDDEN);if(next.networks[0])lv_dropdown_set_options(networks,next.networks);}
    else lv_obj_add_flag(networks,LV_OBJ_FLAG_HIDDEN);
    for(auto button:buttons){if(next.busy)lv_obj_add_state(button,LV_STATE_DISABLED);else lv_obj_remove_state(button,LV_STATE_DISABLED);}
    if(!page_changed)return;
    lv_group_remove_all_objs(input_group);
    revealed=false;
    for(unsigned i=0;i<4;++i){lv_obj_add_flag(fields[i],LV_OBJ_FLAG_HIDDEN);lv_obj_add_flag(field_labels[i],LV_OBJ_FLAG_HIDDEN);lv_obj_add_flag(buttons[i],LV_OBJ_FLAG_HIDDEN);lv_obj_remove_event_cb(buttons[i],pressed);lv_obj_remove_event_cb(buttons[i],navigate_to);lv_textarea_set_text(fields[i],"");}
    auto field=[&](unsigned i,const char* label,bool secret,const char* initial=""){
        secret_fields[i]=secret;lv_label_set_text(field_labels[i],label);lv_obj_remove_flag(field_labels[i],LV_OBJ_FLAG_HIDDEN);lv_obj_remove_flag(fields[i],LV_OBJ_FLAG_HIDDEN);lv_textarea_set_password_mode(fields[i],secret);lv_textarea_set_text(fields[i],initial);lv_group_add_obj(input_group,fields[i]);};
    auto button=[&](unsigned i,const char* label,Action action){auto text=lv_obj_get_child(buttons[i],0);lv_label_set_text(text,label);lv_obj_center(text);lv_obj_remove_flag(buttons[i],LV_OBJ_FLAG_HIDDEN);lv_obj_add_event_cb(buttons[i],pressed,LV_EVENT_CLICKED,reinterpret_cast<void*>(static_cast<uintptr_t>(action)));lv_group_add_obj(input_group,buttons[i]);};
    auto navigation=[&](unsigned i,const char* label,Page page){lv_label_set_text(lv_obj_get_child(buttons[i],0),label);lv_obj_center(lv_obj_get_child(buttons[i],0));lv_obj_remove_flag(buttons[i],LV_OBJ_FLAG_HIDDEN);lv_obj_add_event_cb(buttons[i],navigate_to,LV_EVENT_CLICKED,reinterpret_cast<void*>(static_cast<uintptr_t>(page)));lv_group_add_obj(input_group,buttons[i]);};
    switch(next.page){
    case Page::Provision:lv_label_set_text(heading,"TAB5 ERP | Primeiro boot: admin-local");field(0,"Senha local (mínimo 4 caracteres)",false,next.generated);button(0,"Criar admin-local",Action::Provision);break;
    case Page::Unlock:lv_label_set_text(heading,"TAB5 ERP | Desbloqueio local");field(0,"Senha do admin-local",true);button(0,"Desbloquear",Action::Unlock);break;
    case Page::Configure:lv_label_set_text(heading,"TAB5 ERP | Wi-Fi e servidor");field(0,"SSID",false,next.ssid);field(1,"Senha Wi-Fi",true);field(2,"URL HTTPS",false,next.api[0]?next.api:"https://tab5api.ampere.diadiatech.com.br");button(0,"Salvar e conectar",Action::Save);button(1,"Pesquisar redes",Action::Scan);navigation(2,"Senha local",Page::LocalPassword);navigation(3,"Esquecer rede",Page::ConfirmForget);break;
    case Page::Login:lv_label_set_text(heading,"TAB5 ERP | Login ERP");field(0,"Usuário ERP",false);field(1,"Senha ERP",true);button(0,"Entrar",Action::Login);navigation(1,"Configurar rede",Page::Configure);button(2,"Bloquear",Action::Lock);break;
    case Page::Password:lv_label_set_text(heading,"TAB5 ERP | Alterar senha inicial ERP");field(0,"Senha atual ERP",true);field(1,"Nova senha ERP (mínimo 8)",true);button(0,"Alterar senha ERP",Action::Password);button(1,"Sair",Action::Logout);break;
    case Page::Session:lv_label_set_text(heading,"TAB5 ERP | Sessão autenticada");button(0,"Sair",Action::Logout);navigation(1,"Alterar senha ERP",Page::Password);navigation(2,"Configurar rede",Page::Configure);button(3,"Bloquear",Action::Lock);break;
    case Page::LocalPassword:lv_label_set_text(heading,"TAB5 ERP | Alterar senha local");field(0,"Senha local atual",true);field(1,"Nova senha local",true);button(0,"Alterar senha local",Action::LocalPassword);navigation(1,"Voltar",Page::Configure);navigation(2,"Restaurar Tab5",Page::ConfirmReset);break;
    case Page::ConfirmForget:lv_label_set_text(heading,"Confirmar: esquecer a rede Wi-Fi?");button(0,"Confirmar exclusão",Action::Forget);navigation(1,"Cancelar",Page::Configure);break;
    case Page::ConfirmReset:lv_label_set_text(heading,"Confirmar: apagar senha local e configurações?");lv_label_set_text(message,"O Tab5 reiniciará no primeiro boot. Banco e usuários do servidor serão preservados.");button(0,"Apagar e reiniciar",Action::Reset);navigation(1,"Cancelar",Page::Configure);break;
    }
    if(next.page==Page::Configure)lv_group_add_obj(input_group,networks);
    if(next.authenticated)lv_group_add_obj(input_group,home_button);
    lv_keyboard_set_textarea(keyboard,next.page==Page::Session?nullptr:fields[0]);
}
}
void authentication_start(lv_display_t* display,bool sd_writable){
    card_ready=sd_writable;
    cJSON_Hooks hooks{json_allocate,json_release};cJSON_InitHooks(&hooks);
    view_lock=xSemaphoreCreateMutex();commands=xQueueCreate(1,sizeof(Command));wifi_events=xEventGroupCreate();
    uint8_t mac[6];esp_read_mac(mac,ESP_MAC_BASE);snprintf(device_id,sizeof(device_id),"tab5-%02x%02x%02x%02x%02x%02x",mac[0],mac[1],mac[2],mac[3],mac[4],mac[5]);
    panel=lv_obj_create(lv_display_get_screen_active(display));lv_obj_set_size(panel,1280,720);lv_obj_set_pos(panel,0,0);lv_obj_remove_flag(panel,LV_OBJ_FLAG_SCROLLABLE);lv_obj_set_style_pad_all(panel,16,0);
    heading=lv_label_create(panel);lv_obj_set_style_text_font(heading,&erp_font_pt_28,0);lv_obj_set_pos(heading,8,0);
    auto* message_box=lv_obj_create(panel);lv_obj_set_pos(message_box,8,46);lv_obj_set_size(message_box,1200,112);lv_obj_set_style_pad_all(message_box,0,0);
    message=lv_label_create(message_box);lv_obj_set_size(message,1180,LV_SIZE_CONTENT);lv_label_set_long_mode(message,LV_LABEL_LONG_WRAP);
    diagnostic_group=lv_group_get_default();input_group=lv_group_create();lv_group_set_default(input_group);
    for(unsigned i=0;i<4;++i){field_labels[i]=lv_label_create(panel);lv_obj_set_pos(field_labels[i],8+i*304,172);fields[i]=lv_textarea_create(panel);lv_obj_set_pos(fields[i],8+i*304,204);lv_obj_set_size(fields[i],288,54);lv_textarea_set_one_line(fields[i],true);lv_textarea_set_max_length(fields[i],159);lv_obj_add_event_cb(fields[i],focus_field,LV_EVENT_FOCUSED,nullptr);
        buttons[i]=lv_button_create(panel);lv_obj_set_pos(buttons[i],8+i*304,288);lv_obj_set_size(buttons[i],288,58);auto label=lv_label_create(buttons[i]);lv_obj_center(label);}
    keyboard=lv_keyboard_create(panel);lv_obj_set_pos(keyboard,8,412);lv_obj_set_size(keyboard,1200,256);
    auto* reveal=lv_button_create(panel);lv_obj_set_pos(reveal,8,352);lv_obj_set_size(reveal,240,44);lv_label_set_text(lv_label_create(reveal),"Mostrar/ocultar senha");lv_obj_add_event_cb(reveal,reveal_passwords,LV_EVENT_CLICKED,nullptr);
    auto* diag=lv_button_create(panel);lv_obj_set_pos(diag,1040,0);lv_obj_set_size(diag,176,44);lv_label_set_text(lv_label_create(diag),"Diagnóstico");lv_obj_add_event_cb(diag,diagnostics,LV_EVENT_CLICKED,nullptr);
    return_button=lv_button_create(lv_display_get_screen_active(display));lv_obj_set_pos(return_button,1060,24);lv_obj_set_size(return_button,184,44);lv_label_set_text(lv_label_create(return_button),"Voltar ao acesso");lv_obj_add_event_cb(return_button,diagnostics,LV_EVENT_CLICKED,nullptr);lv_obj_add_flag(return_button,LV_OBJ_FLAG_HIDDEN);
    networks=lv_dropdown_create(panel);lv_obj_set_pos(networks,8,260);lv_obj_set_size(networks,288,28);lv_dropdown_set_options(networks,"Pesquise redes");lv_obj_add_event_cb(networks,selected_network,LV_EVENT_VALUE_CHANGED,nullptr);
    for(auto* input=lv_indev_get_next(nullptr);input;input=lv_indev_get_next(input))if(lv_indev_get_type(input)==LV_INDEV_TYPE_KEYPAD)lv_indev_set_group(input,input_group);
    home_button=lv_button_create(panel);lv_obj_set_pos(home_button,824,0);lv_obj_set_size(home_button,204,44);lv_label_set_text(lv_label_create(home_button),"Menu principal");lv_obj_add_event_cb(home_button,pressed,LV_EVENT_CLICKED,reinterpret_cast<void*>(static_cast<uintptr_t>(Action::Home)));lv_obj_add_flag(home_button,LV_OBJ_FLAG_HIDDEN);
    dashboard_create(display,dashboard_action);
    products_create(display,products_home);
    contacts_create(display,products_home);
    sales_create(display,products_home);
    inventory_create(display,products_home);
    lv_timer_create(render,100,nullptr);
    auto style_button=[](lv_obj_t* button){lv_obj_set_style_bg_color(button,lv_color_hex(0x334155),LV_PART_MAIN);lv_obj_set_style_bg_color(button,lv_color_hex(0x475569),LV_PART_MAIN|LV_STATE_PRESSED);lv_obj_set_style_text_color(button,lv_color_hex(0xf8fafc),LV_PART_MAIN);auto* text=lv_obj_get_child(button,0);lv_obj_set_style_text_color(text,lv_color_hex(0xf8fafc),0);lv_obj_center(text);};
    for(auto* button:buttons)style_button(button);
    style_button(reveal);style_button(diag);style_button(return_button);style_button(home_button);
    for(auto* field:fields){lv_obj_set_style_bg_color(field,lv_color_hex(0x1e293b),0);lv_obj_set_style_text_color(field,lv_color_hex(0xf8fafc),0);}
    lv_obj_set_style_text_color(message,lv_color_hex(0xf8fafc),0);
    lv_obj_set_style_bg_color(message_box,lv_color_hex(0x1e293b),0);
    lv_obj_set_style_bg_color(networks,lv_color_hex(0x1e293b),0);
    lv_obj_set_style_text_color(networks,lv_color_hex(0xf8fafc),0);
    lv_obj_set_style_bg_color(keyboard,lv_color_hex(0x111827),LV_PART_MAIN);
    lv_obj_set_style_bg_color(keyboard,lv_color_hex(0x334155),LV_PART_ITEMS);
    lv_obj_set_style_text_color(keyboard,lv_color_hex(0xf8fafc),LV_PART_ITEMS);
    lv_obj_set_style_bg_color(panel,lv_color_hex(0x111827),0);lv_obj_set_style_text_color(panel,lv_color_hex(0xf8fafc),0);
    for(unsigned i=0;i<4;++i){lv_obj_add_flag(fields[i],LV_OBJ_FLAG_HIDDEN);lv_obj_add_flag(field_labels[i],LV_OBJ_FLAG_HIDDEN);lv_obj_add_flag(buttons[i],LV_OBJ_FLAG_HIDDEN);}
    publish(Page::Unlock,"Inicializando segurança. Aguarde...",true);
    render(nullptr);
    if(xTaskCreate(worker,"erp-auth",24576,nullptr,5,nullptr)!=pdPASS)publish(Page::Unlock,"Memória insuficiente para iniciar autenticação.");
}
}
