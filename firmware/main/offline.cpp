#include "offline.hpp"
#include "cJSON.h"
#include "settings_file.hpp"
#include "esp_heap_caps.h"
#include "esp_random.h"
#include "mbedtls/gcm.h"
#include "mbedtls/base64.h"
#include "mbedtls/sha256.h"
#include "mbedtls/platform_util.h"
#include <cstdio>
#include <cstring>
#include <sys/stat.h>
#include <dirent.h>
#ifndef TAB5_OFFLINE_DIRECTORY
#define TAB5_OFFLINE_DIRECTORY "/sdcard/ERP/offline"
#endif
namespace tab5 { namespace {
unsigned char local_key[32];bool ready=false;int current_user=0;std::string scope;
struct Envelope {unsigned magic,length;unsigned char iv[12],tag[16];};
static_assert(sizeof(Envelope)==36);
constexpr unsigned magic=0x3153464f,max_plain=16384;
bool transform(bool seal,const char* context,const unsigned char* input,size_t size,
               unsigned char* output,size_t capacity,size_t& length){
    if(!ready)return false;
    Envelope envelope{};if(seal){if(size>max_plain||capacity<size+sizeof(envelope))return false;envelope.magic=magic;envelope.length=size;esp_fill_random(envelope.iv,12);}
    else{if(size<sizeof(envelope))return false;memcpy(&envelope,input,sizeof(envelope));if(envelope.magic!=magic||envelope.length>max_plain||envelope.length+sizeof(envelope)!=size||envelope.length>=capacity)return false;}
    std::string aad="TAB5 offline v1:"+scope+":"+context;
    mbedtls_gcm_context ctx;mbedtls_gcm_init(&ctx);int rc=mbedtls_gcm_setkey(&ctx,MBEDTLS_CIPHER_ID_AES,local_key,256);
    if(!rc&&seal)rc=mbedtls_gcm_crypt_and_tag(&ctx,MBEDTLS_GCM_ENCRYPT,size,envelope.iv,12,reinterpret_cast<const unsigned char*>(aad.data()),aad.size(),input,output+sizeof(envelope),16,envelope.tag);
    if(!rc&&!seal)rc=mbedtls_gcm_auth_decrypt(&ctx,envelope.length,envelope.iv,12,reinterpret_cast<const unsigned char*>(aad.data()),aad.size(),envelope.tag,16,input+sizeof(envelope),output);
    mbedtls_gcm_free(&ctx);if(rc){mbedtls_platform_zeroize(output,capacity);return false;}
    if(seal){memcpy(output,&envelope,sizeof(envelope));length=size+sizeof(envelope);}else{length=envelope.length;output[length]=0;}return true;
}
}
void offline_configure(const unsigned char* key,const char* api,const char* device){offline_lock();memcpy(local_key,key,32);scope=std::string(api)+":"+device;ready=true;}
void offline_lock(){mbedtls_platform_zeroize(local_key,32);ready=false;current_user=0;scope.clear();}
std::string offline_scope(){unsigned char hash[32];mbedtls_sha256(reinterpret_cast<const unsigned char*>(scope.data()),scope.size(),hash,0);char hex[65];for(unsigned i=0;i<32;++i)snprintf(hex+i*2,3,"%02x",hash[i]);return hex;}
int offline_user(){return current_user;}void offline_set_user(int user){current_user=user;}
bool offline_seal(const char* context,const char* plain,char* output,size_t capacity){
    size_t bytes=strlen(plain)+sizeof(Envelope),length=0,encoded=0;auto* raw=static_cast<unsigned char*>(heap_caps_malloc(bytes,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));if(!raw)return false;
    bool ok=transform(true,context,reinterpret_cast<const unsigned char*>(plain),strlen(plain),raw,bytes,length)&&mbedtls_base64_encode(reinterpret_cast<unsigned char*>(output),capacity,&encoded,raw,length)==0;
    if(ok&&encoded<capacity)output[encoded]=0;else ok=false;mbedtls_platform_zeroize(raw,bytes);heap_caps_free(raw);return ok;
}
bool offline_open(const char* context,const char* sealed,char* output,size_t capacity){
    size_t bytes=strlen(sealed),length=0,opened=0;auto* raw=static_cast<unsigned char*>(heap_caps_malloc(bytes?bytes:1,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));if(!raw)return false;
    bool ok=mbedtls_base64_decode(raw,bytes,&length,reinterpret_cast<const unsigned char*>(sealed),bytes)==0&&transform(false,context,raw,length,reinterpret_cast<unsigned char*>(output),capacity,opened);
    if(!ok&&capacity){output[0]=0;}
    mbedtls_platform_zeroize(raw,bytes);heap_caps_free(raw);return ok;
}
int offline_blob(const char* operation,const char* name,int user,char* data,size_t capacity){
    if(!ready||user<0||capacity>max_plain+1)return -1;
    mkdir(TAB5_OFFLINE_DIRECTORY,0755);std::string context=std::string(name)+":"+std::to_string(user);
    std::string path=std::string(TAB5_OFFLINE_DIRECTORY)+"/"+std::string(name)+"-"+std::to_string(user)+".enc";
    if(!strcmp(operation,"clear"))return erase_settings_files(path)?1:-1;
    size_t encoded_capacity=(max_plain+sizeof(Envelope))*2+1;auto* encoded=static_cast<char*>(heap_caps_malloc(encoded_capacity,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));if(!encoded)return -1;int result=-1;
    if(!strcmp(operation,"save")){if(offline_seal(context.c_str(),data,encoded,encoded_capacity)&&save_settings_file(path,encoded,strlen(encoded)+1))result=1;}
    else{FILE* f=fopen(path.c_str(),"rb");if(!f&&errno==ENOENT)f=fopen((path+".bak").c_str(),"rb");if(!f){result=errno==ENOENT?0:-1;}else{size_t n=fread(encoded,1,encoded_capacity,f);bool ok=n>0&&n<encoded_capacity&&encoded[n-1]==0&&fgetc(f)==EOF&&!ferror(f);ok=fclose(f)==0&&ok;if(ok&&offline_open(context.c_str(),encoded,data,capacity))result=1;}}
    mbedtls_platform_zeroize(encoded,encoded_capacity);heap_caps_free(encoded);return result;
}
bool offline_draft_exists(){DIR* dir=opendir(TAB5_OFFLINE_DIRECTORY);if(!dir)return errno!=ENOENT;bool found=false;while(auto* e=readdir(dir)){if(!strncmp(e->d_name,"draft-",6)){found=true;break;}}closedir(dir);return found;}
namespace {
const char* draft_text(cJSON* data,const char* field){auto* value=cJSON_GetObjectItemCaseSensitive(data,field);return cJSON_IsString(value)?value->valuestring:"";}
int draft_store(int user,cJSON* data,char* buffer){char* raw=cJSON_PrintUnformatted(data);bool ok=raw&&strlen(raw)<=max_plain;if(ok)snprintf(buffer,max_plain+1,"%s",raw);cJSON_free(raw);return ok?offline_blob("save","draft",user,buffer,max_plain+1):-1;}
}
int offline_draft_pending(int user,char* request,size_t capacity){auto* buffer=static_cast<char*>(heap_caps_calloc(1,max_plain+1,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));if(!buffer)return -1;int result=offline_blob("load","draft",user,buffer,max_plain+1);if(result==1){auto* data=cJSON_Parse(buffer);auto* format=cJSON_GetObjectItemCaseSensitive(data,"format");const char* pending=draft_text(data,"pending_request");if(!cJSON_IsNumber(format)||format->valueint!=1)result=-1;else if(!*pending)result=0;else if(strlen(pending)>=capacity)result=-1;else{auto* body=cJSON_Parse(pending);size_t key_size=strlen(draft_text(body,"idempotency_key"));if(!cJSON_IsObject(body)||key_size<16||key_size>64)result=-1;else snprintf(request,capacity,"%s",pending);cJSON_Delete(body);}cJSON_Delete(data);}mbedtls_platform_zeroize(buffer,max_plain+1);heap_caps_free(buffer);return result;}
int offline_draft_link(int user,const char* request){auto* buffer=static_cast<char*>(heap_caps_calloc(1,max_plain+1,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));if(!buffer)return -1;int result=offline_blob("load","draft",user,buffer,max_plain+1);if(result==1){auto* data=cJSON_Parse(buffer);const char* old=draft_text(data,"pending_request");if(!cJSON_IsObject(data)||(*old&&strcmp(old,request)))result=-1;else{cJSON_DeleteItemFromObjectCaseSensitive(data,"pending_request");cJSON_AddStringToObject(data,"pending_request",request);result=draft_store(user,data,buffer);}cJSON_Delete(data);}else result=-1;mbedtls_platform_zeroize(buffer,max_plain+1);heap_caps_free(buffer);return result;}
int offline_draft_settle(int user,const char* request,bool abandoned){auto* buffer=static_cast<char*>(heap_caps_calloc(1,max_plain+1,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));if(!buffer)return -1;int result=offline_blob("load","draft",user,buffer,max_plain+1);if(result==0)result=1;else if(result==1){auto* data=cJSON_Parse(buffer);if(!cJSON_IsObject(data))result=-1;else if(*draft_text(data,"pending_request")&&!strcmp(draft_text(data,"pending_request"),request)){if(abandoned){cJSON_DeleteItemFromObjectCaseSensitive(data,"pending_request");result=draft_store(user,data,buffer);}else result=offline_blob("clear","draft",user,buffer,max_plain+1);}cJSON_Delete(data);}mbedtls_platform_zeroize(buffer,max_plain+1);heap_caps_free(buffer);return result;}

}
