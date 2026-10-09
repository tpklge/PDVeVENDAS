#include "offline.hpp"
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
