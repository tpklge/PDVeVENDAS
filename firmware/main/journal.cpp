#include "journal.hpp"
#include "settings_file.hpp"
#include "esp_heap_caps.h"
#include "esp_random.h"
#include "mbedtls/gcm.h"
#include "mbedtls/platform_util.h"
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <sys/stat.h>

namespace tab5 {
bool protected_record_exists(const char* path){
    if(!path)return true;
    if(access(path,F_OK)==0||errno!=ENOENT)return true;
    std::string backup=std::string(path)+".bak";
    return access(backup.c_str(),F_OK)==0||errno!=ENOENT;
}
namespace {
struct Pending { uint32_t format; int user; char api[160]; char device[32]; char request[4097]; };
struct Envelope { uint32_t format; uint8_t iv[12],tag[16],data[sizeof(Pending)]; };
static_assert(sizeof(Pending)==4300&&sizeof(Envelope)==4332,"Preserve v1 journal compatibility");
}
int protected_request(const char* operation,int user,char* request,size_t capacity,
                      const unsigned char* key,const char* api,const char* device,
                      const char* path,const char* aad){
    if(!operation||!request||!capacity||!key||!api||!device||!path||!aad||user<=0)return -1;
    const bool saving=!strcmp(operation,"save"),clearing=!strcmp(operation,"clear");
    if(!saving&&!clearing&&strcmp(operation,"load"))return -1;
    if(strlen(api)>=160||strlen(device)>=32)return -1;
    auto* plain=static_cast<Pending*>(heap_caps_calloc(1,sizeof(Pending),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
    auto* sealed=static_cast<Envelope*>(heap_caps_calloc(1,sizeof(Envelope),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
    int result=-1;
    if(plain&&sealed){
        bool readable=true;
        if(saving){
            size_t length=strnlen(request,capacity);
            readable=length>0&&length<capacity&&length<sizeof(plain->request);
            if(readable){plain->format=1;plain->user=user;strcpy(plain->api,api);strcpy(plain->device,device);memcpy(plain->request,request,length+1);sealed->format=1;esp_fill_random(sealed->iv,sizeof(sealed->iv));}
        }else{
            auto status=load_settings_file(path,sealed,sizeof(*sealed));
            readable=status==FileRead::Found&&sealed->format==1;
            if(status==FileRead::Missing)result=clearing?(erase_settings_files(path)?1:-1):0;
        }
        if(readable){
            mbedtls_gcm_context ctx;mbedtls_gcm_init(&ctx);
            int rc=mbedtls_gcm_setkey(&ctx,MBEDTLS_CIPHER_ID_AES,key,256);
            if(rc==0&&saving)rc=mbedtls_gcm_crypt_and_tag(&ctx,MBEDTLS_GCM_ENCRYPT,sizeof(*plain),sealed->iv,12,reinterpret_cast<const uint8_t*>(aad),strlen(aad)+1,reinterpret_cast<const uint8_t*>(plain),sealed->data,16,sealed->tag);
            if(rc==0&&!saving)rc=mbedtls_gcm_auth_decrypt(&ctx,sizeof(*plain),sealed->iv,12,reinterpret_cast<const uint8_t*>(aad),strlen(aad)+1,sealed->tag,16,sealed->data,reinterpret_cast<uint8_t*>(plain));
            mbedtls_gcm_free(&ctx);
            if(rc==0&&saving){char folder[192];if(strlen(path)<sizeof(folder)){strcpy(folder,path);char* slash=strrchr(folder,'/');if(slash)*slash=0;mkdir(folder,0755);result=save_settings_file(path,sealed,sizeof(*sealed))?1:-1;}}
            if(rc==0&&!saving){
                if(plain->format!=1||!memchr(plain->api,0,sizeof(plain->api))||!memchr(plain->device,0,sizeof(plain->device))||!memchr(plain->request,0,sizeof(plain->request)))result=-1;
                else if(plain->user!=user||strcmp(plain->api,api)||strcmp(plain->device,device))result=-2;
                else if(clearing)result=erase_settings_files(path)?1:-1;
                else if(strlen(plain->request)<capacity){strcpy(request,plain->request);result=1;}
            }
        }
    }
    if(plain){mbedtls_platform_zeroize(plain,sizeof(*plain));heap_caps_free(plain);}
    if(sealed){mbedtls_platform_zeroize(sealed,sizeof(*sealed));heap_caps_free(sealed);}
    if(!saving&&!clearing&&result!=1)mbedtls_platform_zeroize(request,capacity);
    return result;
}
}
