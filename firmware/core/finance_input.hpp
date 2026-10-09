#pragma once
#include <cstring>
namespace tab5 {
inline bool valid_financial_date(const char* value){
    if(!value||std::strlen(value)!=10||value[4]!='-'||value[7]!='-')return false;
    for(unsigned i=0;i<10;++i)if(i!=4&&i!=7&&(value[i]<'0'||value[i]>'9'))return false;
    unsigned year=(value[0]-'0')*1000+(value[1]-'0')*100+(value[2]-'0')*10+value[3]-'0';
    unsigned month=(value[5]-'0')*10+value[6]-'0',day=(value[8]-'0')*10+value[9]-'0';
    if(year<1000||month<1||month>12||day<1)return false;
    constexpr unsigned days[]={31,28,31,30,31,30,31,31,30,31,30,31};
    bool leap=year%4==0&&(year%100!=0||year%400==0);
    return day<=days[month-1]+(month==2&&leap?1u:0u);
}
}
