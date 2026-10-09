#include "offline.hpp"
#include "journal.hpp"
#include "esp_heap_caps.h"
#include "offline_catalog.hpp"
#include "settings_file.hpp"
#include <cassert>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <vector>
#include <iostream>
using namespace tab5;
namespace fs=std::filesystem;
static char plain[16385],sealed[33001];
std::string row(int id){return "{\"id\":"+std::to_string(id)+",\"version\":1,\"sku\":\"SKU"+std::to_string(id)+"\",\"name\":\"Café São João\",\"active\":true,\"sale_price\":\"190.00\"}";}
std::vector<std::string> lines(const std::string& path){std::ifstream file(path);std::vector<std::string> out;std::string line;while(std::getline(file,line))out.push_back(line);return out;}
void write_lines(const std::string& path,const std::vector<std::string>& records){std::ofstream file(path);for(const auto& line:records)file<<line<<'\n';}
int main(){
    fs::create_directories(TAB5_OFFLINE_DIRECTORY);
    unsigned char key[32]{};offline_configure(key,"https://test.invalid","device-a");
    const auto journal=std::string(TAB5_OFFLINE_DIRECTORY)+"/pending.enc";
    const char* api="https://test.invalid";const char* device="device-a";
    const char* aad="TAB5 ERP pending sale v1";
    auto pending=[&](const char* operation,int user=17,const char* origin="device-a",const char* context="TAB5 ERP pending sale v1"){
        return protected_request(operation,user,plain,sizeof(plain),key,api,origin,journal.c_str(),context);
    };
    assert(pending("load")==0);
    assert(!protected_record_exists(journal.c_str()));
    assert(protected_record_exists((journal+"/child").c_str())==false);
    strcpy(plain,"{\"idempotency_key\":\"journal-v1-original-key\"}");assert(pending("save")==1);
    strcpy(plain,"{\"idempotency_key\":\"journal-v1-current-key\"}");assert(pending("save")==1);
    assert(pending("load")==1&&strstr(plain,"journal-v1-current-key"));
    assert(protected_record_exists(journal.c_str()));
    assert(protected_record_exists((journal+"/child").c_str())); // ENOTDIR must fail closed.
    for(int allowed: {0,1}){int live=tab5_alloc_live;tab5_alloc_fail_after=allowed;assert(pending("load")<0&&plain[0]==0);assert(tab5_alloc_live==live);tab5_alloc_fail_after=-1;}
    assert(pending("load",18)==-2&&plain[0]==0);
    assert(pending("clear",18)==-2&&fs::exists(journal));
    assert(pending("load",17,"other-device")==-2);
    assert(pending("load",17,device,"TAB5 ERP pending finance v1")<0);
    assert(protected_request("load",17,plain,sizeof(plain),key,"https://other.invalid",device,journal.c_str(),aad)==-2);
    key[0]=1;assert(pending("load")<0);key[0]=0;
    std::ifstream input(journal,std::ios::binary);std::string bytes((std::istreambuf_iterator<char>(input)),{});input.close();
    assert(bytes.size()==4332); // Original v1 fixed binary layout retained.
    auto put=[&](const std::string& value){std::ofstream file(journal,std::ios::binary);file.write(value.data(),value.size());};
    for(size_t i: {0u,4u,15u,16u,31u,32u,160u,4331u}){auto damaged=bytes;damaged[i]^=1;put(damaged);assert(pending("load")<0&&plain[0]==0);assert(pending("clear")<0&&fs::exists(journal));}
    for(size_t size: {0u,1u,4u,4331u}){put(bytes.substr(0,size));assert(pending("load")<0);}
    put(bytes+"x");assert(pending("load")<0); // Reject trailing bytes.
    fs::remove(journal);assert(pending("load")==1&&strstr(plain,"journal-v1-original-key"));
    put(bytes);char short_buffer[2]={'x',0};
    assert(protected_request("load",17,short_buffer,sizeof(short_buffer),key,api,device,journal.c_str(),aad)<0&&short_buffer[0]==0);
    memset(plain,'x',sizeof(plain));assert(pending("save")<0);assert(pending("load")==1&&strstr(plain,"journal-v1-current-key"));
    assert(pending("unknown")<0);assert(pending("clear")==1&&!fs::exists(journal)&&!fs::exists(journal+".bak"));
    assert(pending("load")==0);
    assert(offline_seal("record-a","Configuração e rascunho",sealed,sizeof(sealed)));
    assert(offline_open("record-a",sealed,plain,sizeof(plain))&&std::string(plain)=="Configuração e rascunho");
    assert(!offline_open("record-b",sealed,plain,sizeof(plain))&&plain[0]==0);
    auto copy=std::string(sealed);sealed[60]=sealed[60]=='A'?'B':'A';assert(!offline_open("record-a",sealed,plain,sizeof(plain)));
    offline_configure(key,"https://other.invalid","device-a");assert(!offline_open("record-a",copy.c_str(),plain,sizeof(plain)));
    offline_configure(key,"https://test.invalid","device-b");assert(!offline_open("record-a",copy.c_str(),plain,sizeof(plain)));
    key[0]=1;offline_configure(key,"https://test.invalid","device-a");assert(!offline_open("record-a",copy.c_str(),plain,sizeof(plain)));
    key[0]=0;offline_configure(key,"https://test.invalid","device-a");
    std::strcpy(plain,"{\"items\":[{\"quantity\":\"2.500\"}],\"format\":1}");
    assert(offline_blob("load","draft",17,plain,sizeof(plain))==0);
    std::strcpy(plain,"{\"items\":[{\"quantity\":\"2.500\"}],\"format\":1}");
    assert(offline_blob("save","draft",17,plain,sizeof(plain))==1&&offline_draft_exists());
    offline_lock();assert(offline_blob("load","draft",17,plain,sizeof(plain))<0);
    offline_configure(key,"https://test.invalid","device-a");
    assert(offline_blob("load","draft",17,plain,sizeof(plain))==1&&strstr(plain,"2.500"));
    assert(offline_blob("load","draft",18,plain,sizeof(plain))==0);
    assert(offline_blob("save","draft",17,plain,sizeof(plain))==1);
    auto draft=std::string(TAB5_OFFLINE_DIRECTORY)+"/draft-17.enc";
    {std::ofstream f(draft,std::ios::binary);f<<"truncated";}
    assert(offline_blob("load","draft",17,plain,sizeof(plain))<0); // Never hide damaged operation with stale backup.
    fs::remove(draft);assert(offline_blob("load","draft",17,plain,sizeof(plain))==1); // Interrupted rename recovers backup.
    assert(offline_blob("clear","draft",17,plain,sizeof(plain))==1&&!offline_draft_exists());
    const char* request="{\"idempotency_key\":\"draft-request-key-0001\",\"items\":[{\"product_id\":1}]}";
    strcpy(plain,"{\"format\":1,\"items\":[{\"quantity\":\"2.500\"}]}");assert(offline_blob("save","draft",17,plain,sizeof(plain))==1);
    assert(offline_draft_pending(17,plain,sizeof(plain))==0);
    assert(offline_draft_link(17,request)==1);
    // Reset after marking the draft, before saving the original request journal.
    offline_lock();offline_configure(key,"https://test.invalid","device-a");
    assert(offline_draft_pending(17,plain,sizeof(plain))==1&&!strcmp(plain,request));
    assert(offline_draft_link(17,"{\"idempotency_key\":\"another-key-0001\"}")<0);
    assert(offline_draft_settle(17,"unrelated-request",false)==1&&offline_draft_exists());
    assert(offline_draft_settle(17,request,true)==1);assert(offline_draft_pending(17,plain,sizeof(plain))==0);
    assert(offline_blob("load","draft",17,plain,sizeof(plain))==1&&strstr(plain,"2.500"));
    assert(offline_draft_link(17,request)==1&&offline_draft_settle(17,request,false)==1&&!offline_draft_exists());
    assert(offline_draft_settle(17,request,false)==1);
    auto path=std::string(TAB5_OFFLINE_DIRECTORY)+"/catalog.enc";
    CatalogHeader header;header.revision=3;header.time=1800000000;strcpy(header.epoch,"11111111-1111-1111-1111-111111111111");
    {CatalogFile writer;assert(writer.write(path,header));for(int i=1;i<=3;++i)assert(writer.append(row(i).c_str()));assert(writer.finish());}
    assert(catalog_path_valid(path));auto original=lines(path);assert(original.size()==5);
    for(int allowed: {0,1}){int live=tab5_alloc_live;tab5_alloc_fail_after=allowed;assert(!catalog_path_valid(path));assert(tab5_alloc_live==live);tab5_alloc_fail_after=-1;assert(catalog_path_valid(path));}
    {CatalogFile reader;assert(reader.read(path)&&reader.header.revision==3);for(int i=1;i<=3;++i){assert(reader.next(plain,sizeof(plain))==1&&std::string(plain)==row(i));}assert(reader.next(plain,sizeof(plain))==0);}
    auto invalid=original;invalid.pop_back();write_lines(path,invalid);assert(!catalog_path_valid(path));
    invalid=original;std::swap(invalid[1],invalid[2]);write_lines(path,invalid);assert(!catalog_path_valid(path));
    invalid=original;invalid[1][60]=invalid[1][60]=='A'?'B':'A';write_lines(path,invalid);assert(!catalog_path_valid(path));
    invalid=original;invalid.push_back(original.back());write_lines(path,invalid);assert(!catalog_path_valid(path));
    write_lines(path,original);{CatalogFile writer;assert(writer.write(path+".tmp",header));assert(writer.append(row(4).c_str()));} // Loss before footer.
    assert(catalog_path_valid(path)&&!catalog_path_valid(path+".tmp"));
    {CatalogFile writer;header.revision=4;assert(writer.write(path+".tmp",header));assert(writer.append(row(4).c_str()));assert(writer.finish());}
    assert(catalog_path_valid(path+".tmp")&&commit_settings_temp(path));
    assert(catalog_path_valid(path)&&catalog_path_valid(path+".bak"));
    offline_lock();assert(!catalog_path_valid(path));
    std::cout<<"PASS: AES-GCM, escopo/PIN, rascunho, corrupção, truncamento, ordem, footer e recuperação após reinício.\n";
}
