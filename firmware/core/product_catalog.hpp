#pragma once
#include "cJSON.h"
#include <cstdio>
#include <cstring>
#include <string>
#include <cctype>
namespace tab5::catalog {
constexpr unsigned field_count=14;
struct Product {
    int id=0,version=0;bool active=true;
    char sku[33]{},barcode[15]{},name[481]{},description[2001]{},category[321]{},unit[9]{"UN"};
    char cost[24]{"0"},sale[24]{"0"},stock[24]{"0"},minimum[24]{"0"},maximum[24]{},ncm[9]{},cest[8]{},origin[4]{};
    char created[40]{},updated[40]{};
};
inline constexpr const char* keys[]={"sku","barcode","name","description","category","unit","cost_price","sale_price","stock","stock_min","stock_max","ncm","cest","origin"};

inline char* field(Product& p,unsigned i){char* fields[]={p.sku,p.barcode,p.name,p.description,p.category,p.unit,p.cost,p.sale,p.stock,p.minimum,p.maximum,p.ncm,p.cest,p.origin};return fields[i];}
inline size_t capacity(unsigned i){constexpr size_t sizes[]={33,15,481,2001,321,9,24,24,24,24,24,9,8,4};return sizes[i];}
inline const char* json_text(cJSON* object,const char* key){auto* value=cJSON_GetObjectItemCaseSensitive(object,key);return cJSON_IsString(value)?value->valuestring:"";}
inline int number(cJSON* object,const char* key){auto* value=cJSON_GetObjectItemCaseSensitive(object,key);return cJSON_IsNumber(value)?value->valueint:0;}
inline bool decode(cJSON* object,Product& p){
    if(!cJSON_IsObject(object)){return false;}
    p=Product{};p.id=number(object,"id");p.version=number(object,"version");
    if(p.id<=0 || p.version<=0)return false;
    for(unsigned i=0;i<field_count;++i){auto* value=cJSON_GetObjectItemCaseSensitive(object,keys[i]);
        if(i==13 && cJSON_IsNumber(value))snprintf(p.origin,sizeof(p.origin),"%d",value->valueint);
        else {const char* text=json_text(object,keys[i]);if(strlen(text)>=capacity(i))return false;snprintf(field(p,i),capacity(i),"%s",text);}}
    p.active=cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(object,"active"));
    snprintf(p.created,sizeof(p.created),"%s",json_text(object,"created_at"));snprintf(p.updated,sizeof(p.updated),"%s",json_text(object,"updated_at"));return p.sku[0]&&p.name[0];
}
inline std::string folded(const char* text){
    std::string out;for(const auto* p=reinterpret_cast<const unsigned char*>(text);*p;++p){
        if(*p==0xc3 && p[1]>=0x80 && p[1]<=0x9e && p[1]!=0x97){out+=char(0xc3);out+=char(p[1]+0x20);++p;}
        else out+=char(*p<128?std::tolower(*p):*p);
    }return out;
}
}
