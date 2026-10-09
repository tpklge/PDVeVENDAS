#include "offline_catalog.hpp"
#include "offline.hpp"
#include "product_catalog.hpp"
#include "esp_heap_caps.h"
#include "esp_random.h"
#include <cstring>
#include "mbedtls/platform_util.h"
#include <unistd.h>
#ifndef TAB5_HOST_TEST
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#endif
namespace tab5 {
CatalogFile::CatalogFile(){plain=static_cast<char*>(heap_caps_calloc(1,6002,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));encoded=static_cast<char*>(heap_caps_calloc(1,8193,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));mbedtls_sha256_init(&hash);}
CatalogFile::~CatalogFile(){if(file)fclose(file);if(plain)mbedtls_platform_zeroize(plain,6002);if(encoded)mbedtls_platform_zeroize(encoded,8193);heap_caps_free(plain);heap_caps_free(encoded);mbedtls_sha256_free(&hash);}
bool CatalogFile::line(const char* input,unsigned index){std::string context=index?std::string(header.nonce)+":"+std::to_string(index):"catalog-header";return offline_seal(context.c_str(),input,encoded,8193)&&fprintf(file,"%s\n",encoded)>=0;}
bool CatalogFile::read(const std::string& path){if(file){fclose(file);file=nullptr;}writing=false;count=0;ended=false;header=CatalogHeader{};if(!plain||!encoded)return false;file=fopen(path.c_str(),"rb");if(!file)return false;
    if(!fgets(encoded,8193,file)||!strchr(encoded,'\n'))return false;
    if(!offline_open("catalog-header",encoded,plain,6002))return false;
    auto* data=cJSON_Parse(plain);bool ok=catalog::number(data,"format")==2&&catalog::number(data,"revision")>0&&strlen(catalog::json_text(data,"epoch"))==36&&strlen(catalog::json_text(data,"nonce"))==32;
    if(ok){header.revision=catalog::number(data,"revision");snprintf(header.epoch,sizeof(header.epoch),"%s",catalog::json_text(data,"epoch"));snprintf(header.nonce,sizeof(header.nonce),"%s",catalog::json_text(data,"nonce"));auto* t=cJSON_GetObjectItemCaseSensitive(data,"time");header.time=cJSON_IsNumber(t)?static_cast<long long>(t->valuedouble):0;}cJSON_Delete(data);mbedtls_sha256_starts(&hash,0);return ok;
}
bool CatalogFile::write(const std::string& path,const CatalogHeader& metadata){if(file){fclose(file);file=nullptr;}count=0;ended=false;writing=true;header=metadata;if(!plain||!encoded)return false;file=fopen(path.c_str(),"wb");if(!file)return false;
    unsigned char nonce[16];esp_fill_random(nonce,16);for(unsigned i=0;i<16;++i)snprintf(header.nonce+i*2,3,"%02x",nonce[i]);snprintf(plain,6002,"{\"format\":2,\"epoch\":\"%s\",\"revision\":%u,\"time\":%lld,\"nonce\":\"%s\"}",header.epoch,header.revision,header.time,header.nonce);mbedtls_sha256_starts(&hash,0);return line(plain,0);
}
int CatalogFile::next(char* output,size_t capacity){if(!file||writing||ended||!fgets(encoded,8193,file)||!strchr(encoded,'\n'))return -1;std::string context=std::string(header.nonce)+":"+std::to_string(count+1);if(!offline_open(context.c_str(),encoded,plain,6002))return -1;
    auto* data=cJSON_Parse(plain);if(cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(data,"end"))){unsigned char digest[32];char hex[65];mbedtls_sha256_finish(&hash,digest);for(unsigned i=0;i<32;++i)snprintf(hex+i*2,3,"%02x",digest[i]);bool ok=catalog::number(data,"count")==static_cast<int>(count)&&!strcmp(hex,catalog::json_text(data,"sha256"))&&fgetc(file)==EOF&&!ferror(file);cJSON_Delete(data);ended=ok;return ok?0:-1;}
    // Validating every row prevents truncated, reordered or mixed snapshots.
    auto* product=static_cast<catalog::Product*>(heap_caps_malloc(sizeof(catalog::Product),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));bool ok=product&&catalog::decode(data,*product);heap_caps_free(product);cJSON_Delete(data);if(!ok||++count>10000||strlen(plain)>=capacity)return -1;mbedtls_sha256_update(&hash,reinterpret_cast<const unsigned char*>(plain),strlen(plain));if(output!=plain)snprintf(output,capacity,"%s",plain);
#ifndef TAB5_HOST_TEST
    if((count&31)==0)vTaskDelay(1);
#endif
    return 1;
}
bool CatalogFile::append(const char* row){if(!file||!writing||ended||strlen(row)>6000||count>=10000)return false;if(!line(row,count+1))return false;++count;mbedtls_sha256_update(&hash,reinterpret_cast<const unsigned char*>(row),strlen(row));return true;}
bool CatalogFile::finish(){if(!file||!writing||ended)return false;unsigned char digest[32];char hex[65];mbedtls_sha256_finish(&hash,digest);for(unsigned i=0;i<32;++i)snprintf(hex+i*2,3,"%02x",digest[i]);snprintf(plain,6002,"{\"end\":true,\"count\":%u,\"sha256\":\"%s\"}",count,hex);bool ok=line(plain,count+1);ok=fflush(file)==0&&ok;ok=fsync(fileno(file))==0&&ok;ok=fclose(file)==0&&ok;file=nullptr;ended=ok;return ok;}
bool CatalogFile::valid(){if(!file||writing)return false;for(;;){int result=next(plain,6002);if(result<=0)return result==0;}}
bool catalog_path_valid(const std::string& path){CatalogFile file;return file.read(path)&&file.valid();}
}
