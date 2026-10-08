#pragma once
#include <cstring>
namespace tab5 {
inline bool has_module_permission(const char* permissions,const char* required){
    if(!required)return true;
    const size_t length=std::strlen(required);
    for(const char* p=permissions;*p;){
        while(*p==' ')++p;
        const char* end=std::strchr(p,' ');
        const size_t token=end?static_cast<size_t>(end-p):std::strlen(p);
        if(token==length && std::memcmp(p,required,length)==0)return true;
        if(!end)break;
        p=end+1;
    }
    return false;
}
}
